"""Implements class for generating haircards from a particle system."""

import contextlib
import json
import os
import random
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Iterable, Literal

import bmesh
import bpy
import numpy as np
from HumGen3D import get_prefs
from HumGen3D.backend.preferences.preference_func import get_addon_root
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.geometry import (
    build_distance_dict,
    deform_obj_from_difference,
    obj_from_pydata,
    world_coords_from_obj,
)
from HumGen3D.common.math import create_kdtree, normalize
from HumGen3D.common.memory_management import hg_delete
from HumGen3D.common.type_aliases import C
from HumGen3D.extern.rdp import rdp

if TYPE_CHECKING:
    from ..human import Human

UVCoords = list[list[list[float]]]


class HairCollection:
    """Class for generating haircards from a particle system."""

    def __init__(
        self,
        hair_obj: bpy.types.Object,
        human: "Human",
    ) -> None:
        """Get a new instance based on a particle system converted to a mesh.

        Args:
            hair_obj (bpy.types.Object): Particle system converted to mesh.
            human (Human): Human instance
        """
        self.mx_world_hair_obj = hair_obj.matrix_world

        body_world_coords_eval = world_coords_from_obj(
            human.objects.body, data=human.keys.all_deformation_shapekeys, local=False
        )
        body_local_coords_eval = world_coords_from_obj(
            human.objects.body, data=human.keys.all_deformation_shapekeys, local=True
        )
        self.kd = create_kdtree(body_world_coords_eval)
        self.kd_local = create_kdtree(body_local_coords_eval)

        self.hair_coords = world_coords_from_obj(hair_obj)
        nearest_vert_idx = np.array([self.kd.find(co)[1] for co in self.hair_coords])
        verts = human.objects.body.data.vertices
        self.nearest_normals = np.array(
            [tuple(verts[idx].normal.normalized()) for idx in nearest_vert_idx]
        )

        bm = bmesh.new()  # type:ignore[call-arg]
        bm.from_mesh(hair_obj.data)
        self.hairs = list(self._get_individual_hairs(bm))
        bm.free()
        hg_delete(hair_obj)
        self.objects: dict[int, bpy.types.Object] = {}
        self.materials = []

    @staticmethod
    def _walk_island(vert: bmesh.types.BMVert) -> Iterable[int]:
        """Walk all un-tagged linked verts.

        Args:
            vert (bmesh.types.BMVert): Start vert to walk from.

        Yields:
            int: Index of the next vert.
        """
        vert.tag = True
        yield vert.index
        linked_verts = [
            e.other_vert(vert) for e in vert.link_edges if not e.other_vert(vert).tag
        ]

        for v in linked_verts:
            if v.tag:
                continue
            yield from HairCollection._walk_island(v)

    def _get_individual_hairs(
        self, bm: bmesh.types.BMesh
    ) -> Iterable[tuple[np.ndarray, float]]:  # noqa[TAE002]

        start_verts = []
        for v in bm.verts:
            if len(v.link_edges) == 1:
                start_verts.append(v)
        islands_dict: dict[int, list[np.ndarray]] = defaultdict()  # noqa

        found_verts = set()
        for start_vert in start_verts:
            if start_vert.index in found_verts:
                continue
            island_idxs = np.fromiter(self._walk_island(start_vert), dtype=np.int64)

            yield island_idxs, np.linalg.norm(
                self.hair_coords[island_idxs[0]] - self.hair_coords[island_idxs[-2]]
            )

            found_verts.add(island_idxs[-1])

    def create_mesh(
        self, quality: Literal["low", "medium", "high", "ultra"] = "high"
    ) -> Iterable[bpy.types.Object]:
        """Create a haircard mesh for downsampled hairs.

        Args:
            quality (Literal["low", "medium", "high", "ultra"], optional): Quality of
                the haircards. Defaults to "high".

        Yields:
            bpy.types.Object: Haircard objects for each resolution.
        """
        long_hairs = [hair for hair, length in self.hairs if length > 0.1]
        medium_hairs = [hair for hair, length in self.hairs if 0.1 >= length > 0.05]
        short_hairs = [hair for hair, length in self.hairs if 0.05 >= length]

        quality_dict = {
            "ultra": (1, 5, 6, 0.002, 0.5),
            "high": (3, 6, 6, 0.003, 1),
            "medium": (6, 12, 14, 0.005, 1),
            "low": (15, 20, 20, 0.005, 2),
        }
        chosen_quality = quality_dict[quality]

        all_hairs = []
        for i, hair_list in enumerate((short_hairs, medium_hairs, long_hairs)):
            if len(hair_list) > 30:
                all_hairs.extend(hair_list[:: chosen_quality[i]])
            else:
                all_hairs.extend(hair_list)

        rdp_downsized_hair_co_idxs = [
            hair_vert_idxs[
                rdp(
                    self.hair_coords[hair_vert_idxs],
                    epsilon=chosen_quality[3],
                    return_mask=True,
                )
            ]
            for hair_vert_idxs in all_hairs
        ]
        hair_len_dict: dict[int, list[list[int]]] = defaultdict()  # noqa[TAE002]
        for hair_vert_idxs in rdp_downsized_hair_co_idxs:
            hair_len_dict.setdefault(len(hair_vert_idxs), []).append(hair_vert_idxs)

        hair_len_dict_np: dict[int, np.ndarray] = {
            i: np.array(hairs) for i, hairs in hair_len_dict.items()
        }

        for hair_co_len, hair_vert_idxs in hair_len_dict_np.items():
            hair_coords = self.hair_coords[hair_vert_idxs]
            nearest_normals = self.nearest_normals[hair_vert_idxs]

            perpendicular = self._calculate_perpendicular_vec(
                hair_co_len, hair_coords, nearest_normals
            )

            new_verts, new_verts_parallel = self._compute_new_ver_coordinaes(
                hair_co_len, hair_coords, nearest_normals, perpendicular
            )

            faces, faces_parallel = self._compute_new_face_vert_idxs(
                hair_co_len, hair_coords
            )

            all_verts = np.concatenate((new_verts, new_verts_parallel))
            all_faces = np.concatenate((faces, faces_parallel + len(new_verts)))
            all_faces = all_faces.reshape((-1, 4))

            obj = obj_from_pydata(
                f"hair_{hair_co_len}",
                all_verts,
                faces=all_faces,
                use_smooth=True,
                context=bpy.context,
            )

            self.objects[hair_co_len] = obj
            yield obj

    @staticmethod
    def _compute_new_face_vert_idxs(
        hair_co_len: int, hair_coords: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        faces = np.empty((len(hair_coords), hair_co_len - 1, 4), dtype=np.int64)

        for i in range(hair_coords.shape[0]):
            for j in range(hair_co_len - 1):
                corr = i * hair_co_len * 2
                faces[i, j, :] = (
                    corr + hair_co_len * 2 - j - 1,
                    corr + hair_co_len * 2 - j - 2,
                    corr + j + 1,
                    corr + j,
                )
        faces_parallel = faces.copy()
        return faces, faces_parallel

    @staticmethod
    def _compute_new_ver_coordinaes(
        hair_co_len: int,
        hair_coords: np.ndarray,
        nearest_normals: np.ndarray,
        perpendicular: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        segment_correction = HairCollection._calculate_segment_correction(hair_co_len)
        hair_length = np.linalg.norm(hair_coords[:, 0] - hair_coords[:, -1], axis=1)
        length_correction = np.ones(hair_coords.shape[0])
        np.place(length_correction, hair_length < 0.01, 0.8)
        np.place(length_correction, hair_length < 0.005, 0.6)
        length_correction = length_correction[:, None, None]
        perpendicular_offset = segment_correction * perpendicular * length_correction

        head_normal_offset = (
            segment_correction * np.abs(nearest_normals) * length_correction * 0.3
        )

        hair_coords_right = hair_coords + perpendicular_offset
        hair_coords_left = np.flip(hair_coords, axis=1) - perpendicular_offset
        hair_coords_top = hair_coords + head_normal_offset  # noqa
        hair_coords_bottom = hair_coords - head_normal_offset  # noqa

        new_verts = np.concatenate((hair_coords_left, hair_coords_right), axis=1)
        new_verts_parallel = np.concatenate(
            (hair_coords_top, hair_coords_bottom), axis=1
        )

        new_verts = new_verts.reshape((-1, 3))
        new_verts_parallel = new_verts_parallel.reshape((-1, 3))
        return new_verts, new_verts_parallel

    @staticmethod
    def _calculate_perpendicular_vec(
        hair_co_len: int,
        hair_coords: np.ndarray,
        nearest_normals: np.ndarray,
    ) -> np.ndarray:
        hair_keys_next_coords = np.roll(hair_coords, -1, axis=1)
        hair_key_vectors = normalize(hair_keys_next_coords - hair_coords)
        if hair_co_len > 1:
            hair_key_vectors[:, -1] = hair_key_vectors[:, -2]

        # Fix for bug in Numpy returning NoReturn causing unreachable code
        def crossf(a: np.ndarray, b: np.ndarray, axis) -> np.ndarray:  # type: ignore
            return np.cross(a, b, axis=axis)

        perpendicular = crossf(nearest_normals, hair_key_vectors, 2)
        return perpendicular

    @staticmethod
    def _calculate_segment_correction(hair_co_len: int) -> np.ndarray:
        """Makes an array of scalars to make the hair get narrower with each segment.

        Args:
            hair_co_len (int): Number of coordinates per hair.

        Returns:
            np.ndarray: Array of scalars to multiply with the perpendicular
                vector.
        """
        length_correction = np.arange(0.01, 0.03, 0.02 / hair_co_len, dtype=np.float32)

        length_correction = length_correction[::-1]
        length_correction = np.expand_dims(length_correction, axis=-1)
        return length_correction

    def add_uvs(self) -> None:
        """Add uvs to all hair objects."""
        haircard_json = os.path.join(
            get_prefs().filepath,
            "hair",
            "haircards",
            "HairMediumLength_zones.json",
        )
        with open(haircard_json, "r") as f:
            hairzone_uv_dict = json.load(f)

        for vert_len, obj in self.objects.items():
            uv_layer = obj.data.uv_layers.new()

            if not obj.data.polygons:
                continue

            vert_loop_dict = self._create_vert_loop_dict(obj, uv_layer)

            self._set_vert_group_uvs(hairzone_uv_dict, vert_len, obj, vert_loop_dict)

    @staticmethod
    def _create_vert_loop_dict(
        obj: bpy.types.Object, uv_layer: bpy.types.MeshUVLoopLayer
    ) -> dict[int, list[bpy.types.MeshUVLoop]]:
        vert_loop_dict: dict[int, list[bpy.types.MeshUVLoop]] = {}

        for poly in obj.data.polygons:
            for vert_idx, loop_idx in zip(poly.vertices, poly.loop_indices):
                loop = uv_layer.data[loop_idx]  # type:ignore
                if vert_idx not in vert_loop_dict:
                    vert_loop_dict[vert_idx] = [
                        loop,
                    ]
                else:
                    vert_loop_dict[vert_idx].append(loop)
        return vert_loop_dict

    @staticmethod
    def _set_vert_group_uvs(
        hairzone_uv_dict: dict[str, dict[str, dict[str, UVCoords]]],  # noqa
        vert_len: int,
        obj: bpy.types.Object,
        vert_loop_dict: dict[int, list[bpy.types.MeshUVLoop]],
    ) -> None:
        verts = obj.data.vertices
        for i in range(0, len(verts), vert_len * 2):
            vert_count = vert_len * 2
            hair_verts = verts[i : i + vert_count]  # noqa

            vert_pairs = []
            for vert in hair_verts[:vert_len]:
                vert_pairs.append((vert.index, vert_count - vert.index - 1))

            vert_pairs = zip(  # type:ignore
                [v.index for v in hair_verts[:vert_len]],
                list(reversed([v.index for v in hair_verts[vert_len:]])),
            )

            length = (hair_verts[0].co - hair_verts[vert_len].co).length
            width = (hair_verts[0].co - hair_verts[-1].co).length
            if length > 0.05:
                subdict = random.choice(list(hairzone_uv_dict["long"].values()))
                if width > 0.02:
                    chosen_zone = random.choice(subdict["wide"])
                else:
                    chosen_zone = random.choice(subdict["narrow"])
            else:
                subdict = random.choice(list(hairzone_uv_dict["short"].values()))
                if width > 0.01:
                    chosen_zone = random.choice(subdict["wide"])
                else:
                    chosen_zone = random.choice(subdict["narrow"])

            bottom_left, top_right = chosen_zone

            for i, (vert_left, vert_right) in enumerate(vert_pairs):
                left_loops = vert_loop_dict[vert_left]
                right_loops = vert_loop_dict[vert_right]

                x_min = bottom_left[0]
                x_max = top_right[0]

                y_min = bottom_left[1]
                y_max = top_right[1]
                y_diff = y_max - y_min

                y_relative = i / (vert_len - 1)
                for loop in left_loops:
                    loop.uv = (x_max, y_min + y_diff * y_relative)

                for loop in right_loops:
                    loop.uv = (x_min, y_min + y_diff * y_relative)

    def add_material(self) -> None:
        """Add a material to all hair objects."""
        mat = bpy.data.materials.get("HG_Haircards")
        if not mat:
            blendpath = os.path.join(
                get_prefs().filepath, "hair", "haircards", "haircards_material.blend"
            )
            with bpy.data.libraries.load(blendpath, link=False) as (
                _,
                data_to,
            ):
                data_to.materials = ["HG_Haircards"]

            mat = data_to.materials[0]
        else:
            mat = mat.copy()

        self.materials.append(mat)

        for obj in self.objects.values():
            if not obj.data.materials:
                obj.data.materials.append(mat)

    @injected_context
    def add_haircap(
        self,  # noqa
        human: "Human",
        haircap_type: Literal["Scalp", "Eyelashes", "Brows", "Beard"],
        density_vertex_groups: list[bpy.types.VertexGroup],
        context: C = None,
        downsample_mesh: bool = False,
    ) -> bpy.types.Object:
        """Add a haircap object based on the vertex groups of the human hair systems.

        Args:
            human (Human): The human to add the haircap to.
            density_vertex_groups (list[bpy.types.VertexGroup]): The vertex groups that
                belong to the hair systems the haircards are generated for.
            context (C): The blender context. Defaults to None.
            downsample_mesh (bool): Whether to downsample the haircap mesh.

        Returns:
            bpy.types.Object: The haircap object.
        """
        body_obj = human.objects.body
        vert_count = len(body_obj.data.vertices)

        vg_aggregate = np.zeros(vert_count, dtype=np.float32)

        for vg in density_vertex_groups:
            vg_values = np.zeros(vert_count, dtype=np.float32)
            for i in range(vert_count):
                with contextlib.suppress(RuntimeError):
                    vg_values[i] = vg.weight(i)
            vg_aggregate += vg_values

        vg_aggregate = np.round(vg_aggregate, 4)
        vg_aggregate = np.clip(vg_aggregate, 0, 1)
        if np.max(vg_aggregate) < 0.001:
            vg_aggregate = np.ones(vert_count, dtype=np.float32)

        blendfile = os.path.join(
            get_prefs().filepath, "hair", "haircards", "haircap.blend"
        )
        with bpy.data.libraries.load(blendfile, link=False) as (_, data_to):
            data_to.objects = [
                f"HG_Haircap_{haircap_type}",
            ]

        haircap_obj = data_to.objects[0]
        context.scene.collection.objects.link(haircap_obj)
        haircap_obj.location = human.location
        body_obj_eval_coords = world_coords_from_obj(
            human.objects.body, data=human.keys.all_deformation_shapekeys, local=True
        )
        body_coords = np.empty(
            len(human.objects.body.data.vertices) * 3, dtype=np.float64
        )
        human.objects.body.data.vertices.foreach_get("co", body_coords)
        body_coords = body_coords.reshape((-1, 3))
        haircap_coords = np.empty(len(haircap_obj.data.vertices) * 3, dtype=np.float64)
        haircap_obj.data.vertices.foreach_get("co", haircap_coords)
        haircap_coords = haircap_coords.reshape((-1, 3))
        distance_dict = build_distance_dict(body_coords, haircap_coords)
        deform_obj_from_difference(
            "test", distance_dict, body_obj_eval_coords, haircap_obj, as_shapekey=False
        )

        vc = haircap_obj.data.color_attributes[0]

        bm = None
        if haircap_type in ("Scalp", "Beard"):
            for i, vert_world_co in enumerate(haircap_coords):
                nearest_vert_index = self.kd.find(vert_world_co)[1]
                value = vg_aggregate[nearest_vert_index]
                vc.data[i].color = (value, value, value, 1)

            bm = bmesh.new()  # type:ignore[call-arg]
            bm.from_mesh(haircap_obj.data)
            for edge in bm.edges:
                if edge.is_boundary:
                    v1, v2 = edge.verts
                    vc.data[v1.index].color = (0, 0, 0, 1)
                    vc.data[v2.index].color = (0, 0, 0, 1)

        if haircap_type == "Scalp" and downsample_mesh:
            if not bm:
                bm = bmesh.new()  # type:ignore[call-arg]
                bm.from_mesh(haircap_obj.data)

            edge_json = os.path.join(get_addon_root(), "human", "hair", "haircap.json")
            with open(edge_json, "r") as f:
                edge_idxs = set(json.load(f))

            edges_to_dissolve = [edge for edge in bm.edges if edge.index in edge_idxs]

            bmesh.ops.dissolve_edges(
                bm, edges=edges_to_dissolve, use_verts=True, use_face_split=True
            )

            # Offset mesh to account for lowered resolution
            for v in bm.verts:
                v.co += v.normal * 0.1

        self.haircap_obj = haircap_obj
        if bm:
            bm.to_mesh(haircap_obj.data)
            bm.free()

        return haircap_obj

    def set_node_values(self, human: "Human") -> None:
        """Set values of the hair material node on all materials of the haircards.

        Args:
            human: The human object to get the values from.
        """
        card_materials = self.materials if hasattr(self, "materials") else []

        cap_material = (
            self.haircap_obj.data.materials[0] if hasattr(self, "haircap_obj") else None
        )

        old_hair_mat = human.objects.body.data.materials[2]
        old_node = next(
            node
            for node in old_hair_mat.node_tree.nodes
            if node.bl_idname == "ShaderNodeGroup"
        )

        for mat in [cap_material] + card_materials:
            if not mat:
                continue
            node = next(
                node
                for node in mat.node_tree.nodes
                if node.bl_idname == "ShaderNodeGroup"
            )
            for inp_name in ("Lightness", "Redness"):
                node.inputs[inp_name].default_value = old_node.inputs[
                    inp_name
                ].default_value
