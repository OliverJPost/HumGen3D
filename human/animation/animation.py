# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Contains class for applying animations from the library to a human."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Optional

import bpy
from HumGen3D.backend import get_prefs
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.type_aliases import C
from HumGen3D.human.common_baseclasses.pcoll_content import PreviewCollectionContent
from mathutils import Matrix

from .clip import read_clip
from .retarget import apply_keys_as_action, retarget_clip

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

# Custom properties on actions created by Human Generator
ACTION_PRESET_PROP = "hg_animation"
ACTION_LOOP_PROP = "hg_loop"
ACTION_FRAME_COUNT_PROP = "hg_frame_count"
ACTION_FINGER_CURL_PROP = "hg_finger_curl"
DEFAULT_FINGER_CURL = 1.0


class AnimationSettings(PreviewCollectionContent):
    """Class for applying animations from the Human Generator library.

    Animations are stored as rig independent clips and retargeted to the rig of this
    human when set, see retarget.py. The result is a normal Blender action on the
    rig, which can be edited like any other animation.
    """

    def __init__(self, _human: "Human") -> None:
        self._human: "Human" = _human
        self._pcoll_name = "animation"
        self._pcoll_gender_split = False

    @property
    def action(self) -> Optional[bpy.types.Action]:
        """The action created by Human Generator on the rig, if any.

        Returns:
            Optional[bpy.types.Action]: Action with the active animation, None if
                the human has no Human Generator animation.
        """
        animation_data = self._human.objects.rig.animation_data
        if not animation_data or not animation_data.action:
            return None
        action = animation_data.action
        return action if ACTION_PRESET_PROP in action else None

    @property
    def is_active(self) -> bool:
        """True if a Human Generator animation is on this human."""
        return self.action is not None

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
        """Number of frames of the active animation, 0 if there is none."""
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
    ) -> None:
        """Applies an animation from the Human Generator library to this human.

        The animation replaces the animation set before, and the pose of the body.
        The pose of the face rig is kept.

        Args:
            preset (str): Name of the animation to set, you can get options from the
                `get_options` method.
            context (C): Context to use. Defaults to None.
            loop (Optional[bool]): Repeat the animation outside its frame range.
                Defaults to the setting of the clip, True for cyclic animations.
            set_frame_range (bool): Set the frame range of the scene to the
                animation. Defaults to True.
            finger_curl (float): Blend of the fingers between the relaxed hand of
                the rest pose (0) and the hand of the animation (1). Defaults to 1.0.

        Raises:
            HumGenException: If the human has a Rigify rig.
        """
        if preset == "none":
            return
        if self._human.pose.rigify.is_rigify:
            raise HumGenException("Animations are not supported on Rigify humans.")

        clip = read_clip(os.path.join(get_prefs().filepath, preset))
        if loop is None:
            loop = clip["loop"]

        self.remove()
        self._active = preset

        rig = self._human.objects.rig
        scene = context.scene
        frame_scale = scene.render.fps / clip["fps"]
        keys = retarget_clip(clip, rig, finger_curl)
        name = os.path.splitext(os.path.basename(preset))[0].replace("HG_", "", 1)
        action = apply_keys_as_action(
            rig,
            keys,
            f"{self._human.name}_{name}",
            frame_scale,
            scene.frame_start,
            loop,
        )
        action[ACTION_PRESET_PROP] = preset
        action[ACTION_LOOP_PROP] = loop
        action[ACTION_FRAME_COUNT_PROP] = clip["frame_count"]
        action[ACTION_FINGER_CURL_PROP] = finger_curl

        if set_frame_range:
            self.set_scene_frame_range(context)
        self._human.props.hashes["$pose"] = str(hash(self._human.pose))

    @injected_context
    def refresh(
        self, context: C = None, finger_curl: Optional[float] = None
    ) -> None:
        """Retargets the active animation again, after the rig changed.

        Needed after changes to the height, proportions or rest pose of the human.

        Args:
            context (C): Context to use. Defaults to None.
            finger_curl (Optional[float]): New finger curl factor, see `set`.
                Defaults to the factor of the active animation.
        """
        action = self.action
        if not action:
            return
        if finger_curl is None:
            finger_curl = self.finger_curl
        self.set(
            action[ACTION_PRESET_PROP],
            context,
            loop=bool(action[ACTION_LOOP_PROP]),
            set_frame_range=False,
            finger_curl=finger_curl,
        )

    def remove(self) -> None:
        """Removes the Human Generator animation from this human.

        The animated bones return to their rest position.
        """
        action = self.action
        if not action:
            return

        rig = self._human.objects.rig
        rig.animation_data.action = None
        for group in _action_groups(action):
            rig.pose.bones[group.name].matrix_basis = Matrix.Identity(4)
        if action.users == 0 or (action.users == 1 and action.use_fake_user):
            bpy.data.actions.remove(action)

    @injected_context
    def set_scene_frame_range(self, context: C = None) -> None:
        """Sets the frame range of the scene to one cycle of the active animation.

        Args:
            context (C): Context to use. Defaults to None.
        """
        action = self.action
        if not action:
            return
        scene = context.scene
        frame_start, frame_end = (round(f) for f in action.frame_range)
        # The last frame of a cyclic animation is the same as the first one
        if self.loop and frame_end > frame_start:
            frame_end -= 1
        scene.frame_start = frame_start
        scene.frame_end = max(frame_start, frame_end)

    def as_dict(self) -> dict[str, Any]:
        """Animation settings as dict.

        Returns:
            dict[str, Any]: Animation settings as dict.
        """
        return {"set": self._active if self.is_active else None}


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
