# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Converts recipes saved by older versions to the current settings schema.

Version 1 recipes were a dict per section with the Blender properties of that
section, present when the section was enabled. The bone and object renaming
sections of that version have no equivalent and are dropped with a warning.
"""

import os
from typing import Any, Dict

from HumGen3D.backend.logging import hg_log
from HumGen3D.backend.preferences.preference_func import get_addon_root, get_prefs

from .settings import SCHEMA_VERSION

# Decimate ratios of the clothing options of version 1
_CLOTHING_RATIOS = {"original": 1.0, "high": 0.5, "medium": 0.25, "low": 0.1}
_GAME_RIG_NAMES = {
    "generic_a": "humgen",
    "generic_t": "humgen",
    "humanoid": "humanoid",
    "unreal": "unreal",
    "mixamo": "mixamo",
}


def migrate_v1(data: Dict[str, Any]) -> Dict[str, Any]:  # noqa: CCR001
    """Settings dict of the current version from a version 1 recipe dict."""
    main = data.get("main", {})
    new: Dict[str, Any] = {"version": SCHEMA_VERSION}

    output: Dict[str, Any] = {}
    if main.get("output_type") == "export":
        file_type = main.get("export_file_type", "fbx").lstrip(".").lower()
        output["format"] = {
            "obj": "obj",
            "fbx": "fbx",
            "abc": "abc",
            "glb": "glb",
            "gltf embedded": "glb",
            "gltf separate": "gltf",
        }.get(file_type, "fbx")
    else:
        output["format"] = "in_file"
    new["output"] = output

    quality: Dict[str, Any] = {}
    lod = data.get("lod")
    if lod:
        quality["body"] = int(lod.get("body_lod", 0))
        if "decimate_ratio" in lod:
            ratio = lod["decimate_ratio"]
            quality["clothing"] = min(
                _CLOTHING_RATIOS, key=lambda opt: abs(_CLOTHING_RATIOS[opt] - ratio)
            )
        else:
            quality["clothing"] = lod.get("clothing", "medium")
        quality["eyes"] = lod.get("eyes", "original")
        quality["teeth"] = int(lod.get("teeth", 0))
        new["meshes"] = {
            "remove_clothing_subdiv": lod.get("remove_clothing_subdiv", True),
            "remove_clothing_solidify": lod.get("remove_clothing_solidify", True),
        }
    else:
        quality.update({"body": 0, "clothing": "original", "eyes": "original", "teeth": 0})

    haircards = data.get("haircards")
    new["haircards"] = {"enabled": bool(haircards)}
    quality["haircards"] = (haircards or {}).get("quality", "high")

    game_rig = data.get("game_rig")
    # Older recipes had the T-pose as a category of its own or as a main setting
    t_pose = "rest_pose" in data or main.get("rest_pose") == "t_pose"
    if game_rig:
        preset = game_rig.get("preset", "generic_a")
        new["skeleton"] = {
            "enabled": True,
            "names": _GAME_RIG_NAMES.get(preset, "humgen"),
            "rest_pose": game_rig.get("rest_pose", "t_pose" if t_pose else "a_pose"),
            "root_bone": game_rig.get("add_root_bone", True),
            "root_bone_name": game_rig.get("root_bone_name", "root"),
            "keep_eyes": game_rig.get("keep_eyes", True),
            "keep_jaw": game_rig.get("keep_jaw", True),
            "keep_breasts": game_rig.get("keep_breasts", True),
            "keep_metacarpals": game_rig.get("keep_metacarpals", False),
            "units": game_rig.get("units", "meters"),
        }
        quality["bones_per_vertex"] = int(game_rig.get("max_influences", 4))
    else:
        new["skeleton"] = {
            "enabled": t_pose,
            "names": "humgen",
            "rest_pose": "t_pose" if t_pose else "a_pose",
        }
        quality["bones_per_vertex"] = 0
    new["lods"] = [quality]

    shape_keys = data.get("shapekeys")
    if shape_keys:
        new["shape_keys"] = {
            key: shape_keys[key]
            for key in ("face_rig", "expressions", "correctives", "body", "face", "age")
            if key in shape_keys
        }

    baking = data.get("baking")
    textures: Dict[str, Any] = {"enabled": bool(baking)}
    if baking:
        textures["resolution"] = {
            "body": int(baking.get("res_body", 1024)),
            "clothing": int(baking.get("res_clothes", 1024)),
            "eyes": int(baking.get("res_eyes", 512)),
            "teeth": int(baking.get("res_teeth", 256)),
            "hair": int(baking.get("res_haircards", 512)),
        }
        textures["samples"] = int(baking.get("samples", 4))
        textures["pack_hair_alpha"] = baking.get("pack_haircard_alpha", True)
        if baking.get("export_folder"):
            output["folder"] = baking["export_folder"]
    file_type = main.get("bake_file_type", (baking or {}).get("file_type", "png"))
    textures["file_format"] = "jpeg" if file_type == "jpeg" else "png"
    new["textures"] = textures

    modapply = data.get("modapply")
    if modapply:
        enabled_items = modapply.get("enabled_items", [])
        new.setdefault("meshes", {})["remove_hidden_skin"] = (
            "MASK" in enabled_items or not enabled_items
        )

    scripts = []
    for name in data.get("scripting", {}):
        path = _find_script(name)
        if path:
            scripts.append({"path": path, "stage": "after_processing"})
        else:
            hg_log(f"Script '{name}' of the recipe was not found", level="WARNING")
    new["scripts"] = {"enabled": bool(scripts), "items": scripts}

    for dropped in ("rig_renaming", "renaming", "material_renaming"):
        if dropped in data:
            hg_log(
                f"The '{dropped}' section of this recipe is no longer supported, the"
                " names follow the naming scheme of the output now",
                level="WARNING",
            )
    return new


def _find_script(name: str) -> str:
    """Path of a script by file name, in the content folder or the shipped ones."""
    for folder in (
        os.path.join(get_prefs().filepath, "scripts"),
        os.path.join(get_addon_root(), "scripts", "preset_scripts"),
    ):
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            return path
    return ""
