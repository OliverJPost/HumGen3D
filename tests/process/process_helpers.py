# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Shared tools of the tests of the process system.

Making a source human, cheap settings, a snapshot of a human to prove the
source is not changed, counting datablocks to find leaks, and reading the
written files back: FBX, glTF, OBJ and Alembic are imported into the file and
removed again, glb and glTF are also read with pygltflib.
"""

import os
import re
import struct
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Dict, Iterator, List, Optional

import bpy
import numpy as np
from HumGen3D.common.object_finding import HUMAN_ID_KEY
from HumGen3D.human.human import Human
from HumGen3D.human.process.animations import rig_actions
from HumGen3D.human.process.settings import ExportSettings
from HumGen3D.tests.test_fixtures import _create_human

# Small textures keep a bake at a few seconds
TEST_RESOLUTION = 128
# The datablock collections a run may add to and must clean up
DATA_COLLECTIONS = (
    "objects",
    "meshes",
    "armatures",
    "materials",
    "images",
    "actions",
    "node_groups",
    "particles",
    "textures",
)
SUFFIX = re.compile(r"\.\d{3}$")

__all__ = [
    "TEST_RESOLUTION",
    "SUFFIX",
    "make_source_human",
    "cheap_settings",
    "snapshot",
    "datablock_counts",
    "imported",
    "gltf_document",
    "fbx_unit_scale",
    "bone_influences",
    "world_height",
    "arm_angle",
    "action_paths",
    "image_pixels",
    "files_in",
    "select_only",
    "write_script",
    "tris",
]


HAIRSTYLE = "Short Side Part"
BEARD = "Full_Beard_1"


def make_source_human(
    gender: str = "male", outfit: bool = True, clips: int = 2, hair: bool = True
) -> Human:
    """A human as a user would process it: clothing, particle hair and clips.

    A male human gets scalp hair and a beard, so every hair type becomes hair
    cards. The first clip ends up as NLA strip next to the others, as
    `animation.set` with `as_strip` pushes the active one down.
    """
    context = bpy.context
    human = _create_human(gender)
    if hair and gender == "male":
        for settings, style in ((human.hair.regular_hair, HAIRSTYLE), (human.hair.face_hair, BEARD)):
            options = settings.get_options(context)
            settings.set(next(option for option in options if style in option), context)
    if outfit:
        options = human.clothing.outfit.get_options(context=context)
        human.clothing.outfit.set(options[0], context)
    if clips:
        options = human.animation.get_options(context=context)
        human.animation.set(options[0], context)
        for preset in options[1:clips]:
            human.animation.set(preset, context, as_strip=True)
    return human


def cheap_settings(recipe: str, folder: Optional[str] = None, **overrides: Any) -> ExportSettings:
    """The settings of a recipe with tiny textures, overrides as "section.field".

    Args:
        recipe (str): Identifier of a shipped recipe.
        folder (Optional[str]): Output folder, never the content folder.
        overrides: Dotted paths with their values, "output.format" = "glb".
    """
    settings = ExportSettings.from_recipe(recipe)
    settings.textures.resolution = {key: TEST_RESOLUTION for key in settings.textures.resolution}
    if folder is not None:
        settings.output.folder = str(folder)
    for path, value in overrides.items():
        *parents, name = path.split(".")
        target = settings
        for parent in parents:
            target = getattr(target, parent)
        setattr(target, name, value)
    return settings


def snapshot(human: Human) -> Dict[str, Any]:
    """Everything a run could change on the source human."""
    rig = human.objects.rig
    meshes = [obj for obj in human.objects if obj.type == "MESH"]
    return {
        "objects": sorted(obj.name for obj in human.objects),
        "bones": sorted(bone.name for bone in rig.data.bones),
        "rest": [tuple(round(v, 5) for v in bone.head_local) for bone in rig.data.bones],
        "keys": {
            obj.name: [key.name for key in obj.data.shape_keys.key_blocks]
            if obj.data.shape_keys
            else []
            for obj in meshes
        },
        "materials": {
            obj.name: [slot.material.name if slot.material else None for slot in obj.material_slots]
            for obj in meshes
        },
        "modifiers": {obj.name: [mod.type for mod in obj.modifiers] for obj in meshes},
        "vertices": {obj.name: len(obj.data.vertices) for obj in meshes},
        "hair_modifiers": len(human.hair.modifiers),
        "rig_properties": sorted(key for key in rig.keys() if key != HUMAN_ID_KEY),
        "actions": [action.name for action in rig_actions(human)],
        "location": tuple(round(v, 5) for v in human.location),
        "skin_nodes": len(human.objects.body.material_slots[0].material.node_tree.nodes),
    }


def datablock_counts() -> Dict[str, int]:
    return {name: len(getattr(bpy.data, name)) for name in DATA_COLLECTIONS}


def tris(obj: bpy.types.Object) -> int:
    return len(obj.data.loops) - 2 * len(obj.data.polygons)


@contextmanager
def imported(path: str) -> Iterator[SimpleNamespace]:
    """Imports a written file and yields what it added, removed afterwards.

    Yields:
        SimpleNamespace: `objects`, `armatures` (objects), `meshes` (objects),
            `materials`, `images` and `actions` that the import added.
    """
    before = {name: set(getattr(bpy.data, name)) for name in DATA_COLLECTIONS}
    # Datablocks with the names of the file would make the importer add a
    # suffix, so the names in the scene are moved aside during the import
    renamed = []
    for name in ("objects", "meshes", "armatures", "materials", "images", "actions"):
        # A list first, renaming sorts the collection anew
        for index, block in enumerate(list(getattr(bpy.data, name))):
            renamed.append((block, block.name))
            block.name = f"~hgtest{index}"
    extension = os.path.splitext(path)[1].lower()
    if extension == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif extension in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif extension == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif extension == ".abc":
        bpy.ops.wm.alembic_import(filepath=path, as_background_job=False)
    else:
        raise ValueError(f"Can't import {path}")
    new = {
        name: [block for block in getattr(bpy.data, name) if block not in before[name]]
        for name in DATA_COLLECTIONS
    }
    result = SimpleNamespace(
        objects=new["objects"],
        armatures=[obj for obj in new["objects"] if obj.type == "ARMATURE"],
        meshes=[obj for obj in new["objects"] if obj.type == "MESH"],
        materials=new["materials"],
        images=new["images"],
        actions=new["actions"],
    )
    try:
        yield result
    finally:
        removable = [block for blocks in new.values() for block in blocks]
        bpy.data.batch_remove(removable)
        for block, name in renamed:
            block.name = name
        # The view layer lists removed objects as None until it is updated
        bpy.context.view_layer.update()


def gltf_document(path: str) -> Any:
    """The glTF of a .glb or .gltf file, read without Blender."""
    from pygltflib import GLTF2

    return GLTF2().load(path)


def fbx_unit_scale(path: str) -> float:
    """The UnitScaleFactor of a binary FBX file, 1.0 for meters, 100.0 for cm.

    The property is a record of the strings name, type, label and flags,
    followed by its value as double.
    """
    with open(path, "rb") as f:
        data = f.read()
    index = data.index(b"UnitScaleFactor") + len(b"UnitScaleFactor")
    for _ in range(3):
        assert data[index : index + 1] == b"S"
        length = struct.unpack("<I", data[index + 1 : index + 5])[0]
        index += 5 + length
    assert data[index : index + 1] == b"D"
    return float(struct.unpack("<d", data[index + 1 : index + 9])[0])


def bone_influences(obj: bpy.types.Object, armature: bpy.types.Object) -> int:
    """The most bones that deform one vertex of a mesh, weights above zero."""
    bones = {bone.name for bone in armature.data.bones}
    names = {group.index: group.name for group in obj.vertex_groups}
    most = 0
    for vertex in obj.data.vertices:
        count = sum(
            1 for group in vertex.groups if group.weight > 1e-6 and names.get(group.group) in bones
        )
        most = max(most, count)
    return most


def world_height(objects: List[bpy.types.Object]) -> float:
    """Height of the bounding box of the objects in world space."""
    from mathutils import Vector

    zs = [
        (obj.matrix_world @ Vector(corner)).z
        for obj in objects
        for corner in obj.bound_box
    ]
    return max(zs) - min(zs)


def arm_angle(armature: bpy.types.Object, upper_arm: str, forearm: str) -> float:
    """Angle in degrees of the rest pose upper arm below the horizontal.

    From the head of the upper arm to the head of the forearm, as importers
    may change the bone tails.
    """
    import math

    bones = armature.data.bones
    matrix = armature.matrix_world
    start = matrix @ bones[upper_arm].head_local
    end = matrix @ bones[forearm].head_local
    vector = end - start
    return math.degrees(math.asin(abs(vector.z) / vector.length))


def action_paths(action: bpy.types.Action) -> set:
    """The animated data paths of an action, slotted (4.4+) or not."""
    paths = set()
    if hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    paths.update(fcurve.data_path for fcurve in bag.fcurves)
    else:
        paths.update(fcurve.data_path for fcurve in action.fcurves)
    return paths


def image_pixels(path: str) -> np.ndarray:
    """RGBA pixels of an image file as (pixels, 4) floats."""
    image = bpy.data.images.load(path, check_existing=False)
    try:
        pixels = np.empty(len(image.pixels), dtype=np.float32)
        image.pixels.foreach_get(pixels)
        return pixels.reshape(-1, 4)
    finally:
        bpy.data.images.remove(image)


def files_in(folder: str) -> List[str]:
    """Every file below a folder, relative to it."""
    found = []
    for root, _, files in os.walk(folder):
        for file in files:
            found.append(os.path.relpath(os.path.join(root, file), folder))
    return sorted(found)


def select_only(context: bpy.types.Context, *humans: Human) -> None:
    """Selects the rigs of the humans, the first active, as a user does."""
    for obj in context.selected_objects:
        obj.select_set(False)
    for human in humans:
        human.objects.rig.select_set(True)
    context.view_layer.objects.active = humans[0].objects.rig if humans else None


def write_script(folder: str, name: str, body: str) -> str:
    """Writes a process script and returns its path."""
    path = os.path.join(str(folder), name + ".py")
    with open(path, "w") as f:
        f.write(body)
    return path
