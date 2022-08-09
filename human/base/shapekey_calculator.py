import bpy
import numpy as np
from HumGen3D.backend import hg_delete
from HumGen3D.human.length.length import apply_armature
from HumGen3D.human.shape_keys.shape_keys import apply_shapekeys
from mathutils import Vector, kdtree  # type:ignore


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


def deform_obj_from_difference(
    name,
    distance_dict,
    deform_target,
    obj_to_deform,
    as_shapekey=True,
    apply_source_sks=True,
    ignore_cor_sk=False,
):
    """
    Creates a shapekey from the difference between the distance_dict value and the current distance to that corresponding vertex
    """
    deform_target_copy = deform_target.copy()
    deform_target_copy.data = deform_target_copy.data.copy()
    bpy.context.scene.collection.objects.link(deform_target_copy)

    if deform_target_copy.data.shape_keys and ignore_cor_sk:
        for sk in [
            sk
            for sk in deform_target_copy.data.shape_keys.key_blocks
            if sk.name.startswith("cor_")
        ]:
            deform_target_copy.shape_key_remove(sk)

    if apply_source_sks:
        apply_shapekeys(deform_target_copy)
    # apply_armature(source_copy)

    if "Female_" in name or "Male_" in name:
        name = name.replace("Female_", "")
        name = name.replace("Male_", "")

    sk = None
    if as_shapekey:
        sk = obj_to_deform.shape_key_add(name=name)
        sk.interpolation = "KEY_LINEAR"
        sk.value = 1
    elif obj_to_deform.data.shape_keys:
        sk = obj_to_deform.data.shape_keys.key_blocks["Basis"]

    for vertex_index in distance_dict:
        source_new_vert_loc = (
            deform_target_copy.matrix_world
            @ deform_target_copy.data.vertices[distance_dict[vertex_index][0]].co
        )
        distance_to_vert = distance_dict[vertex_index][1]
        world_new_loc = source_new_vert_loc - distance_to_vert

        if sk:
            sk.data[vertex_index].co = (
                obj_to_deform.matrix_world.inverted() @ world_new_loc
            )
        else:
            obj_to_deform.data.vertices[vertex_index].co = (
                obj_to_deform.matrix_world.inverted() @ world_new_loc
            )

    hg_delete(deform_target_copy)
