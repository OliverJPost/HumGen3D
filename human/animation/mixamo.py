# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Converts Mixamo animations to Human Generator clips.

Mixamo characters are rigged in a T-pose with the palms down and the feet flat,
which is the reference pose of the clip format (see clip.py). Baking the rotation
of every bone relative to its rest rotation, in world space, therefore gives a
clip that retarget.py can apply like the ones of the library. Only the names of
the bones differ, these are mapped to the bones of the Human Generator rig.

The FBX file is imported into the current file to read the animation and removed
again afterwards, nothing of it is kept.
"""

import os
import re
from typing import Dict, List, Optional

import bpy
from HumGen3D.common.exceptions import HumGenException
from mathutils import Vector

from .clip import FORMAT_VERSION, LEG_BONES, ROOT_BONE

# Mixamo bone names, without the "mixamorig:" prefix, to Human Generator bone names.
# Human Generator has one spine bone more, the retargeting spreads the bend of the
# chest evenly over the chain. The end bones of Mixamo (HeadTop_End, Thumb4,
# Toe_End) have no rotation of their own and are not mapped.
BONE_NAME_MAP = {
    "Hips": ROOT_BONE,
    "Spine": "spine.001",
    "Spine1": "spine.002",
    "Spine2": "spine.003",
    "Neck": "neck",
    "Head": "head",
}
for _side, _suffix in (("Left", ".L"), ("Right", ".R")):
    BONE_NAME_MAP.update(
        {
            f"{_side}Shoulder": f"shoulder{_suffix}",
            f"{_side}Arm": f"upper_arm{_suffix}",
            f"{_side}ForeArm": f"forearm{_suffix}",
            f"{_side}Hand": f"hand{_suffix}",
            f"{_side}UpLeg": f"thigh{_suffix}",
            f"{_side}Leg": f"shin{_suffix}",
            f"{_side}Foot": f"foot{_suffix}",
            f"{_side}ToeBase": f"toe{_suffix}",
        }
    )
    for _mixamo_finger, _hg_finger in (
        ("Thumb", "thumb"),
        ("Index", "f_index"),
        ("Middle", "f_middle"),
        ("Ring", "f_ring"),
        ("Pinky", "f_pinky"),
    ):
        for _i in (1, 2, 3):
            BONE_NAME_MAP[f"{_side}Hand{_mixamo_finger}{_i}"] = (
                f"{_hg_finger}.0{_i}{_suffix}"
            )

# Bones every Mixamo rig has, used to recognize one
REQUIRED_BONES = ("Hips", "Spine2", "LeftUpLeg", "RightArm")
# Mixamo prefixes its bones with "mixamorig:", sometimes numbered, like "mixamorig1:"
PREFIX_PATTERN = re.compile(r"^mixamorig\d*[:_]")

# Datablock collections the FBX importer adds to, cleaned up after the import
IMPORTED_DATA = (
    "objects",
    "armatures",
    "meshes",
    "materials",
    "images",
    "actions",
    "cameras",
    "lights",
)


def mixamo_bone_name(name: str) -> str:
    """Name of a Mixamo bone without the rig prefix."""
    return PREFIX_PATTERN.sub("", name)


def fbx_to_clip(
    filepath: str, context: bpy.types.Context, loop: bool = False
) -> Dict:
    """Imports a Mixamo FBX file and converts its animation to a clip.

    Args:
        filepath (str): Path of the FBX file downloaded from Mixamo, with or
            without skin.
        context (Context): Context to import in.
        loop (bool): Mark the clip as cyclic. Defaults to False.

    Returns:
        dict: Clip in the layout of clip.py.

    Raises:
        HumGenException: If the file could not be imported, does not contain a
            Mixamo rig or has no animation.
    """
    scene = context.scene
    scene_state = _SceneState(scene)
    before = {name: set(getattr(bpy.data, name)) for name in IMPORTED_DATA}
    try:
        _import_fbx(filepath)
        rigs = [
            obj
            for obj in bpy.data.objects
            if obj not in before["objects"] and obj.type == "ARMATURE"
        ]
        rig = next((r for r in rigs if _is_mixamo_rig(r)), None)
        if not rig:
            raise HumGenException(
                f"{os.path.basename(filepath)} does not contain a Mixamo rig."
            )
        if not rig.animation_data or not rig.animation_data.action:
            raise HumGenException(f"{os.path.basename(filepath)} has no animation.")

        clip = _bake_clip(rig, scene, filepath, loop)
    finally:
        _remove_imported(before)
        scene_state.restore(scene)

    return clip


def _import_fbx(filepath: str) -> None:
    """Imports the FBX with the importer available in this Blender version."""
    if "fbx_import" in dir(bpy.ops.wm):
        result = bpy.ops.wm.fbx_import(filepath=filepath)
    else:
        result = bpy.ops.import_scene.fbx(filepath=filepath)
    if "FINISHED" not in result:
        raise HumGenException(f"Could not import {os.path.basename(filepath)}.")


def _is_mixamo_rig(rig: bpy.types.Object) -> bool:
    names = {mixamo_bone_name(bone.name) for bone in rig.data.bones}
    return all(name in names for name in REQUIRED_BONES)


def _bake_clip(
    rig: bpy.types.Object, scene: bpy.types.Scene, filepath: str, loop: bool
) -> Dict:
    """Samples the rotations of the mapped bones per frame, in world space.

    World space is used because the FBX importer leaves the rig scaled and
    rotated as object, which puts it upright and in meters like a human.
    """
    pose_bones = {
        BONE_NAME_MAP[name]: pose_bone
        for pose_bone in rig.pose.bones
        for name in (mixamo_bone_name(pose_bone.name),)
        if name in BONE_NAME_MAP
    }
    world = rig.matrix_world
    rest_matrices = {
        name: world @ pose_bone.bone.matrix_local
        for name, pose_bone in pose_bones.items()
    }
    rest_rotations = {
        name: matrix.to_3x3().normalized().inverted()
        for name, matrix in rest_matrices.items()
    }
    root_rest_location = rest_matrices[ROOT_BONE].translation

    rotations: Dict[str, List] = {name: [] for name in pose_bones}
    root_locations: List[Vector] = []
    action = rig.animation_data.action
    frame_start, frame_end = (int(round(f)) for f in action.frame_range)
    for frame in range(frame_start, frame_end + 1):
        scene.frame_set(frame)
        world = rig.matrix_world
        for name, pose_bone in pose_bones.items():
            matrix = world @ pose_bone.matrix
            delta = matrix.to_3x3().normalized() @ rest_rotations[name]
            rotations[name].append(delta.to_quaternion())
        root_locations.append(
            (world @ pose_bones[ROOT_BONE].matrix).translation - root_rest_location
        )

    # Bone vectors in world space, so in meters like the rest of the clip
    bone_vectors = {
        name: world.to_3x3() @ (pb.bone.tail_local - pb.bone.head_local)
        for name, pb in pose_bones.items()
    }
    leg_length = sum(bone_vectors[f"{name}.L"].length for name in LEG_BONES)
    reference_directions = {
        name: vector.normalized() for name, vector in bone_vectors.items()
    }
    return {
        "format_version": FORMAT_VERSION,
        "source": f"Mixamo, {os.path.basename(filepath)}",
        "license": "Adobe Mixamo",
        "fps": scene.render.fps / scene.render.fps_base,
        "frame_count": frame_end - frame_start + 1,
        "loop": loop,
        "root_motion": _has_root_motion(root_locations),
        "reference_leg_length": leg_length,
        "reference_directions": reference_directions,
        "rotations": rotations,
        "root_location": root_locations,
    }


def _has_root_motion(root_locations: List[Vector], threshold: float = 0.3) -> bool:
    """True if the hips travel horizontally, i.e. not an 'In Place' animation."""
    first, last = root_locations[0], root_locations[-1]
    return (Vector((last.x, last.y)) - Vector((first.x, first.y))).length > threshold


def _remove_imported(before: Dict[str, set]) -> None:
    """Removes everything the FBX import added to the file."""
    for name in IMPORTED_DATA:
        collection = getattr(bpy.data, name)
        for block in [b for b in collection if b not in before[name]]:
            collection.remove(block)


class _SceneState:
    """Frame range, fps and selection of the scene, restored after importing."""

    def __init__(self, scene: bpy.types.Scene) -> None:
        self.frame_start = scene.frame_start
        self.frame_end = scene.frame_end
        self.frame_current = scene.frame_current
        self.fps = scene.render.fps
        self.fps_base = scene.render.fps_base
        view_layer = bpy.context.view_layer
        self.active: Optional[bpy.types.Object] = view_layer.objects.active
        self.selected = [obj for obj in view_layer.objects if obj.select_get()]

    def restore(self, scene: bpy.types.Scene) -> None:
        scene.frame_start = self.frame_start
        scene.frame_end = self.frame_end
        scene.render.fps = self.fps
        scene.render.fps_base = self.fps_base
        scene.frame_set(self.frame_current)
        view_layer = bpy.context.view_layer
        for obj in view_layer.objects:
            obj.select_set(False)
        for obj in self.selected:
            try:
                obj.select_set(True)
            except ReferenceError:
                pass
        try:
            view_layer.objects.active = self.active
        except ReferenceError:
            pass
