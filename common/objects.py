from typing import Union

import bpy

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
