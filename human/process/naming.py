# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Names of the objects, meshes, materials and textures of a processed human.

A processed human is a copy, so Blender gives its datablocks a number suffix
like "HG_Body.001". Engines show those names, so every datablock of the result
is named after the human and its part by a naming scheme instead: "Jake_Body",
"Jake_Skin", "Jake_Body_BaseColor" or, with the Unreal scheme, "SK_Jake_Body",
"M_Jake_Skin", "T_Jake_Body_BC".
"""

import re
from contextlib import contextmanager
from typing import TYPE_CHECKING, Dict, Iterator, List, Tuple

import bpy

from .settings import OutputSettings

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

# Templates of each scheme, see OutputSettings.naming_templates for the custom one
SCHEMES = {
    "plain": {
        "rig": "{name}",
        "mesh": "{name}_{part}",
        "material": "{name}_{part}",
        "texture": "{name}_{part}_{pass}",
    },
    "unreal": {
        "rig": "SK_{name}",
        "mesh": "SK_{name}_{part}",
        "material": "M_{name}_{part}",
        "texture": "T_{name}_{part}_{pass}",
    },
}
# What the passes are called in texture names, the Unreal style guide abbreviates
PASS_NAMES = {
    "plain": {
        "base_color": "BaseColor",
        "normal": "Normal",
        "roughness": "Roughness",
        "metallic": "Metallic",
        "alpha": "Alpha",
        "orm": "ORM",
        "metallic_roughness": "MetallicRoughness",
        "metallic_smoothness": "MetallicSmoothness",
    },
    "unreal": {
        "base_color": "BC",
        "normal": "N",
        "roughness": "R",
        "metallic": "M",
        "alpha": "A",
        "orm": "ORM",
        "metallic_roughness": "MR",
        "metallic_smoothness": "MS",
    },
}
# Part names of the haircard objects, by the tag of their hair type
HAIR_PARTS = {
    "hg_main_hair": "Hair",
    "hg_face_hair": "FaceHair",
    "hg_eyebrows": "Eyebrows",
    "hg_eyelashes": "Eyelashes",
}
# The caps of these hair types are cut from one atlas and don't overlap in UV
# space, so they are one material and one texture set. The beard cap has an
# atlas of its own.
SHARED_CAP_TAGS = ("hg_main_hair", "hg_eyebrows", "hg_eyelashes")
HAIRCAP_PART = "Haircap"
SKIN_PART = "Skin"
TEMP_SUFFIX = ".hg_tmp"


class Namer:
    """Names for one processed human, see the module docstring.

    Args:
        output (OutputSettings): Scheme and templates.
        name (str): Name of the human, the "{name}" token.
        level (int): LOD level of the human, added as "_LOD1" suffix to the
            meshes when there is more than one level.
        levels (int): Number of LOD levels.
    """

    def __init__(
        self, output: OutputSettings, name: str, level: int = 0, levels: int = 1
    ) -> None:
        self.name = clean(name)
        self.scheme = output.naming
        if self.scheme == "custom":
            self.templates = dict(SCHEMES["plain"], **output.naming_templates)
        else:
            self.templates = SCHEMES.get(self.scheme, SCHEMES["plain"])
        self.pass_names = PASS_NAMES.get(self.scheme, PASS_NAMES["plain"])
        self.level = level
        self.lod_suffix = f"_LOD{level}" if levels > 1 else ""
        # Materials and textures of the first level are shared by the other
        # levels, those the other levels have of their own get the suffix too
        self.level_suffix = self.lod_suffix if level > 0 else ""

    def rig(self) -> str:
        """Name of the armature object and its data."""
        return self._fill("rig")

    def mesh(self, part: str) -> str:
        """Name of a mesh object and its data."""
        return self._fill("mesh", part) + self.lod_suffix

    def material(self, part: str, per_level: bool = False) -> str:
        """Name of a material, per_level for one this level has of its own."""
        return self._fill("material", part) + (self.level_suffix if per_level else "")

    def texture(self, part: str, pass_id: str, per_level: bool = False) -> str:
        """Name of an image and its file, without extension."""
        pass_name = self.pass_names.get(pass_id, pass_id)
        return self._fill("texture", part, pass_name) + (self.level_suffix if per_level else "")

    def _fill(self, kind: str, part: str = "", pass_name: str = "") -> str:
        template = self.templates[kind]
        return clean(
            template.replace("{name}", self.name)
            .replace("{part}", part)
            .replace("{pass}", pass_name)
        )


def clean(text: str) -> str:
    """A name without the number suffix of Blender, spaces or odd characters."""
    text = re.sub(r"\.\d{3}$", "", text.strip())
    text = re.sub(r"[^\w\-]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def part_names(human: "Human") -> Dict[bpy.types.Object, str]:
    """The part name of every mesh object of the human, "Body", "Eyes", "Hair"..."""
    objects = human.objects
    parts = {
        objects.body: "Body",
        objects.eyes: "Eyes",
        objects.upper_teeth: "TeethUpper",
        objects.lower_teeth: "TeethLower",
    }
    for hair_obj in objects.haircards:
        tag = next((tag for tag in HAIR_PARTS if tag in hair_obj), None)
        parts[hair_obj] = HAIR_PARTS.get(tag, "Hair")  # type:ignore[arg-type]
    for cloth_obj in human.clothing.outfit.objects + human.clothing.footwear.objects:
        parts[cloth_obj] = clean(cloth_obj.name.replace("HG_", "", 1))
    return parts


def material_part(human: "Human", obj: bpy.types.Object, slot: int, part: str) -> str:
    """Part name of the material in a slot.

    Materials shared by parts get one name: the teeth share theirs, the hair,
    eyebrows and eyelashes share their cap. The skin, the layers of the eyes
    and the hair cards get names of their own.
    """
    objects = human.objects
    if obj == objects.body and slot == 0:
        return SKIN_PART
    if obj == objects.eyes and len(obj.material_slots) > 1:
        return "EyesOuter" if slot == 0 else "EyesInner"
    if "hg_teeth" in obj:
        return "Teeth"
    if "hg_haircard" in obj:
        if slot == 1:
            return part + "Cards"
        if is_shared_cap(obj):
            return HAIRCAP_PART
    return part


def is_shared_cap(obj: bpy.types.Object) -> bool:
    """Whether the cap of a haircard object is part of the shared cap atlas."""
    return any(tag in obj for tag in SHARED_CAP_TAGS)


def apply_names(human: "Human", namer: Namer) -> None:
    """Names the datablocks of the human by the scheme.

    Objects and their meshes, the armature, the materials in use and the
    images of the baked materials. Unused material slots are removed first, so
    the particle hair materials do not end up in the file.
    """
    rig = human.objects.rig
    _set_name(rig, namer.rig())
    _set_name(rig.data, namer.rig())
    for obj, part in part_names(human).items():
        _set_name(obj, namer.mesh(part))
        _set_name(obj.data, namer.mesh(part))
        _remove_unused_slots(obj)
        # The eyes and hair cards of a level have materials of their own, see
        # textures.share_textures
        per_level = obj == human.objects.eyes or "hg_haircard" in obj
        for slot_index, slot in enumerate(obj.material_slots):
            material = slot.material
            if not material:
                continue
            _set_name(
                material,
                namer.material(material_part(human, obj, slot_index, part), per_level),
            )


def _set_name(datablock: bpy.types.ID, name: str) -> None:
    if datablock.name != name:
        datablock.name = name


def _remove_unused_slots(obj: bpy.types.Object) -> None:
    mesh = obj.data
    if not mesh.materials or len(mesh.materials) == 1:
        return
    used = {polygon.material_index for polygon in mesh.polygons}
    for index in reversed(range(len(mesh.materials))):
        if index not in used and len(mesh.materials) > 1:
            mesh.materials.pop(index=index)


def datablocks(human: "Human") -> List[bpy.types.ID]:
    """Every object, mesh, armature, material and image of the human."""
    ids: List[bpy.types.ID] = []
    for obj in human.objects:
        ids.append(obj)
        ids.append(obj.data)
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            material = slot.material
            if not material or material in ids:
                continue
            ids.append(material)
            if material.node_tree:
                for node in material.node_tree.nodes:
                    image = getattr(node, "image", None)
                    if image and image not in ids:
                        ids.append(image)
    return ids


@contextmanager
def exact_names(ids: List[bpy.types.ID]) -> Iterator[None]:
    """Gives the datablocks the names they have without the number suffix, briefly.

    Blender keeps names unique, so a second export of the same human would write
    "Jake_Body.001" when "Jake_Body" is still in the file. For the duration of
    the block the other holder of each name is renamed out of the way, afterwards
    both get their names back.
    """
    swapped: List[Tuple[bpy.types.ID, bpy.types.ID, str, str]] = []
    try:
        for datablock in ids:
            wanted = re.sub(r"\.\d{3}$", "", datablock.name)
            if wanted == datablock.name:
                continue
            collection = _collection_of(datablock)
            other = collection.get(wanted) if collection else None
            if other is None or other == datablock:
                continue
            ours = datablock.name
            other.name = wanted + TEMP_SUFFIX
            datablock.name = wanted
            swapped.append((datablock, other, ours, wanted))
        yield
    finally:
        for datablock, other, ours, wanted in reversed(swapped):
            datablock.name = ours
            other.name = wanted


def _collection_of(datablock: bpy.types.ID):  # noqa: ANN202
    if isinstance(datablock, bpy.types.Object):
        return bpy.data.objects
    if isinstance(datablock, bpy.types.Mesh):
        return bpy.data.meshes
    if isinstance(datablock, bpy.types.Armature):
        return bpy.data.armatures
    if isinstance(datablock, bpy.types.Material):
        return bpy.data.materials
    if isinstance(datablock, bpy.types.Image):
        return bpy.data.images
    if isinstance(datablock, bpy.types.Action):
        return bpy.data.actions
    return None
