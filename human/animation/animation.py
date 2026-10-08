# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Contains class for applying animations from the library to a human."""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any, Optional

import bpy
from HumGen3D.backend import get_prefs, hg_log
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.type_aliases import C
from HumGen3D.human.common_baseclasses.pcoll_content import PreviewCollectionContent
from mathutils import Matrix

from .clip import read_clip, write_clip
from .mixamo import fbx_to_clip
from .retarget import (
    keyed_frame_start,
    new_action,
    resample_keys,
    retarget_clip,
    write_keys,
)

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

# Custom properties on actions created by Human Generator
ACTION_PRESET_PROP = "hg_animation"
ACTION_LOOP_PROP = "hg_loop"
ACTION_FRAME_COUNT_PROP = "hg_frame_count"
ACTION_FINGER_CURL_PROP = "hg_finger_curl"
ACTION_FPS_PROP = "hg_fps"
DEFAULT_FINGER_CURL = 1.0
# Name of the NLA tracks that animations are added to as strips
NLA_TRACK_NAME = "Human Generator"


class AnimationSettings(PreviewCollectionContent):
    """Class for applying animations from the Human Generator library.

    Animations are stored as rig independent clips and retargeted to the rig of this
    human when set, see retarget.py. The result is a normal Blender action on the
    rig, which can be edited like any other animation. Animations can also be added
    as strips in the NLA editor, to chain or layer them.

    When the human changes shape the actions are retargeted again, in place: only
    the channels of the animated bones are written again, other channels, the name
    and fake user of the action and the NLA strips using it are kept.
    """

    def __init__(self, _human: "Human") -> None:
        self._human: "Human" = _human
        self._pcoll_name = "animation"
        self._pcoll_gender_split = False

    @property
    def action(self) -> Optional[bpy.types.Action]:
        """The active action created by Human Generator on the rig, if any.

        Returns:
            Optional[bpy.types.Action]: Action with the active animation, None if
                the rig has no Human Generator animation as active action. Animations
                in NLA strips are found in `strips`.
        """
        animation_data = self._human.objects.rig.animation_data
        if not animation_data or not animation_data.action:
            return None
        action = animation_data.action
        return action if _is_hg_action(action) else None

    @property
    def strips(self) -> list[bpy.types.NlaStrip]:
        """NLA strips on the rig with an animation created by Human Generator."""
        animation_data = self._human.objects.rig.animation_data
        if not animation_data:
            return []
        return [
            strip
            for track in animation_data.nla_tracks
            for strip in track.strips
            if strip.action and _is_hg_action(strip.action)
        ]

    @property
    def actions(self) -> list[bpy.types.Action]:
        """All actions created by Human Generator on the rig, active and in strips."""
        actions = [self.action] if self.action else []
        for strip in self.strips:
            if strip.action not in actions:
                actions.append(strip.action)
        return actions

    @property
    def is_active(self) -> bool:
        """True if a Human Generator animation is on this human, active or in NLA."""
        return bool(self.actions)

    @property
    def loop(self) -> bool:
        """True if the active animation repeats outside its frame range."""
        action = self.action
        return bool(action and action.get(ACTION_LOOP_PROP))

    @property
    def finger_curl(self) -> float:
        """Blend of the fingers between the rest pose (0) and the animation (1)."""
        action = self.action
        if not action:
            return DEFAULT_FINGER_CURL
        return float(action.get(ACTION_FINGER_CURL_PROP, DEFAULT_FINGER_CURL))

    @property
    def frame_count(self) -> int:
        """Number of keyed frames of the active animation, 0 if there is none."""
        action = self.action
        return int(action.get(ACTION_FRAME_COUNT_PROP, 0)) if action else 0

    @injected_context
    def set(  # noqa: A003
        self,
        preset: str,
        context: C = None,
        loop: Optional[bool] = None,
        set_frame_range: bool = True,
        finger_curl: float = DEFAULT_FINGER_CURL,
        as_strip: bool = False,
        frame_start: Optional[int] = None,
    ) -> Optional[bpy.types.Action]:
        """Applies an animation from the Human Generator library to this human.

        By default the animation becomes the active action of the rig, replacing
        the active Human Generator animation set before, and the pose of the body.
        The pose of the face rig is kept. Keys are placed on whole scene frames,
        resampled if the frame rate of the clip differs from the scene.

        With `as_strip` the animation is added as a strip in the NLA editor instead,
        after the last strip added this way. An active Human Generator animation
        is pushed down to a strip first, so the new one is visible.

        Args:
            preset (str): Name of the animation to set, you can get options from the
                `get_options` method.
            context (C): Context to use. Defaults to None.
            loop (Optional[bool]): Repeat the animation outside its frame range.
                Defaults to the setting of the clip, True for cyclic animations.
            set_frame_range (bool): Set the frame range of the scene to the
                animation. Defaults to True. Ignored for strips.
            finger_curl (float): Blend of the fingers between the relaxed hand of
                the rest pose (0) and the hand of the animation (1). Defaults to 1.0.
            as_strip (bool): Add as NLA strip instead of as active action. Defaults
                to False.
            frame_start (Optional[int]): Scene frame of the first key. Defaults to
                the start frame of the scene, for strips to the end of the last
                Human Generator strip.

        Returns:
            Optional[bpy.types.Action]: The created action, None if preset is
                "none".

        Raises:
            HumGenException: If the human has a Rigify rig.
        """
        if preset == "none":
            return None
        if self._human.pose.rigify.is_rigify:
            raise HumGenException("Animations are not supported on Rigify humans.")

        clip = read_clip(os.path.join(get_prefs().filepath, preset))
        if loop is None:
            loop = clip["loop"]

        self._active = preset
        rig = self._human.objects.rig
        scene = context.scene
        name = os.path.splitext(os.path.basename(preset))[0].replace("HG_", "", 1)
        action = new_action(rig, f"{self._human.name}_{name}")

        if as_strip:
            self.push_down()
            if frame_start is None:
                frame_start = self._next_strip_start(scene)
            self._retarget_into(
                action, clip, preset, loop, finger_curl, scene.render.fps, frame_start
            )
            self._add_strip(action, frame_start)
        else:
            self.remove()
            if not rig.animation_data:
                rig.animation_data_create()
            rig.animation_data.action = action
            if hasattr(action, "slots"):
                rig.animation_data.action_slot = action.slots[0]
            if frame_start is None:
                frame_start = scene.frame_start
            self._retarget_into(
                action, clip, preset, loop, finger_curl, scene.render.fps, frame_start
            )
            if set_frame_range:
                self.set_scene_frame_range(context)

        self._human.props.hashes["$pose"] = str(hash(self._human.pose))
        return action

    @injected_context
    def import_mixamo(
        self,
        filepath: str,
        name: Optional[str] = None,
        category: str = "Mixamo",
        loop: bool = False,
        context: C = None,
        render_thumbnail: bool = True,
        finger_curl: float = DEFAULT_FINGER_CURL,
    ) -> str:
        """Converts a Mixamo FBX file to a clip in the library and applies it.

        The clip is saved as json in the animations folder of the content folder,
        so it shows up in the animation library and can be used on other humans
        too. See mixamo.py for the conversion.

        Args:
            filepath (str): Path of the FBX file downloaded from Mixamo.
            name (Optional[str]): Name of the animation in the library. Defaults
                to the name of the file.
            category (str): Folder of the animation library to save the clip in,
                created if it does not exist. Defaults to "Mixamo".
            loop (bool): Mark the animation as cyclic. Defaults to False.
            context (C): Context to use. Defaults to None.
            render_thumbnail (bool): Render a thumbnail of this human in the
                animation next to the clip. Defaults to True.
            finger_curl (float): See `set`. Defaults to 1.0.

        Returns:
            str: Preset path of the new animation, relative to the content folder.

        Raises:
            HumGenException: If the file is not a Mixamo animation or the human
                has a Rigify rig.
        """
        if self._human.pose.rigify.is_rigify:
            raise HumGenException("Animations are not supported on Rigify humans.")

        clip = fbx_to_clip(filepath, context, loop)
        if not name:
            name = os.path.splitext(os.path.basename(filepath))[0]
        name = _file_name(name)
        folder = os.path.join(get_prefs().filepath, "animations", category)
        os.makedirs(folder, exist_ok=True)
        write_clip(os.path.join(folder, name + ".json"), clip)
        preset = os.path.join("animations", category, name + ".json")

        self.set(preset, context, finger_curl=finger_curl)
        if render_thumbnail:
            self._render_thumbnail(folder, name, context)
        self.refresh_pcoll(context)
        return preset

    def _render_thumbnail(self, folder: str, name: str, context: C) -> None:
        """Renders the human at a representative frame of the active animation."""
        if not context.window:
            hg_log("No window to render a thumbnail in, skipping", level="WARNING")
            return
        scene = context.scene
        frame = scene.frame_current
        scene.frame_set(
            scene.frame_start + round(0.4 * (scene.frame_end - scene.frame_start))
        )
        try:
            self._human.render_thumbnail(folder, name, context=context)
        finally:
            scene.frame_set(frame)

    @injected_context
    def refresh(
        self, context: C = None, finger_curl: Optional[float] = None
    ) -> None:
        """Retargets the Human Generator animations again, after the rig changed.

        Needed after changes to the height, proportions or rest pose of the human.
        The actions are updated in place, see the class docstring, and keep their
        timing: the frame they start on and their length.

        Args:
            context (C): Context to use. Defaults to None.
            finger_curl (Optional[float]): New finger curl factor for the active
                animation, see `set`. Defaults to the factor it has. Animations in
                NLA strips keep their own factor.
        """
        active = self.action
        for action in self.actions:
            preset = action[ACTION_PRESET_PROP]
            try:
                clip = read_clip(os.path.join(get_prefs().filepath, preset))
            except (OSError, ValueError) as e:
                hg_log(f"Could not refresh animation {preset}: {e}", level="WARNING")
                continue
            curl = float(action.get(ACTION_FINGER_CURL_PROP, DEFAULT_FINGER_CURL))
            if finger_curl is not None and active and action == active:
                curl = finger_curl
            self._retarget_into(
                action,
                clip,
                preset,
                bool(action.get(ACTION_LOOP_PROP)),
                curl,
                float(action.get(ACTION_FPS_PROP, context.scene.render.fps)),
                context.scene.frame_start,
            )

    def _retarget_into(
        self,
        action: bpy.types.Action,
        clip: dict[str, Any],
        preset: str,
        loop: bool,
        finger_curl: float,
        fps: float,
        default_frame_start: int,
    ) -> None:
        """Writes the retargeted clip to the action, see retarget.write_keys.

        The keys start on the frame the action already has keys for these bones on,
        or on default_frame_start if it has none.
        """
        rig = self._human.objects.rig
        keys = retarget_clip(clip, rig, finger_curl)
        keys = resample_keys(keys, fps / clip["fps"])
        frame_start = keyed_frame_start(action, keys)
        if frame_start is None:
            frame_start = default_frame_start
        write_keys(action, rig, keys, frame_start, loop)

        action[ACTION_PRESET_PROP] = preset
        action[ACTION_LOOP_PROP] = loop
        action[ACTION_FRAME_COUNT_PROP] = len(next(iter(keys.values()))[0])
        action[ACTION_FINGER_CURL_PROP] = finger_curl
        action[ACTION_FPS_PROP] = fps

    def push_down(self) -> Optional[bpy.types.NlaStrip]:
        """Moves the active Human Generator animation to a strip in the NLA editor.

        Like the push down button of Blender. The action keeps its frame range and
        is no longer the active action, so another animation can be set or added on
        top of it.

        Returns:
            Optional[bpy.types.NlaStrip]: The new strip, None if the human has no
                active Human Generator animation.
        """
        action = self.action
        if not action:
            return None
        animation_data = self._human.objects.rig.animation_data
        strip = self._add_strip(action, round(action.frame_range[0]))
        animation_data.action = None
        return strip

    def _add_strip(
        self, action: bpy.types.Action, frame_start: int
    ) -> bpy.types.NlaStrip:
        """Adds the action as strip to a Human Generator track that has room for it."""
        rig = self._human.objects.rig
        if not rig.animation_data:
            rig.animation_data_create()
        animation_data = rig.animation_data

        for track in animation_data.nla_tracks:
            if track.name != NLA_TRACK_NAME and not track.name.startswith(
                NLA_TRACK_NAME + "."
            ):
                continue
            try:
                strip = track.strips.new(action.name, frame_start, action)
                break
            except RuntimeError:
                # No room between the strips of this track
                continue
        else:
            track = animation_data.nla_tracks.new()
            track.name = NLA_TRACK_NAME
            strip = track.strips.new(action.name, frame_start, action)

        if hasattr(strip, "action_slot") and action.slots:
            strip.action_slot = action.slots[0]
        return strip

    def _next_strip_start(self, scene: bpy.types.Scene) -> int:
        """Frame after the last Human Generator strip, the scene start if none."""
        strips = self.strips
        if not strips:
            return int(scene.frame_start)
        return round(max(strip.frame_end for strip in strips))

    def remove(self, active: bool = True, strips: bool = False) -> None:
        """Removes Human Generator animations from this human.

        The animated bones return to their rest position. Actions are deleted
        unless they are still used, by an NLA strip or a fake user.

        Args:
            active (bool): Remove the active animation. Defaults to True.
            strips (bool): Remove the Human Generator animations in NLA strips and
                the tracks that become empty. Defaults to False.
        """
        rig = self._human.objects.rig
        animation_data = rig.animation_data
        action = self.action
        if active and action:
            animation_data.action = None
            self._reset_bones(action)
            _delete_if_unused(action)

        if not strips or not animation_data:
            return
        for track in list(animation_data.nla_tracks):
            for strip in list(track.strips):
                if not strip.action or not _is_hg_action(strip.action):
                    continue
                strip_action = strip.action
                track.strips.remove(strip)
                self._reset_bones(strip_action)
                _delete_if_unused(strip_action)
            if not track.strips and track.name.startswith(NLA_TRACK_NAME):
                animation_data.nla_tracks.remove(track)

    def _reset_bones(self, action: bpy.types.Action) -> None:
        """Puts the bones animated by the action back in their rest position."""
        pose_bones = self._human.objects.rig.pose.bones
        for group in _action_groups(action):
            if group.name in pose_bones:
                pose_bones[group.name].matrix_basis = Matrix.Identity(4)

    def _detach(self) -> dict[str, Any]:
        """Stops the animation of the rig, to change its pose without the animation
        writing over it. Undo with `_attach`.

        Returns:
            dict[str, Any]: State for `_attach`.
        """
        animation_data = self._human.objects.rig.animation_data
        if not animation_data:
            return {}
        state: dict[str, Any] = {
            "action": animation_data.action,
            "slot_identifier": getattr(animation_data, "last_slot_identifier", None),
            "muted_tracks": [track.mute for track in animation_data.nla_tracks],
        }
        animation_data.action = None
        for track in animation_data.nla_tracks:
            track.mute = True
        return state

    def _attach(self, state: dict[str, Any]) -> None:
        """Restores the animation of the rig stopped by `_detach`."""
        if not state:
            return
        animation_data = self._human.objects.rig.animation_data
        action = state["action"]
        animation_data.action = action
        if action and state["slot_identifier"] and hasattr(action, "slots"):
            slot = action.slots.get(state["slot_identifier"])
            if slot:
                animation_data.action_slot = slot
        for track, mute in zip(animation_data.nla_tracks, state["muted_tracks"]):
            track.mute = mute

    @injected_context
    def set_scene_frame_range(self, context: C = None) -> None:
        """Sets the frame range of the scene to the Human Generator animation.

        One cycle of the active animation, or the range of all Human Generator
        strips if there is no active animation.

        Args:
            context (C): Context to use. Defaults to None.
        """
        scene = context.scene
        action = self.action
        if action:
            frame_start, frame_end = (round(f) for f in action.frame_range)
            # The last frame of a cyclic animation is the same as the first one
            if self.loop and frame_end > frame_start:
                frame_end -= 1
        elif self.strips:
            frame_start = round(min(strip.frame_start for strip in self.strips))
            frame_end = round(max(strip.frame_end for strip in self.strips))
        else:
            return
        scene.frame_start = frame_start
        scene.frame_end = max(frame_start, frame_end)

    def as_dict(self) -> dict[str, Any]:
        """Animation settings as dict.

        Returns:
            dict[str, Any]: Animation settings as dict.
        """
        return {"set": self._active if self.is_active else None}


def _is_hg_action(action: bpy.types.Action) -> bool:
    return ACTION_PRESET_PROP in action


def _delete_if_unused(action: bpy.types.Action) -> None:
    """Deletes the action unless something still uses it, a strip or a fake user."""
    if action.users == 0:
        bpy.data.actions.remove(action)


def _file_name(name: str) -> str:
    """Library file name for a user given name, like the other content savers."""
    name = re.sub(r"[^\w\s-]", "", name.strip())
    return re.sub(r"\s+", "_", name) or "Animation"


def _action_groups(action: bpy.types.Action) -> list[bpy.types.ActionGroup]:
    if hasattr(action, "slots"):
        return [
            group
            for layer in action.layers
            for strip in layer.strips
            for channelbag in strip.channelbags
            for group in channelbag.groups
        ]
    return list(action.groups)
