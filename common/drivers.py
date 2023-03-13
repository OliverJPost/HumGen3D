# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Functions for dealing with Blender drivers."""

from typing import Any

import bpy


def build_driver_dict(
    obj: bpy.types.Object, remove: bool = True
) -> dict[str, dict[str, Any]]:
    """Builds a dictionary of drivers on this object, to be re-used later.

    Args:
        obj (Object) : object to index drivers from
        remove (bool): Remove the drivers after saving their settings.
            Defaults to True.

    Returns:
        dict:
            key (str): name of the shapekey this driver was controlling
            value (dict):
                key (str): name of setting that was copied
                value (AnyType): value of this setting
    """
    driver_dict = {}
    remove_list = []

    if not obj.data.shape_keys:
        return driver_dict

    for driver in obj.data.shape_keys.animation_data.drivers:

        target_sk = driver.data_path.replace('key_blocks["', "").replace('"].value', "")
        expression = driver.driver.expression
        var = driver.driver.variables[0]
        target = var.targets[0]
        target_bone = target.bone_target
        transform_type = target.transform_type
        transform_space = target.transform_space

        driver_dict[target_sk] = {
            "expression": expression,
            "target_bone": target_bone,
            "transform_type": transform_type,
            "transform_space": transform_space,
        }
        remove_list.append(driver)
    if remove:
        for driver in remove_list:
            obj.data.shape_keys.animation_data.drivers.remove(driver)

    return driver_dict
