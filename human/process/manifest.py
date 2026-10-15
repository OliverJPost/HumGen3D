# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""The manifest next to an exported character, `<name>.humgen3d.json`.

The Companions for Unity, Unreal Engine and Godot only set up an imported file
when its manifest is next to it, so they never touch other characters and do
not depend on the naming scheme. The manifest says which file is the character,
which are its textures, and what every mesh and material is:

    {
        "humgen3d_export": 1,
        "generator": "Human Generator 3D 4.0.32",
        "name": "Jake",
        "recipe": "unity",
        "rig": "Jake",
        "files": {"character": "Jake.fbx", "animations": ["Jake@Run.fbx"]},
        "meshes": {"Jake_Body": {"part": "Body", "type": "body"}},
        "materials": {
            "Jake_Skin": {
                "part": "Skin",
                "type": "skin",
                "textures": {
                    "base_color": {"image": "Jake_Skin_BaseColor", "file": "Textures/Jake_Skin_BaseColor.png"}
                },
                "values": {"specular": 0.06}
            }
        },
        "settings": {...}
    }

Paths are relative to the manifest, with forward slashes. "file" is null for
a texture embedded in the character file. "values" are the inputs of the baked
material that are a plain value instead of a map ("roughness", "metallic",
"specular", on Blender's 0 to 1 scales): the eyes have no roughness map but a
roughness of 0.1, which an engine can't read from the character file. "settings"
is the `ExportSettings` the character was made with. `FORMAT` only goes up when
a Companion that reads the current format would misread the new one; new keys
don't change it.
"""

import json
import os
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import bpy
from HumGen3D.human.hair.compatibility import SPECULAR_INPUT_NAME

from .naming import HAIRCAP_PART, PART_KEY, SKIN_PART
from .settings import ExportSettings

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

FORMAT = 1
EXTENSION = ".humgen3d.json"
FORMAT_KEY = "humgen3d_export"
# Blender's number suffix, the file has the names without it, see naming.exact_names
_SUFFIX = re.compile(r"\.\d{3}$")
# Principled inputs listed under "values" when they are not linked to a map
VALUE_INPUTS = {
    "roughness": "Roughness",
    "metallic": "Metallic",
    "specular": SPECULAR_INPUT_NAME,
}
# What a part is, for the parts that are not clothing
PART_TYPES = {
    "Body": "body",
    SKIN_PART: "skin",
    "Eyes": "eyes",
    "EyesOuter": "eyes_outer",
    "EyesInner": "eyes_inner",
    "TeethUpper": "teeth",
    "TeethLower": "teeth",
    "Teeth": "teeth",
    HAIRCAP_PART: "haircap",
    "Hair": "haircap",
    "FaceHair": "face_haircap",
    "Eyebrows": "haircap",
    "Eyelashes": "haircap",
    "HairCards": "hair_cards",
    "FaceHairCards": "hair_cards",
    "EyebrowsCards": "hair_cards",
    "EyelashesCards": "hair_cards",
}


def manifest_path(character_file: str) -> str:
    """Path of the manifest of a character file: the file name without extension."""
    return os.path.splitext(character_file)[0] + EXTENSION


def part_type(part: str) -> str:
    """The type of a part name, "clothing" for the parts that are not listed."""
    return PART_TYPES.get(part, "clothing")


def build(
    human: "Human",
    settings: ExportSettings,
    name: str,
    character_file: str,
    animation_files: List[str],
) -> Dict[str, Any]:
    """The manifest of a written character, see the module docstring.

    Args:
        human (Human): The processed copy that was written, with its parts named.
        settings (ExportSettings): The settings it was made with.
        name (str): The name of the result.
        character_file (str): Path of the file with the meshes.
        animation_files (List[str]): Paths of the files with only clips.
    """
    from HumGen3D import bl_info

    folder = os.path.dirname(os.path.abspath(character_file))
    meshes: Dict[str, Any] = {}
    materials: Dict[str, Any] = {}
    for obj in human.objects:
        if obj.type != "MESH" or PART_KEY not in obj:
            continue
        part = str(obj[PART_KEY])
        meshes[_name(obj)] = {"part": part, "type": part_type(part)}
        for slot in obj.material_slots:
            material = slot.material
            if not material or _name(material) in materials:
                continue
            material_part = str(material.get(PART_KEY, part))
            materials[_name(material)] = {
                "part": material_part,
                "type": part_type(material_part),
                "textures": _textures(material, folder),
                "values": _values(material),
            }

    return {
        FORMAT_KEY: FORMAT,
        "generator": "Human Generator 3D " + ".".join(str(n) for n in bl_info["version"]),
        "name": name,
        "recipe": settings.recipe,
        "rig": _name(human.objects.rig),
        "files": {
            "character": _relative(character_file, folder),
            "animations": [_relative(path, folder) for path in animation_files],
        },
        "meshes": meshes,
        "materials": materials,
        "settings": settings.to_dict(),
    }


def write(
    human: "Human",
    settings: ExportSettings,
    name: str,
    character_file: str,
    animation_files: List[str],
) -> str:
    """Writes the manifest next to the character file, see `build`.

    Returns:
        str: The path of the manifest.
    """
    path = manifest_path(character_file)
    with open(path, "w") as f:
        json.dump(build(human, settings, name, character_file, animation_files), f, indent=2)
    return path


def _textures(material: bpy.types.Material, folder: str) -> Dict[str, Any]:
    """The images of a baked material by pass, the image nodes are named after it."""
    textures: Dict[str, Any] = {}
    if not material.node_tree:
        return textures
    for node in material.node_tree.nodes:
        image = getattr(node, "image", None)
        if node.type != "TEX_IMAGE" or image is None:
            continue
        image_name = _name(image)
        path = bpy.path.abspath(image.filepath_raw) if image.filepath_raw else ""
        inside = path and os.path.abspath(path).startswith(os.path.join(folder, ""))
        if not inside or not os.path.isfile(path) or image.packed_file:
            # Embedded, or the flow map written next to the file, see
            # textures.write_sidecar_images
            sidecar = os.path.join(folder, image_name + ".png")
            path = sidecar if os.path.isfile(sidecar) else ""
        textures[node.name] = {
            "image": image_name,
            "file": _relative(path, folder) if path else None,
        }
    return textures


def _values(material: bpy.types.Material) -> Dict[str, float]:
    """The Principled inputs of a baked material that are a plain value, see VALUE_INPUTS."""
    if not material.node_tree:
        return {}
    principled = next(
        (node for node in material.node_tree.nodes if node.bl_idname == "ShaderNodeBsdfPrincipled"),
        None,
    )
    if principled is None:
        return {}
    values = {}
    for key, input_name in VALUE_INPUTS.items():
        socket = principled.inputs.get(input_name)
        if socket is not None and not socket.is_linked:
            values[key] = round(float(socket.default_value), 4)  # type:ignore[arg-type]
    return values


def _name(datablock: bpy.types.ID) -> str:
    return _SUFFIX.sub("", datablock.name)


def _relative(path: str, folder: str) -> str:
    return os.path.relpath(os.path.abspath(path), folder).replace(os.sep, "/")


def read(path: str) -> Optional[Dict[str, Any]]:
    """The manifest at a path, None when it is missing or not a manifest."""
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and FORMAT_KEY in data else None
