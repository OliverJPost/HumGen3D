# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Converts the Quaternius Universal Animation Library to Human Generator clips.

Run headless on the library file, for example:

    blender -b AnimationLibrary.blend --python convert_animation_library.py -- \
        /path/to/HumGen/Content/animations

Every action is baked to the deform bones of the Rigify rig and written as a clip
json, see HumGen3D/human/animation/clip.py for the format. The clips are stored in
category folders, named after the animation.
"""

import json
import os
import re
import sys

import bpy
from mathutils import Matrix

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from human.animation.clip import (  # noqa: E402
    FORMAT_VERSION,
    ROOT_BONE,
    write_clip,
)

SOURCE_RIG = "Rig"
# Rigify deform bones are named after the metarig bones, which are the same as the
# bones of the HumGen rig. Only the hips have a different name.
BONE_NAME_MAP = {"DEF-hips": ROOT_BONE}
SKIP_ACTIONS = ("A_Tpose",)

CATEGORIES = {
    "Idle": ("Idle_", "Turn90_"),
    "Walking": ("Walk_",),
    "Running": ("Jog_", "Sprint_"),
    "Crouching": ("Crouch_",),
    "Crawling": ("Crawl_",),
    "Climbing": ("Climb",),
    "Sitting": ("Sitting_", "GroundSit_", "Driving_"),
    "Jumping": ("Jump_", "BackFlip", "Roll", "Dodge_"),
    "Swimming": ("Swim_",),
    "Fighting": ("Punch", "Kick", "Hit_", "Death"),
    "Weapons": ("Sword_", "Pistol_"),
    "Magic": ("Spell_",),
    "Interaction": ("Counter_", "Drink", "Interact", "PickUp_", "Push_", "Fixing_"),
    "Emotes": ("Celebration", "Crying", "Dance_"),
}

WORD_REPLACEMENTS = {
    "Fwd": "Forward",
    "Bwd": "Backward",
    "L": "Left",
    "R": "Right",
    "RM": "Root_Motion",
    "LeanL": "Lean_Left",
    "LeanR": "Lean_Right",
    "Idle02": "Idle_2",
    "Idle03": "Idle_3",
    "Death01": "Death_1",
    "Death02": "Death_2",
    "Turn90": "Turn_90",
    "ClimbLedge": "Climb_Ledge",
    "GroundSit": "Ground_Sit",
    "PunchKick": "Punch_Kick",
    "PickUp": "Pick_Up",
    "BackFlip": "Backflip",
}


def category_of(action_name: str) -> str:
    for category, prefixes in CATEGORIES.items():
        if action_name.startswith(prefixes):
            return category
    return "Other"


def file_name_of(action_name: str) -> str:
    words = [WORD_REPLACEMENTS.get(word, word) for word in action_name.split("_")]
    return "HG_" + "_".join(words)


def bake_action(
    rig: bpy.types.Object, action: bpy.types.Action, scene: bpy.types.Scene
) -> dict:
    rig.animation_data.action = action
    if hasattr(action, "slots") and action.slots:
        rig.animation_data.action_slot = action.slots[0]

    deform_bones = [pb for pb in rig.pose.bones if pb.name.startswith("DEF-")]
    rest_rotations = {
        pb.name: pb.bone.matrix_local.to_3x3().normalized().inverted()
        for pb in deform_bones
    }
    root_rest_location = rig.pose.bones["DEF-hips"].bone.matrix_local.translation

    rotations = {BONE_NAME_MAP.get(pb.name, pb.name[4:]): [] for pb in deform_bones}
    root_locations = []
    frame_start, frame_end = (int(round(f)) for f in action.frame_range)
    for frame in range(frame_start, frame_end + 1):
        scene.frame_set(frame)
        for pb in deform_bones:
            delta = pb.matrix.to_3x3().normalized() @ rest_rotations[pb.name]
            rotations[BONE_NAME_MAP.get(pb.name, pb.name[4:])].append(
                delta.to_quaternion()
            )
        root_locations.append(
            rig.pose.bones["DEF-hips"].matrix.translation - root_rest_location
        )

    thigh = rig.pose.bones["DEF-thigh.L"].bone
    shin = rig.pose.bones["DEF-shin.L"].bone
    reference_directions = {
        BONE_NAME_MAP.get(pb.name, pb.name[4:]): (
            pb.bone.tail_local - pb.bone.head_local
        ).normalized()
        for pb in deform_bones
    }
    return {
        "format_version": FORMAT_VERSION,
        "source": "Universal Animation Library by Quaternius",
        "license": "CC0 1.0",
        "fps": scene.render.fps,
        "frame_count": frame_end - frame_start + 1,
        "loop": action.name.endswith("_Loop"),
        "root_motion": "_RM" in action.name,
        "reference_leg_length": thigh.length + shin.length,
        "reference_directions": reference_directions,
        "rotations": rotations,
        "root_location": root_locations,
    }


def main(output_dir: str) -> None:
    scene = bpy.context.scene
    rig = bpy.data.objects[SOURCE_RIG]
    if not rig.animation_data:
        rig.animation_data_create()

    for action in bpy.data.actions:
        if action.name in SKIP_ACTIONS:
            continue
        clip = bake_action(rig, action, scene)
        folder = os.path.join(output_dir, category_of(action.name))
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, file_name_of(action.name) + ".json")
        write_clip(path, clip)
        print(f"{action.name:30s} -> {os.path.relpath(path, output_dir)}")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1])
