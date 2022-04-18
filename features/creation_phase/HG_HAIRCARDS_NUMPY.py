import json
import math
import os
import random
from collections import defaultdict
from itertools import islice
from typing import Dict, List, Tuple

import bpy  # type: ignore
import mathutils
import numpy as np
from mathutils import Matrix, Vector

from ...features.common.HG_COMMON_FUNC import find_human, get_prefs


class Hair:
    key_coordinates: np.ndarray
    location: Tuple[float]
    rotation: Tuple[float]
    nearest_vert_normals: np.ndarray
    particle_sys: bpy.types.ParticleSystem
    perpendicular_card: bpy.types.Object
    parallel_card: bpy.types.Object

    def __init__(self, mw, kd, guide_hair, particle_sys, verts):
        self.location = guide_hair.location
        self.rotation = guide_hair.rotation
        self.key_coordinates = np.array([hk.co for hk in guide_hair.hair_keys])

        self.nearest_vert_normals = np.empty(self.key_coordinates.shape)
        for i, k_co in enumerate(self.key_coordinates):
            nearest_vert_idx = kd.find(k_co)[1]
            self.nearest_vert_normals[i] = verts[
                nearest_vert_idx
            ].normal.normalized()

        self.particle_system = particle_sys
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
        hair_keys_next_coords = np.roll(self.key_coordinates, -1, axis=1)
        hair_key_vectors = self.normalized(
            hair_keys_next_coords - self.key_coordinates
        )

        perpendicular = np.cross(head_normals, hair_key_vectors)

        length_correction = np.arange(
            0.01, 0.03, 0.02 / hk_len, dtype=np.float32
        )

        length_correction = length_correction[::-1]
        length_correction = np.expand_dims(length_correction, axis=-1)

        perpendicular_offset = length_correction * np.abs(perpendicular)
        head_normal_offset = length_correction * np.abs(head_normals) * 0.3

        self.perpendicular_card = self.__create_mesh_from_offset(
            mw, scene, perpendicular_offset
        )
        self.parallel_card = self.__create_mesh_from_offset(
            mw, scene, head_normal_offset, check=True
        )

    def __create_mesh_from_offset(self, mw, scene, offset, check=False):
        mesh = bpy.data.meshes.new(name=f"hair_{self.location}")

        vertices_right = self.key_coordinates + offset
        vertices_left = np.flip(self.key_coordinates - offset, axis=0)

        vertices = np.concatenate((vertices_left, vertices_right))
        vertices_subdivided = self.__subdivide_coordinates(
            vertices, factor=1.3
        )
        vertices_subdivided = self.matrix_multiplication(
            mw, vertices_subdivided
        )

        edges = []

        vert_count = vertices_subdivided.shape[0]
        assert vert_count % 2 == 0

        faces = []
        for i in range(int(vert_count / 2)):
            faces.append((i, i + 1, vert_count - i - 2, vert_count - i - 1))

        mesh.from_pydata(vertices_subdivided, edges, faces)
        mesh.update()

        for f in mesh.polygons:
            f.use_smooth = True

        obj = bpy.data.objects.new(f"hair_{self.location}", mesh)

        scene.collection.objects.link(obj)

        return obj

    def __subdivide_coordinates(self, coords: np.ndarray, factor: float = 2.0):
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
            poly_count = len(obj.data.polygons)

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
                for vert_idx, loop_idx in zip(
                    poly.vertices, poly.loop_indices
                ):
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
                get_prefs().filepath, "hair", "haircards", "haircards.blend"
            )
            with bpy.data.libraries.load(blendpath, link=False) as (
                _,
                data_to,
            ):
                data_to.materials = ["HG_Haircards"]

            mat = data_to.materials[0]

        self.perpendicular_card.data.materials.append(mat)
        self.parallel_card.data.materials.append(mat)


class HG_CONVERT_HAIRCARDS(bpy.types.Operator):
    """
    Removes the corresponding hair system
    """

    bl_idname = "hg3d.haircards"
    bl_label = "Convert to hair cards"
    bl_description = "Converts this system to hair cards"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):

        pref = get_prefs()
        scene = context.scene
        hg_rig = find_human(context.object)
        dg = context.evaluated_depsgraph_get()

        hg_body = hg_rig.HG.body_obj.evaluated_get(dg)

        vertices = hg_body.data.vertices
        size = len(vertices)
        kd = mathutils.kdtree.KDTree(size)

        for i, v in enumerate(vertices):
            kd.insert(v.co, i)
        kd.balance()

        mw = hg_body.matrix_world

        hairs: Hair = []
        for ps in hg_body.particle_systems:
            for gh in ps.particles:
                hairs.append(Hair(mw, kd, gh, ps, vertices))

        hairs = self.downsample_to_size(hairs, 100)

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

        for mod in hg_body.modifiers:
            mod.show_viewport = False

        return {"FINISHED"}

    def downsample_to_size(self, list_to_downsample, wanted_size):
        ln = len(list_to_downsample)
        if ln <= wanted_size:
            return list_to_downsample
        proportion = wanted_size / ln
        return list(islice(list_to_downsample, 0, ln, int(1 / proportion)))
