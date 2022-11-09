import json
import os
from typing import TYPE_CHECKING, cast

import bpy

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.backend.preferences.preference_func import get_addon_root
from HumGen3D.common.exceptions import HumGenException  # type:ignore
from HumGen3D.common.geometry import (
    build_distance_dict,
    deform_obj_from_difference,
    world_coords_from_obj,
)
from HumGen3D.common.math import centroid


def correct_shape_to_a_pose(
    cloth_obj: bpy.types.Object, hg_body: bpy.types.Object, context: bpy.types.Context
) -> None:
    # TODO mask modifiers
    depsgraph = context.evaluated_depsgraph_get()

    hg_body_eval = hg_body.evaluated_get(depsgraph)
    hg_body_eval_coords_world = world_coords_from_obj(hg_body_eval)
    cloth_obj_coords_world = world_coords_from_obj(cloth_obj)
    distance_dict = build_distance_dict(
        hg_body_eval_coords_world, cloth_obj_coords_world
    )
    deform_obj_from_difference(
        "", distance_dict, hg_body_eval_coords_world, cloth_obj, as_shapekey=False
    )


def add_corrective_shapekeys(
    cloth_obj: bpy.types.Object, human: "Human", cloth_type: str
) -> None:
    hg_body = human.objects.body
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
        sk_name_dict = json.load(f)

    corrective_shapekey_names = sk_name_dict[cloth_type]
    for cor_sk_name in corrective_shapekey_names:
        evaluated_body_coords_world = world_coords_from_obj(
            hg_body, data=hg_body.data.shape_keys.key_blocks[cor_sk_name].data
        )
        deform_obj_from_difference(
            cor_sk_name,
            distance_dict,
            evaluated_body_coords_world,
            cloth_obj,
            as_shapekey=True,
        )

    _set_cloth_corrective_drivers(
        hg_body, cloth_obj, cloth_obj.data.shape_keys.key_blocks
    )


def _set_cloth_corrective_drivers(hg_body, hg_cloth, sk):
    """Sets up the drivers of the corrective shapekeys on the clothes

    Args:
        hg_body (Object): HumGen body object
        sk (list): List of cloth object shapekeys #CHECK
    """
    try:
        for driver in hg_cloth.data.shape_keys.animation_data.drivers[:]:
            hg_cloth.data.shape_keys.animation_data.drivers.remove(driver)
    except AttributeError:
        pass

    for driver in hg_body.data.shape_keys.animation_data.drivers:
        target_sk = driver.data_path.replace('key_blocks["', "").replace(
            '"].value', ""
        )  # TODO this is horrible

        if target_sk not in [shapekey.name for shapekey in sk]:
            continue

        new_driver = sk[target_sk].driver_add("value")
        new_var = new_driver.driver.variables.new()
        new_var.type = "TRANSFORMS"
        new_target = new_var.targets[0]
        old_var = driver.driver.variables[0]
        old_target = old_var.targets[0]
        new_target.id = hg_body.parent

        new_driver.driver.expression = driver.driver.expression
        new_target.bone_target = old_target.bone_target
        new_target.transform_type = old_target.transform_type
        new_target.transform_space = old_target.transform_space


def auto_weight_paint(
    cloth_obj: bpy.types.Object,
    hg_body: bpy.types.Object,
    context: bpy.types.Context,
    hg_rig: bpy.types.Object,
) -> None:
    for mod in hg_body.modifiers:
        if mod.type == "MASK":
            mod.show_viewport = False
            mod.show_render = False

    armature = next(
        (mod for mod in cloth_obj.modifiers if mod.type == "ARMATURE"), None
    )
    if not armature:
        armature = cloth_obj.modifiers.new(name="Cloth Armature", type="ARMATURE")
    armature.object = hg_rig

    with context.temp_override(
        active_object=cloth_obj, object=cloth_obj, selected_objects=[cloth_obj]
    ):
        # use old method for versions older than 2.90
        if (2, 90, 0) > bpy.app.version:
            while cloth_obj.modifiers.find(armature.name) != 0:
                bpy.ops.object.modifier_move_up(modifier=armature.name)
        else:
            bpy.ops.object.modifier_move_to_index(modifier=armature.name, index=0)

    cloth_obj.parent = hg_rig

    with context.temp_override(
        active_object=hg_body, object=hg_body, selected_objects=[hg_body, cloth_obj]
    ):
        bpy.ops.object.data_transfer(
            data_type="VGROUP_WEIGHTS",
            vert_mapping="NEAREST",
            layers_select_src="ALL",
            layers_select_dst="NAME",
            mix_mode="REPLACE",
        )

    for mod in hg_body.modifiers:
        if mod.type == "MASK":
            mod.show_viewport = True
            mod.show_render = True


def get_human_from_distance(cloth_obj: bpy.types.Object) -> "Human":
    world_coords_cloth_obj = world_coords_from_obj(cloth_obj)
    centroid_cloth = centroid(world_coords_cloth_obj)

    human_rig_objs = (obj for obj in bpy.data.objects if obj.HG.ishuman)

    human_distances = {}
    for rig_obj in human_rig_objs:
        world_body_coords = world_coords_from_obj(rig_obj.HG.body_obj)
        human_distances[rig_obj] = abs(
            (centroid(world_body_coords) - centroid_cloth).length
        )

    closest_human_rig = min(human_distances, key=human_distances.get)  # type:ignore

    if human_distances[closest_human_rig] > 2.0:
        raise HumGenException("Clothing does not seem to be on a HG body object.")

    from HumGen3D.human.human import Human

    return cast(Human, Human.from_existing(closest_human_rig))
