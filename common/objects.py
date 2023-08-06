from typing import Union, Optional

import bpy
import numpy as np

from HumGen3D.common.memory_management import hg_delete

ALL = "ALL"


def import_objects_to_scene_collection(
    filepath: str, names: Union[str, list[str]] = ALL
) -> Union[bpy.types.Object, list[bpy.types.Object]]:
    with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
        if names is ALL:
            data_to.objects = data_from.objects
        else:
            data_to.objects = names

    for obj in data_to.objects:
        bpy.context.collection.objects.link(obj)

    if len(data_to.objects) == 1:
        return data_to.objects[0]
    return data_to.objects


def duplicate_object(obj: bpy.types.Object, context) -> bpy.types.Object:
    new_obj = obj.copy()
    new_obj.data = obj.data.copy()
    context.collection.objects.link(new_obj)
    return new_obj


def remove_all_shapekeys(obj: bpy.types.Object, apply_last: str = None) -> None:
    """Remove all shapekeys from the passed object."""
    if not obj.data.shape_keys:
        return

    if apply_last and apply_last not in obj.data.shape_keys.key_blocks:
        raise ValueError(f"Shape key {apply_last} not found on {obj.name}")

    # List reversed because of StructRNA removed error
    for sk in list(reversed(obj.data.shape_keys.key_blocks))[:]:
        if sk.name == apply_last:
            continue
        obj.shape_key_remove(sk)

    if apply_last:
        sk = obj.data.shape_keys.key_blocks[apply_last]
        obj.shape_key_remove(sk)

    assert obj.data.shape_keys is None


def transfer_shape_key(sk: bpy.types.ShapeKey, to_obj: bpy.types.Object):
    """Transfer the passed shape key to the passed object."""

    # Add basis shape key if it doesn't exist
    if not to_obj.data.shape_keys:
        to_obj.shape_key_add(name="Basis", from_mix=False)

    # Deal with the case where the shape key already exists
    if sk.name in to_obj.data.shape_keys.key_blocks:
        raise ValueError(f"Shape key {sk.name} already exists in {to_obj.name}")

    to_obj.shape_key_add(name=sk.name, from_mix=False)
    new_sk = to_obj.data.shape_keys.key_blocks[sk.name]
    new_sk.value = sk.value
    new_sk.mute = sk.mute
    new_sk.slider_min = sk.slider_min
    new_sk.slider_max = sk.slider_max
    new_sk.interpolation = sk.interpolation
    new_sk.vertex_group = sk.vertex_group
    new_sk.relative_key = sk.relative_key

    sk_coords = np.empty(len(sk.data) * 3, dtype=np.float64)
    sk.data.foreach_get("co", sk_coords)
    new_sk.data.foreach_set("co", sk_coords)


def transfer_as_shape_key(source_obj: bpy.types.Object, to_obj: bpy.types.Object):
    """Transfer the passed object as a shape key to the passed object."""
    sk = source_obj.shape_key_add(name=source_obj.name, from_mix=False)
    transfer_shape_key(sk, to_obj)


def delete_object(obj: bpy.types.Object) -> None:
    """Delete the passed object from the scene."""
    hg_delete(obj)


def apply_sk_to_mesh(sk: bpy.types.ShapeKey, obj: bpy.types.Object) -> None:
    """Apply the passed shape key to the passed object."""
    sk_coords = np.empty(len(sk.data) * 3, dtype=np.float64)
    sk.data.foreach_get("co", sk_coords)
    obj_coords = np.empty(len(obj.data.vertices) * 3, dtype=np.float64)
    obj.data.vertices.foreach_get("co", obj_coords)
    diff = (obj_coords - sk_coords) * sk.value
    obj.data.vertices.foreach_set("co", obj_coords - diff)
    if obj.data.shape_keys:
        obj.data.shape_keys.key_blocks["Basis"].data.foreach_set("co", obj_coords - diff)
    obj.data.update()
