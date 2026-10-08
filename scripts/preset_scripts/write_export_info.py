"""Writes a JSON file next to the exported files with the name, bones and
triangle count of the character, for a pipeline that reads it."""

import json
import os

import bpy
from HumGen3D import Human

STAGE = "after_export"


def main(context: bpy.types.Context, human: Human, files: list, file_name: str = "export_info"):
    """Runs after the export, the stage it is added with.

    Args:
        context (bpy.types.Context): Blender context.
        human (Human): The processed copy that was written.
        files (list): Paths of the files that were written.
        file_name (str): Name of the JSON file, without extension.
    """
    if not files:
        print("Nothing was exported, no export info written")
        return
    info = {
        "name": human.name,
        "files": [os.path.basename(path) for path in files],
        "bones": [bone.name for bone in human.objects.rig.data.bones],
        "triangles": sum(
            len(obj.data.loops) - 2 * len(obj.data.polygons)
            for obj in human.objects
            if obj.type == "MESH"
        ),
    }
    path = os.path.join(os.path.dirname(files[0]), file_name + ".json")
    with open(path, "w") as f:
        json.dump(info, f, indent=4)
