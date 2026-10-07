# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Animations of a processed human, for export.

The actions of the source human animate its rig, which the processed copy no
longer has once the skeleton is converted: bones are gone or renamed and the
rest pose may be the T-pose. The Human Generator animations are stored as rig
independent clips, so they are retargeted again onto the converted skeleton.
Other actions are exported as they are, with a warning when the rest pose
changed.
"""

import re
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator, List, Optional, Tuple

import bpy
from HumGen3D.backend.logging import hg_log
from HumGen3D.human.animation.animation import ACTION_PRESET_PROP, NLA_TRACK_NAME
from HumGen3D.human.animation.retarget import _channels, original_name
from mathutils import Vector

from .settings import AnimationSettings

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

HIPS_BONE = "spine"


def library_clips(human: "Human", context: bpy.types.Context) -> List[Tuple[str, str]]:
    """Preset path and display name of every clip in the animation library."""
    presets = [
        option
        for option in human.animation.get_options(context=context)
        if option != "none"
    ]
    return [
        (preset, os.path.splitext(os.path.basename(preset))[0].replace("HG_", "", 1))
        for preset in presets
    ]


def library_presets(
    human: "Human", settings: AnimationSettings, context: bpy.types.Context
) -> List[str]:
    """The library clips the settings select, all of them for None."""
    presets = [preset for preset, _ in library_clips(human, context)]
    if settings.clips is None:
        return presets
    return [preset for preset in presets if preset in settings.clips]


def source_clips(
    human: "Human", settings: AnimationSettings, context: Optional[bpy.types.Context] = None
) -> list:
    """What the settings select to export: actions of the human, or for the
    library source the preset paths.

    Args:
        human (Human): Human with the animations, the source or its copy.
        settings (AnimationSettings): None for `clips` selects every Human
            Generator animation, otherwise the actions with those names.
        context (Optional[bpy.types.Context]): Needed for the library source.
    """
    if settings.source == "library":
        return library_presets(human, settings, context or bpy.context)
    rig = human.objects.rig
    actions = []
    if settings.clips is None:
        actions = list(human.animation.actions)
    else:
        for name in settings.clips:
            action = bpy.data.actions.get(name)
            if action and action not in actions:
                actions.append(action)
    # The active action first, so it is the default take
    animation_data = rig.animation_data
    active = animation_data.action if animation_data else None
    if active in actions:
        actions.remove(active)
        actions.insert(0, active)
    return actions


def clip_names(human: "Human") -> List[Tuple[str, bool]]:
    """Name of every action on the rig of the human and whether it is a Human
    Generator animation, for the interface."""
    rig = human.objects.rig
    names = []
    animation_data = rig.animation_data
    if not animation_data:
        return names
    if animation_data.action:
        names.append((animation_data.action.name, ACTION_PRESET_PROP in animation_data.action))
    for track in animation_data.nla_tracks:
        for strip in track.strips:
            if strip.action and strip.action.name not in [n for n, _ in names]:
                names.append((strip.action.name, ACTION_PRESET_PROP in strip.action))
    return names


def prepare_clips(
    copy: "Human",
    source: "Human",
    settings: AnimationSettings,
    context: bpy.types.Context,
) -> Tuple[List[bpy.types.Action], List[str]]:
    """Gives the processed copy its own actions, fitted to its skeleton.

    The copy shares the actions of the source human after duplicating. Each
    selected action is copied, Human Generator animations are retargeted onto
    the converted rig, and the copy's animation data holds only these actions,
    one strip per NLA track so exporters write every clip as a take.

    Args:
        copy (Human): The processed copy, skeleton already converted.
        source (Human): The human it was made from.
        settings (AnimationSettings): Which clips and the root motion.
        context (bpy.types.Context): Blender context.

    Returns:
        Tuple[List[Action], List[str]]: The actions of the copy and warnings.
    """
    warnings: List[str] = []
    rig = copy.objects.rig
    if not rig.animation_data:
        rig.animation_data_create()
    animation_data = rig.animation_data
    animation_data.action = None
    for track in list(animation_data.nla_tracks):
        animation_data.nla_tracks.remove(track)

    clips = []
    rest_pose_changed = copy.process.has_t_pose_rest
    if settings.source == "library":
        # Set on the copy itself, which retargets onto its skeleton right away
        for preset in library_presets(copy, settings, context):
            copy.animation.set(preset, context, as_strip=True, set_frame_range=False)
        clips = list(copy.animation.actions)
    for action in source_clips(source, settings) if settings.source != "library" else []:
        clip = action.copy()
        clip.name = action.name
        clip.use_fake_user = False
        if ACTION_PRESET_PROP not in clip and rest_pose_changed:
            warnings.append(
                f"Clip {action.name} is not a Human Generator animation, it was"
                " exported as is, in the A-pose rest pose"
            )
        _retarget_action_bones(clip, rig)
        clips.append(clip)

    # Retargets the Human Generator clips onto the converted skeleton
    animation_data.action = clips[0] if clips else None
    for clip in clips[1:]:
        track = animation_data.nla_tracks.new()
        track.name = NLA_TRACK_NAME
        strip = track.strips.new(clip.name, int(clip.frame_range[0]), clip)
        if hasattr(strip, "action_slot") and clip.slots:
            strip.action_slot = clip.slots[0]
    if hasattr(animation_data, "action_slot") and clips and clips[0].slots:
        animation_data.action_slot = clips[0].slots[0]
    copy.animation.refresh(context)

    if settings.root_motion == "root" and copy.process.has_game_rig:
        root = next(
            (b for b in rig.pose.bones if b.bone.parent is None and not b.bone.use_deform),
            None,
        )
        if root:
            for clip in clips:
                _move_root_motion(clip, rig, root.name)
        else:
            warnings.append("No root bone to move the root motion to")

    # Every clip as its own strip, the active action in the first track
    if clips:
        animation_data.action = None
        for track in list(animation_data.nla_tracks):
            animation_data.nla_tracks.remove(track)
        for clip in clips:
            track = animation_data.nla_tracks.new()
            track.name = clip.name
            strip = track.strips.new(clip.name, int(clip.frame_range[0]), clip)
            if hasattr(strip, "action_slot") and clip.slots:
                strip.action_slot = clip.slots[0]
    return clips, warnings


def _retarget_action_bones(action: bpy.types.Action, rig: bpy.types.Object) -> None:
    """Points the channels of an action at the renamed bones of the rig.

    Blender renames the channels of assigned actions when a bone is renamed,
    but these actions were copied afterwards and belong to the source rig.
    """
    by_original = {original_name(pb): pb.name for pb in rig.pose.bones}
    fcurves, groups = _channels(action)
    for fcurve in fcurves:
        path = fcurve.data_path
        if not path.startswith('pose.bones["'):
            continue
        bone_name = path[12 : path.index('"]')]
        new_name = by_original.get(bone_name)
        if new_name and new_name != bone_name:
            fcurve.data_path = path.replace(f'["{bone_name}"]', f'["{new_name}"]', 1)
            if fcurve.group:
                fcurve.group.name = new_name
    for fcurve in list(fcurves):
        bone_name = fcurve.data_path[12 : fcurve.data_path.index('"]')] if fcurve.data_path.startswith('pose.bones["') else None
        if bone_name and bone_name not in rig.pose.bones:
            # The bone was removed by the skeleton conversion
            fcurves.remove(fcurve)


def _move_root_motion(action: bpy.types.Action, rig: bpy.types.Object, root_name: str) -> None:
    """Moves the travel of the hips over the ground to the root bone.

    The hips keep their height and sway, the root bone carries the horizontal
    movement, which engines read as root motion.
    """
    hips = next((pb for pb in rig.pose.bones if original_name(pb) == HIPS_BONE), None)
    if hips is None:
        return
    fcurves, groups = _channels(action)
    hips_path = f'pose.bones["{hips.name}"].location'
    hips_curves = [None, None, None]
    for fcurve in fcurves:
        if fcurve.data_path == hips_path and fcurve.array_index < 3:
            hips_curves[fcurve.array_index] = fcurve
    if not any(hips_curves):
        return
    frames = sorted(
        {
            round(point.co.x)
            for fcurve in hips_curves
            if fcurve
            for point in fcurve.keyframe_points
        }
    )
    if not frames:
        return

    # Hips location is in the local space of the hips bone, the root bone is
    # at the origin with world axes
    rest = hips.bone.matrix_local.to_3x3()
    root_path = f'pose.bones["{root_name}"].location'
    group = groups.get(root_name) or groups.new(root_name)
    root_curves = []
    for index in range(3):
        fcurve = next(
            (f for f in fcurves if f.data_path == root_path and f.array_index == index),
            None,
        )
        if fcurve is None:
            fcurve = fcurves.new(root_path, index=index)
            fcurve.group = group
        root_curves.append(fcurve)

    first_local = Vector(
        [fcurve.evaluate(frames[0]) if fcurve else 0.0 for fcurve in hips_curves]
    )
    for frame in frames:
        local = Vector([fcurve.evaluate(frame) if fcurve else 0.0 for fcurve in hips_curves])
        world = rest @ (local - first_local)
        # Only the travel over the ground moves to the root
        world.z = 0.0
        for index, fcurve in enumerate(root_curves):
            fcurve.keyframe_points.insert(frame, world[index], options={"FAST"})
        stays = local - rest.inverted() @ world
        for index, fcurve in enumerate(hips_curves):
            if fcurve:
                point = next((p for p in fcurve.keyframe_points if round(p.co.x) == frame), None)
                if point:
                    point.co.y = stays[index]
    for fcurve in root_curves + [f for f in hips_curves if f]:
        fcurve.update()


@contextmanager
def active_clip(human: "Human", clip: Optional[bpy.types.Action]) -> Iterator[None]:
    """Makes one clip the active action and mutes the strips, for per-clip files."""
    rig = human.objects.rig
    animation_data = rig.animation_data
    if not animation_data:
        yield
        return
    old_action = animation_data.action
    muted = [(track, track.mute) for track in animation_data.nla_tracks]
    for track in animation_data.nla_tracks:
        track.mute = True
    animation_data.action = clip
    if clip is not None and hasattr(animation_data, "action_slot") and clip.slots:
        animation_data.action_slot = clip.slots[0]
    try:
        yield
    finally:
        animation_data.action = old_action
        for track, mute in muted:
            track.mute = mute


def clip_file_name(name: str, clip: bpy.types.Action) -> str:
    """File name of a clip exported on its own, "Jake@Run" as Unity reads it."""
    clip_name = re.sub(r"\.\d{3}$", "", clip.name)
    if clip_name.startswith(name + "_"):
        clip_name = clip_name[len(name) + 1 :]
    return f"{name}@{clip_name}"


def rig_actions(human: "Human") -> List[bpy.types.Action]:
    """The active action and the actions of the NLA strips of the rig."""
    animation_data = human.objects.rig.animation_data
    if not animation_data:
        return []
    actions = []
    if animation_data.action:
        actions.append(animation_data.action)
    for track in animation_data.nla_tracks:
        for strip in track.strips:
            if strip.action and strip.action not in actions:
                actions.append(strip.action)
    return actions


def remove_clips(human: "Human") -> None:
    """Removes the actions and strips of a processed human that is deleted."""
    rig = human.objects.rig
    animation_data = rig.animation_data
    if not animation_data:
        return
    actions = rig_actions(human)
    animation_data.action = None
    for track in list(animation_data.nla_tracks):
        animation_data.nla_tracks.remove(track)
    for action in actions:
        if action.users == 0:
            bpy.data.actions.remove(action)
        else:
            hg_log(f"Action {action.name} still in use, not removed", level="DEBUG")
