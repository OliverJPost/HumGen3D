import contextlib
import json
import os
import random
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Iterable, Set

import bmesh
import bpy
import numpy as np
from HumGen3D import get_prefs
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.geometry import obj_from_pydata  # noqa
from HumGen3D.common.math import create_kdtree, normalize
from HumGen3D.common.shapekey_calculator import (
    matrix_multiplication,
    world_coords_from_obj,
)
from HumGen3D.common.type_aliases import C
from HumGen3D.extern.rdp import rdp

if TYPE_CHECKING:
    from ..human import Human

UVCoords = list[list[list[float]]]


class HairCollection:
    def __init__(
        self,
        hair_obj: bpy.types.Object,
        body_obj: bpy.types.Object,
        depsgraph: bpy.types.Depsgraph,
    ) -> None:
        self.mx_world_hair_obj = hair_obj.matrix_world
        body_obj_eval = body_obj.evaluated_get(depsgraph)

        kd = create_kdtree(body_obj_eval)

        hair_obj_world_co = world_coords_from_obj(hair_obj)
        nearest_vert_idx = np.array([kd.find(co)[1] for co in hair_obj_world_co])
        verts = body_obj.data.vertices
        self.nearest_normals = np.array(
            [tuple(verts[idx].normal.normalized()) for idx in nearest_vert_idx]
        )

        hair_coords = np.empty(len(hair_obj.data.vertices) * 3, dtype=np.float64)
        mx_hair = hair_obj.matrix_world
        hair_obj.data.vertices.foreach_get("co", hair_coords)
        self.hair_coords = matrix_multiplication(mx_hair, hair_coords.reshape((-1, 3)))

        bm = bmesh.new()  # type:ignore[call-arg]
        bm.from_mesh(hair_obj.data)
        self.hairs = self._get_individual_hairs(bm)
        bm.free()
        self.objects: dict[int, bpy.types.Object] = {}

    @staticmethod
    def _walk_island(vert: bmesh.types.BMVert) -> Iterable[int]:
        """walk all un-tagged linked verts"""
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
    ) -> dict[int, np.ndarray[Any, Any]]:
        start_verts = []
        for v in bm.verts:
            if len(v.link_edges) == 1:
                start_verts.append(v)
        islands_dict: dict[int, list[np.ndarray[Any, Any]]] = defaultdict()  # noqa

        found_verts = set()
        for start_vert in start_verts:
            if tuple(start_vert.co) in found_verts:
                continue
            island_idxs = np.fromiter(self._walk_island(start_vert), dtype=np.int64)
            island_co = self.hair_coords[island_idxs]
            island_rdp_masked = island_idxs[
                rdp(island_co, epsilon=0.005, return_mask=True)
            ]

            island = np.fromiter(island_rdp_masked, dtype=np.int64)
            islands_dict.setdefault(len(island), []).append(island)
            found_verts.add(island[-1])

        return {
            hair_len: np.array(islands) for hair_len, islands in islands_dict.items()
        }

    def create_mesh(self) -> Iterable[bpy.types.Object]:
        for hair_co_len, hair_vert_idxs in self.hairs.items():
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
    def _create_obj_from_verts_and_faces(
        obj_name: str, all_verts: np.ndarray[Any, Any], all_faces: np.ndarray[Any, Any]
    ) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(name="hair")
        all_verts_as_tuples = [tuple(co) for co in all_verts]
        all_faces_as_tuples = [tuple(idxs) for idxs in all_faces]

        mesh.from_pydata(all_verts_as_tuples, [], all_faces_as_tuples)
        mesh.update()

        for f in mesh.polygons:
            f.use_smooth = True

        obj = bpy.data.objects.new(obj_name, mesh)  # type:ignore[arg-type]
        return obj

    @staticmethod
    def _compute_new_face_vert_idxs(
        hair_co_len: int, hair_coords: np.ndarray[Any, Any]
    ) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
        faces = np.empty((len(hair_coords), hair_co_len - 1, 4), dtype=np.int64)

        for i in range(hair_coords.shape[0]):
            for j in range(hair_co_len - 1):
                corr = i * hair_co_len * 2
                faces[i, j, :] = (
                    corr + j,
                    corr + j + 1,
                    corr + hair_co_len * 2 - j - 2,
                    corr + hair_co_len * 2 - j - 1,
                )
        faces_parallel = faces.copy()
        return faces, faces_parallel

    @staticmethod
    def _compute_new_ver_coordinaes(
        hair_co_len: int,
        hair_coords: np.ndarray[Any, Any],
        nearest_normals: np.ndarray[Any, Any],
        perpendicular: np.ndarray[Any, Any],
    ) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
        length_correction = HairCollection._calculate_length_correction(hair_co_len)
        perpendicular_offset = length_correction * perpendicular
        head_normal_offset = length_correction * np.abs(nearest_normals) * 0.3

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
        hair_coords: np.ndarray[Any, Any],
        nearest_normals: np.ndarray[Any, Any],
    ) -> np.ndarray[Any, Any]:
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
    def _calculate_length_correction(hair_co_len: int) -> np.ndarray[Any, Any]:
        length_correction = np.arange(0.01, 0.03, 0.02 / hair_co_len, dtype=np.float32)

        length_correction = length_correction[::-1]
        length_correction = np.expand_dims(length_correction, axis=-1)
        return length_correction

    def add_uvs(self) -> None:
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

        for obj in self.objects.values():
            obj.data.materials.append(mat)

    @injected_context
    def add_haircap(
        self,
        human: "Human",
        density_vertex_groups: list[bpy.types.VertexGroup],
        context: C = None,
    ) -> bpy.types.Object:
        body_obj = human.body_obj
        vert_count = len(body_obj.data.vertices)

        vg_aggregate = np.zeros(vert_count, dtype=np.float32)

        for vg in density_vertex_groups:
            vg_values = np.zeros(vert_count, dtype=np.float32)
            for i in range(vert_count):
                with contextlib.suppress(RuntimeError):
                    vg_values[i] = vg.weight(i)
            vg_aggregate += vg_values

        vg_aggregate = np.round(vg_aggregate, 4)
        vert_idxs_to_duplicate = np.nonzero(vg_aggregate)[0]
        vert_idxs_to_duplicate = expand_region(body_obj, vert_idxs_to_duplicate)
        normals = np.empty(vert_count * 3, dtype=np.float64)
        body_obj.data.vertices.foreach_get("normal", normals)
        normals = normals.reshape((-1, 3))

        vert_idx_set = set(vert_idxs_to_duplicate)
        body_world_co = world_coords_from_obj(
            body_obj, data=human.keys.all_deformation_shapekeys
        )
        vert_coordinates_to_duplicate = body_world_co[vert_idxs_to_duplicate]
        vert_idx_translation = {
            orig_idx: i for i, orig_idx in enumerate(vert_idxs_to_duplicate)
        }

        new_faces = []
        for poly in body_obj.data.polygons:
            # Check if all vertices of this face are in the vertices to keep set
            if set(poly.vertices).issubset(vert_idx_set):
                # Set original idx to new idx
                new_faces.append([vert_idx_translation[v] for v in poly.vertices])

        # 3mm offset
        vert_coords_offset = (
            vert_coordinates_to_duplicate + normals[vert_idxs_to_duplicate] * 0.003
        )
        obj = obj_from_pydata(
            "hair_cap", vert_coords_offset, faces=new_faces, context=context
        )

        color_data = np.clip(vg_aggregate[vert_idxs_to_duplicate], 0, 1)
        vc = (
            obj.data.vertex_colors[0]
            if obj.data.vertex_colors
            else obj.data.vertex_colors.new(name="col")
        )
        i = 0
        for poly in obj.data.polygons:
            for j, _ in enumerate(poly.loop_indices):
                vert_idx = poly.vertices[j]
                color_value = color_data[vert_idx]
                vc.data[i].color = (color_value, color_value, color_value, 1.0)
                i += 1

        return obj


def expand_region(
    obj: bpy.types.Object, vert_idxs: Iterable[int]
) -> np.ndarray[Any, Any]:
    bm = bmesh.new()  # type:ignore
    bm.from_mesh(obj.data)
    other_verts: Set[int] = set()
    for vert_idx in vert_idxs:
        other_verts.update(
            (e.other_vert.index for e in bm.verts[vert_idx].link_edges)  # type:ignore
        )

    with_added_verts = vert_idxs.append(other_verts)
    return np.unique(with_added_verts)
