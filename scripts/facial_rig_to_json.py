import json

import bpy
import numpy as np


def build_driver_dict(obj, remove=False) -> dict:
    """Builds a dictionary of drivers on this object, saving their settings to
    be re-used later

    Args:
        obj    (Object)        : object to index drivers from
        remove (bool, optional): Remove the drivers after saving their settings.
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


def main():
    body = bpy.data.objects["HG_FACS_BODY"]
    teeth = bpy.data.objects["HG_FACS_TEETH"]
    json_data = {}

    driver_dict_body = build_driver_dict(body)
    driver_dict_teeth = build_driver_dict(teeth)

    base_coordinates_body = np.empty(len(body.data.vertices) * 3, dtype=np.float64)
    body.data.vertices.foreach_get("co", base_coordinates_body)
    json_data["body"] = {}
    for sk in body.data.shape_keys.key_blocks:
        if sk.name == "Basis":
            continue

        sk_coordinates = np.empty(len(body.data.vertices) * 3, dtype=np.float64)
        sk.data.foreach_get("co", sk_coordinates)

        relative_coordinates = sk_coordinates - base_coordinates_body

        sk_dict = driver_dict_body[sk.name]
        sk_dict["relative_coordinates"] = list(relative_coordinates)
        json_data["body"][sk.name] = sk_dict

    # TODO this is just copy pasted
    base_coordinates_teeth = np.empty(len(teeth.data.vertices) * 3, dtype=np.float64)
    teeth.data.vertices.foreach_get("co", base_coordinates_teeth)
    json_data["teeth"] = {}
    for sk in teeth.data.shape_keys.key_blocks:
        if sk.name == "Basis":
            continue

        sk_coordinates = np.empty(len(teeth.data.vertices) * 3, dtype=np.float64)
        sk.data.foreach_get("co", sk_coordinates)

        relative_coordinates = sk_coordinates - base_coordinates_teeth

        sk_dict = driver_dict_teeth[sk.name]
        sk_dict["relative_coordinates"] = list(relative_coordinates)
        json_data["teeth"][sk.name] = sk_dict

    with open("/Users/ole/Documents/Human Generator/models/face_rig.json", "w") as f:
        json.dump(json_data, f, indent=4)
