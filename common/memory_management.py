# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from typing import no_type_check

import bpy

from ..backend.logging import hg_log


@no_type_check
def hg_delete(obj: bpy.types.Object) -> None:
    """Deletes this object thorougly from Blender, also removing mesh data.

    Args:
        obj (bpy.types.Object): Object to remove
    """
    me = obj.data if (obj and obj.type == "MESH") else None

    images, materials = _get_mats_and_images(obj)

    bpy.data.objects.remove(obj)

    if me and not me.users:
        bpy.data.meshes.remove(me)

    for material in [m for m in materials if m and not m.users]:
        try:
            bpy.data.materials.remove(material)
        except Exception as e:  # noqa PIE786
            hg_log("Error while deleting material: ", e)
            pass

    for image in [i for i in images if i and not i.users]:
        try:
            bpy.data.images.remove(image)
        except Exception as e:  # noqa PIE786
            hg_log("Error while deleting image: ", e)
            pass


@no_type_check
def _get_mats_and_images(obj):
    images = []
    materials = []
    if obj.type != "MESH":
        return [], []
    for mat in obj.data.materials:
        materials.append(mat)
        nodes = mat.node_tree.nodes
        for node in [n for n in nodes if n.bl_idname == "ShaderNodeTexImage"]:
            images.append(node.image)

    return list(set(images)), materials


@no_type_check
def remove_broken_drivers():
    """Removes hanging drivers that cause console warnings.

    Credits to batFINGER for this solution.
    """
    for sk in bpy.data.shape_keys:
        if not sk.animation_data:
            continue
        broken_drivers = []

        for d in sk.animation_data.drivers:
            try:
                sk.path_resolve(d.data_path)
            except ValueError:
                broken_drivers.append(d)

        while broken_drivers:
            sk.animation_data.drivers.remove(broken_drivers.pop())
