# type:ignore
import json
import math
import os
import random
import time
from collections import defaultdict
from itertools import islice
from typing import Dict, List

import bmesh
import bpy  # type: ignore
import mathutils
import numpy as np
from HumGen3D import Human, get_prefs
from HumGen3D.backend.logging import time_update
from HumGen3D.extern.rdp import rdp
from HumGen3D.human.base.shapekey_calculator import (
    matrix_multiplication,
    world_coords_from_obj,
)
from mathutils import Matrix


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
            new_verts = new_verts.reshape((-1, 3))

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
            verts = [tuple(co) for co in new_verts]

            faces = faces.reshape((-1, 4))
            bpy_faces = [tuple(idxs) for idxs in faces]
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


class Hair:
    key_coordinates: np.ndarray
    nearest_vert_normals: np.ndarray
    particle_sys: bpy.types.ParticleSystem
    perpendicular_card: bpy.types.Object
    parallel_card: bpy.types.Object

    def __init__(self, mw, kd, vert_island, normals):
        self.location = "blabla"
        self.key_coordinates = self.matrix_multiplication(mw, np.array(vert_island))

        self.nearest_vert_normals = np.empty(self.key_coordinates.shape)
        for i, k_co in enumerate(self.key_coordinates):
            nearest_vert_idx = kd.find(k_co)[1]
            split = normals[nearest_vert_idx]
            self.nearest_vert_normals[i] = split

        self.perpendicular_card = None
        self.parallel_card = None

    def normalized(self, a, axis=-1, order=2):
        l2 = np.atleast_1d(np.linalg.norm(a, order, axis))
        l2[l2 == 0] = 1
        return a / np.expand_dims(l2, axis)

    def matrix_multiplication(
        self, matrix: Matrix, coordinates: np.ndarray
    ) -> np.ndarray:
        vert_count = coordinates.shape[0]
        coords_4d = np.ones((vert_count, 4), "f")
        coords_4d[:, :-1] = coordinates

        coords: np.ndarray = np.einsum("ij,aj->ai", matrix, coords_4d)[:, :-1]

        return coords

    def to_mesh(self, mw, scene):
        hk_len = len(self.key_coordinates)
        head_normals = self.nearest_vert_normals
        hair_keys_next_coords = np.roll(self.key_coordinates, -1, axis=0)
        hair_key_vectors = self.normalized(hair_keys_next_coords - self.key_coordinates)
        hair_key_vectors[-1] = hair_key_vectors[-2]

        perpendicular = np.cross(head_normals, hair_key_vectors)

        length_correction = np.arange(0.01, 0.03, 0.02 / hk_len, dtype=np.float32)

        length_correction = length_correction[::-1]
        length_correction = np.expand_dims(length_correction, axis=-1)

        perpendicular_offset = length_correction * perpendicular
        head_normal_offset = length_correction * np.abs(head_normals) * 0.3

        self.perpendicular_card = self.create_mesh_from_offset(
            mw, scene, perpendicular_offset
        )
        self.parallel_card = self.create_mesh_from_offset(
            mw, scene, head_normal_offset, check=True
        )

    def create_mesh_from_offset(self, mw, scene, offset, check=False):
        mesh = bpy.data.meshes.new(name=f"hair_{self.location}")

        vertices_right = self.key_coordinates + offset
        vertices_left = self.key_coordinates - offset

        # Create verts for the left side of the card in reverse order for poly creation
        vertices_left = np.flip(vertices_left, axis=0)

        vertices = np.concatenate((vertices_left, vertices_right))
        vertices_subdivided = self.subdivide_coordinates(vertices, factor=1.3)
        vertices_subdivided = self.matrix_multiplication(mw, vertices_subdivided)

        edges = []

        vert_count = vertices_subdivided.shape[0]
        assert vert_count % 2 == 0

        faces = []
        for i in range(int(vert_count / 2)):
            faces.append((i, i + 1, vert_count - i - 2, vert_count - i - 1))

        return vertices_subdivided, faces

        mesh.from_pydata(vertices_subdivided, edges, faces)
        mesh.update()

        for f in mesh.polygons:
            f.use_smooth = True

        obj = bpy.data.objects.new(f"hair_{self.location}", mesh)

        scene.collection.objects.link(obj)

        return obj

    def subdivide_coordinates(self, coords: np.ndarray, factor: float = 2.0):
        c_len = coords.shape[0]

        # Round samples to nearest EVEN integer
        samples = math.ceil(c_len * factor / 2.0) * 2

        steps_new = np.linspace(0, 1, samples)
        steps_old = np.linspace(0, 1, c_len)

        co_interp = np.empty((samples, 3), dtype=np.float32)

        for i in range(3):
            axis_co = coords[:, i]
            axis_interp = np.interp(steps_new, steps_old, axis_co)

            co_interp[:, i] = axis_interp

        return co_interp

    def add_uv(self):
        for obj in [self.perpendicular_card, self.parallel_card]:

            haircard_json = os.path.join(
                get_prefs().filepath,
                "hair",
                "haircards",
                "HairMediumLength_zones.json",
            )
            with open(haircard_json, "r") as f:
                zone_dict = json.load(f)

            uv_layer = obj.data.uv_layers.new()

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

            flattened_hairzones = []
            for hz in zone_dict["long"]["dense"]["wide"]:
                flattened_hairzones.append(hz)
            for hz in zone_dict["long"]["dense"]["narrow"]:
                flattened_hairzones.append(hz)

            vert_pairs = []
            vert_count = len(obj.data.vertices)
            half = len(obj.data.vertices) // 2
            for vert in obj.data.vertices[:half]:
                vert_pairs.append((vert.index, vert_count - vert.index - 1))

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

                y_relative = i / (half - 1)
                for loop in left_loops:
                    loop.uv = (x_max, y_min + y_diff * y_relative)

                for loop in right_loops:
                    loop.uv = (x_min, y_min + y_diff * y_relative)

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

        self.perpendicular_card.data.materials.append(mat)
        self.parallel_card.data.materials.append(mat)


