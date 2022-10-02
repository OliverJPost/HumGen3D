import json
import os

import bpy
from HumGen3D.backend.preferences.preference_func import get_addon_root
from HumGen3D.human.base.exceptions import HumGenException  # type:ignore
from HumGen3D.human.base.geometry import centroid
from HumGen3D.human.base.shapekey_calculator import (
    build_distance_dict,
    deform_obj_from_difference,
    world_coords_from_obj,
)
from mathutils import Matrix, Vector, kdtree


def correct_shape_to_a_pose(cloth_obj, hg_body, context):
    # TODO mask modifiers
    depsgraph = context.depsgraph_get()

    hg_body_eval = hg_body.evaluated_get(depsgraph)
    distance_dict = build_distance_dict(hg_body_eval, cloth_obj)
    deform_obj_from_difference("", distance_dict, hg_body, cloth_obj, as_shapekey=False)


def add_corrective_shapekeys(cloth_obj, human, cloth_type, context):
    hg_body = human.body_obj
    hg_body_world_coords = world_coords_from_obj(hg_body)
    cloth_obj_world_coords = world_coords_from_obj(cloth_obj)
    distance_dict = build_distance_dict(hg_body_world_coords, cloth_obj_world_coords)

    if not cloth_obj.data.shape_keys:
        sk = cloth_obj.shape_key_add(name="Basis")
        sk.interpolation = "KEY_LINEAR"

    json_path = os.path.join(
        get_addon_root(), "human", "clothing", "corrective_sk_names.json"
    )

    with open(json_path, "r") as f:
        sk_name_dict = json.read(f)

    corrective_shapekey_names = sk_name_dict[cloth_type]
    for cor_sk_name in corrective_shapekey_names:
        evaluated_body_coords = world_coords_from_obj(
            cloth_obj, data=hg_body.data.shape_keys.key_blocks[cor_sk_name].data
        )
        deform_obj_from_difference(
            cor_sk_name,
            distance_dict,
            evaluated_body_coords,
            cloth_obj,
            as_shapekey=True,
        )


def auto_weight_paint(cloth_obj, hg_body):
    # hg_body_world_coords = world_coords_from_obj(hg_body)

    # kd = kdtree.KDTree(len(hg_body_world_coords))

    # for i, co in enumerate(hg_body_world_coords):
    #     kd.insert(co, i)

    # kd.balance()
    # FIXME
    pass


def get_human_from_distance(cloth_obj):
    world_coords_cloth_obj = world_coords_from_obj(cloth_obj)
    centroid_cloth = centroid(world_coords_cloth_obj)

    human_rig_objs = (obj for obj in bpy.data.objects if obj.HG.ishuman)

    human_distances = {}
    for rig_obj in human_rig_objs:
        world_body_coords = world_coords_from_obj(rig_obj.HG.body_obj)
        human_distances[rig_obj] = abs(centroid(world_body_coords) - centroid_cloth)

    closest_human_rig = min(human_distances, key=human_distances.get)

    if human_distances[closest_human_rig] > 2.0:
        raise HumGenException("Clothing does not seem to be on a HG body object.")

    from HumGen3D.human.human import Human

    return Human.from_existing(closest_human_rig)
