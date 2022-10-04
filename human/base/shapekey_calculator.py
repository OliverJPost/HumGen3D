# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy
import numpy as np
from HumGen3D.backend import hg_delete
from HumGen3D.human.keys.keys import apply_shapekeys
from mathutils import Matrix, Vector, kdtree  # type:ignore


def world_coords_from_obj(obj, data=None) -> np.array:
    if not data:
        data = obj.data.vertices

    vert_count = len(data)
    local_coords = np.empty(vert_count * 3, dtype=np.float64)
    data.foreach_get("co", local_coords)

    mx = obj.matrix_world
    world_coords = matrix_multiplication(mx, local_coords)

    return world_coords


def build_distance_dict(body_coordinates_world, target_coordinates_world):
    kd = kdtree.KDTree(len(body_coordinates_world))

    for i, co in enumerate(body_coordinates_world):
        kd.insert(co, i)

    kd.balance()

    distance_dict = {}
    for idx_target, co_target in enumerate(target_coordinates_world):
        co_body, idx_body, _ = kd.find_n(co_target, 1)[0]

        distance_dict[idx_target] = (idx_body, co_body - co_target)

    return distance_dict


def matrix_multiplication(matrix: Matrix, coordinates: np.ndarray) -> np.ndarray:
    vert_count = coordinates.shape[0]
    coords_4d = np.ones((vert_count, 4), "f")
    coords_4d[:, :-1] = coordinates

    coords: np.ndarray = np.einsum("ij,aj->ai", matrix, coords_4d)[:, :-1]

    return coords


def sum_shapekeys(obj, skip_corrective_keys=True):
    vert_count = len(obj.data.vertices)
    coords_eval = np.empty(vert_count * 3, dtype=np.float64)
    temp_coords = np.empty(vert_count * 3, dtype=np.float64)

    obj.data.vertices.foreach_get("co", coords_eval)

    body_base_coords = coords_eval.copy()

    for sk in obj.data.shape_keys.key_blocks:
        if sk.name.startswith("cor_") and skip_corrective_keys:
            continue

        if sk.mute or not sk.value:
            continue

        sk.data.foreach_get("co", temp_coords)
        temp_coords -= body_base_coords
        coords_eval += temp_coords * sk.value

    return coords_eval


def deform_obj_from_difference(
    name, distance_dict, body_coords_woorld, deform_obj, as_shapekey=False
):

    sk = deform_obj.data.shape_keys.key_blocks.get(name)
    if as_shapekey:
        if not sk:
            sk = deform_obj.shape_key_add(name=name)
            sk.interpolation = "KEY_LINEAR"
            sk.value = 1

    # TODO fully numpy
    for vertex_index in distance_dict:
        source_new_vert_loc = Vector(body_coords_woorld[distance_dict[vertex_index][0]])
        distance_to_vert = distance_dict[vertex_index][1]
        world_new_loc = source_new_vert_loc - distance_to_vert

        if sk and as_shapekey:
            sk.data[vertex_index].co = (
                deform_obj.matrix_world.inverted() @ world_new_loc
            )
        else:
            deform_obj.data.vertices[vertex_index].co = (
                deform_obj.matrix_world.inverted() @ world_new_loc
            )