def walk_island(vert):
    """walk all un-tagged linked verts"""
    vert.tag = True
    yield (tuple(vert.co))
    linked_verts = [
        e.other_vert(vert) for e in vert.link_edges if not e.other_vert(vert).tag
    ]

    for v in linked_verts:
        if v.tag:
            continue
        yield from walk_island(v)


def get_individual_hairs(bm):
    t = time.perf_counter()
    start_verts = []
    for v in bm.verts:
        if len(v.link_edges) == 1:
            start_verts.append(v)
    t = time_update("start vert finding", t)
    islands = []

    found_verts = set()
    for start_vert in start_verts:
        if tuple(start_vert.co) in found_verts:
            continue
        island_list = list(walk_island(start_vert))
        island = np.array(island_list, dtype=np.float64)
        islands.append(island)
        found_verts.update(tuple(island[-1]))

    t = time_update("island finding", t)
    return islands


class HG_CONVERT_HAIRCARDS(bpy.types.Operator):
    bl_idname = "hg3d.haircards"
    bl_label = "Convert to hair cards"
    bl_description = "Converts this system to hair cards"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        human = Human.from_existing(context.object)
        dg = context.evaluated_depsgraph_get()

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
            for obj in objs:
                obj.name += ps.name

            hc.add_uvs()
            hc.add_material()

        return {"FINISHED"}
        hg_body = human.body_obj.evaluated_get(dg)
        vertices = hg_body.data.vertices
        normals = [v.normal.normalized() for v in vertices]
        size = len(vertices)
        kd = mathutils.kdtree.KDTree(size)
        mw = hg_body.matrix_world
        for i, v in enumerate(vertices):
            kd.insert(mw @ v.co, i)
        kd.balance()

        hairs = []
        bm = bmesh.new()
        for mod in human.hair.regular_hair.modifiers:
            ps = mod.particle_system
            ps.settings.child_nbr = 200 // len(ps.particles)

            with context.temp_override(active_object=human.body_obj):
                bpy.ops.object.modifier_convert(modifier=mod.name)

            hair_mesh = context.object
            assert not len(hair_mesh.data.polygons)

            bm.from_mesh(hair_mesh.data)
            for obj in context.selected_objects:
                if obj != hair_mesh:
                    obj.select_set(False)

            individual_hairs = get_individual_hairs(bm)

            mw = obj.matrix_world
            for hair in individual_hairs:
                if len(hair) <= 1:
                    continue
                hair_decimated = rdp(hair, epsilon=0.01)
                hairs.append(Hair(mw, kd, hair_decimated, ps, normals))

        bm.free()

        for hair in reversed(hairs):
            hair.to_mesh(mw, scene)
            hair.add_uv()
            hair.add_material()
        hair_objs = [h.parallel_card for h in hairs] + [
            h.perpendicular_card for h in hairs
        ]

        c = {}

        c["object"] = c["active_object"] = hair_objs[0]
        c["selected_objects"] = c["selected_editable_objects"] = hair_objs

        bpy.ops.object.join(c)

        for mod in human.body_obj.modifiers:
            mod.show_viewport = False
        return {"FINISHED"}

    def downsample_to_size(self, list_to_downsample, wanted_size) -> list[Hair]:
        ln = len(list_to_downsample)
        if ln <= wanted_size:
            return list_to_downsample
        proportion = wanted_size / ln
        return list(islice(list_to_downsample, 0, ln, int(1 / proportion)))
