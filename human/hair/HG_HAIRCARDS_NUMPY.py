# type:ignore
import json
import os
import random
from collections import defaultdict
from typing import Dict, List

import bmesh
import bpy  # type: ignore
import mathutils
import numpy as np
from HumGen3D import Human, get_prefs
from HumGen3D.extern.rdp import rdp  # noqa
from HumGen3D.human.base.shapekey_calculator import (
    matrix_multiplication,
    world_coords_from_obj,
)


class HairCollection:
    hairs: dict[int, list[tuple[np.ndarray, np.ndarray]]]  # noqa

    def __init__(self, hair_obj, body_obj, depsgraph, bm) -> None:
        self.mx_world_hair_obj = hair_obj.matrix_world
        body_obj_eval = body_obj.evaluated_get(depsgraph)

        vertices = body_obj_eval.data.vertices
        size = len(vertices)
        kd = mathutils.kdtree.KDTree(size)
        for i, v in enumerate(vertices):
            kd.insert(body_obj.matrix_world @ v.co, i)
        kd.balance()

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

        bm.from_mesh(hair_obj.data)
        self.hairs = self._get_individual_hairs(bm)
        self.objects = {}

    def create_mesh(self):
        for hair_co_len, hair_vert_idxs in self.hairs.items():
            hair_coords = self.hair_coords[hair_vert_idxs]
            nearest_normals = self.nearest_normals[hair_vert_idxs]

            perpendicular_card_coords = np.empty(
                (len(hair_coords), hair_co_len, 3), np.float64
            )
            parallel_card_coords = perpendicular_card_coords.copy()  # noqa

            hair_keys_next_coords = np.roll(hair_coords, -1, axis=1)
            hair_key_vectors = self._normalized(hair_keys_next_coords - hair_coords)
            if hair_co_len > 1:
                hair_key_vectors[:, -1] = hair_key_vectors[:, -2]

            length_correction = np.arange(
                0.01, 0.03, 0.02 / hair_co_len, dtype=np.float32
            )

            length_correction = length_correction[::-1]
            length_correction = np.expand_dims(length_correction, axis=-1)

            perpendicular = np.cross(nearest_normals, hair_key_vectors, axis=2)
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
            mesh = bpy.data.meshes.new(name="hair")
            faces_parallel = faces.copy()

            all_verts = np.concatenate((new_verts, new_verts_parallel))
            all_faces = np.concatenate((faces, faces_parallel + len(new_verts)))
            verts = [tuple(co) for co in all_verts]

            all_faces = all_faces.reshape((-1, 4))
            bpy_faces = [tuple(idxs) for idxs in all_faces]
            mesh.from_pydata(verts, [], bpy_faces)
            mesh.update()

            for f in mesh.polygons:
                f.use_smooth = True

            obj = bpy.data.objects.new(f"hair_{hair_co_len}", mesh)

            bpy.context.scene.collection.objects.link(obj)  # TODO bpy

            self.objects[hair_co_len] = obj
            yield obj

    def add_uvs(self):
        haircard_json = os.path.join(
            get_prefs().filepath,
            "hair",
            "haircards",
            "HairMediumLength_zones.json",
        )
        with open(haircard_json, "r") as f:
            zone_dict = json.load(f)

        flattened_hairzones = []
        for hz in zone_dict["long"]["dense"]["wide"]:
            flattened_hairzones.append(hz)
        for hz in zone_dict["long"]["dense"]["narrow"]:
            flattened_hairzones.append(hz)

        for vert_len, obj in self.objects.items():
            uv_layer = obj.data.uv_layers.new()

            if not obj.data.polygons:
                continue

            vert_loop_dict = self._create_vert_loop_dict(obj, uv_layer)

            self._set_vert_group_uvs(flattened_hairzones, vert_len, obj, vert_loop_dict)

    def add_material(self):
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

    def _set_vert_group_uvs(self, flattened_hairzones, vert_len, obj, vert_loop_dict):
        verts = obj.data.vertices
        for i in range(0, len(verts), vert_len * 2):
            vert_count = vert_len * 2
            hair_verts = verts[i : i + vert_count]  # noqa

            vert_pairs = []
            for vert in hair_verts[:vert_len]:
                vert_pairs.append((vert.index, vert_count - vert.index - 1))

            vert_pairs = zip(
                [v.index for v in hair_verts[:vert_len]],
                list(reversed([v.index for v in hair_verts[vert_len:]])),
            )

            chosen_zone = random.choice(flattened_hairzones)
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

    def _create_vert_loop_dict(self, obj, uv_layer):
        vert_loop_dict: Dict[int, List[bpy.types.uvloop]] = {}

        for poly in obj.data.polygons:
            for vert_idx, loop_idx in zip(poly.vertices, poly.loop_indices):
                loop = uv_layer.data[loop_idx]
                if vert_idx not in vert_loop_dict:
                    vert_loop_dict[vert_idx] = [
                        loop,
                    ]
                else:
                    vert_loop_dict[vert_idx].append(loop)
        return vert_loop_dict

    def _normalized(self, a, axis=-1, order=2):
        l2 = np.atleast_1d(np.linalg.norm(a, order, axis))
        l2[l2 == 0] = 1
        return a / np.expand_dims(l2, axis)

    def _walk_island(self, vert):
        """walk all un-tagged linked verts"""
        vert.tag = True
        yield vert.index
        linked_verts = [
            e.other_vert(vert) for e in vert.link_edges if not e.other_vert(vert).tag
        ]

        for v in linked_verts:
            if v.tag:
                continue
            yield from self._walk_island(v)

    def _get_individual_hairs(self, bm):
        start_verts = []
        for v in bm.verts:
            if len(v.link_edges) == 1:
                start_verts.append(v)
        islands = defaultdict()

        found_verts = set()
        for start_vert in start_verts:
            if tuple(start_vert.co) in found_verts:
                continue
            island = np.fromiter(self._walk_island(start_vert), dtype=np.int64)
            islands.setdefault(len(island), []).append(island)
            found_verts.add(island[-1])

        return islands


class HG_CONVERT_HAIRCARDS(bpy.types.Operator):
    bl_idname = "hg3d.haircards"
    bl_label = "Convert to hair cards"
    bl_description = "Converts this system to hair cards"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        human = Human.from_existing(context.object)
        dg = context.evaluated_depsgraph_get()
        hair_objs = []
        bm = bmesh.new()
        for mod in human.hair.regular_hair.modifiers:
            ps = mod.particle_system
            ps.settings.child_nbr = 200 // len(ps.particles)

            with context.temp_override(
                active_object=human.body_obj,
                object=human.body_obj,
                selected_objects=[
                    human.body_obj,
                ],
            ):
                bpy.ops.object.modifier_convert(modifier=mod.name)

            hair_obj = context.object
            hc = HairCollection(hair_obj, human.body_obj, dg, bm)
            objs = hc.create_mesh()
            hair_objs.extend(objs)
            for obj in objs:
                obj.name += ps.name

            hc.add_uvs()
            hc.add_material()

        return {"FINISHED"}
        c = {}

        c["object"] = c["active_object"] = hair_objs[0]
        c["selected_objects"] = c["selected_editable_objects"] = hair_objs

        bpy.ops.object.join(c)

        for mod in human.body_obj.modifiers:  # noqa
            mod.show_viewport = False
