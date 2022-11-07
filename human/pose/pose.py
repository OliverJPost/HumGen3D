"""Contains class for manipulating pose of human."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Optional

import bpy
from bpy.types import Image  # type:ignore
from HumGen3D.backend import get_prefs, hg_delete, hg_log
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C
from HumGen3D.human.common_baseclasses.pcoll_content import PreviewCollectionContent
from HumGen3D.human.common_baseclasses.savable_content import SavableContent

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.backend.content.content_saving import save_objects_optimized, save_thumb


class PoseSettings(PreviewCollectionContent, SavableContent):
    """Class for manipulating pose of human."""

    def __init__(self, _human: "Human") -> None:
        self._human: "Human" = _human
        self._pcoll_name = "pose"
        self._pcoll_gender_split = False

    @injected_context
    def set(self, preset: str, context: C = None) -> None:  # noqa: A003
        """Set a pose from the Human Generator pose library.

        Args:
            preset (str): Name of the pose to set, you can get options from the
                `get_options` method.
            context (C): Context to use. Defaults to None.
        """
        sett = bpy.context.window_manager.humgen3d  # type:ignore[attr-defined]
        pref = get_prefs()

        if sett.load_exception:
            return

        self._active = preset

        hg_rig = self._human.rig_obj
        hg_pose = self._import_pose(preset, context)

        self._match_rotation_mode(hg_rig, hg_pose, context)
        self._match_roll(hg_rig, hg_pose, context)

        self._copy_pose(context, hg_pose)

        hg_rig.hide_set(False)
        hg_rig.hide_viewport = False

        context.view_layer.objects.active = hg_rig

        hg_pose.select_set(False)
        hg_rig.select_set(True)

        bpy.ops.object.mode_set(mode="POSE")
        bpy.ops.pose.paste()

        bpy.ops.object.mode_set(mode="OBJECT")

        if not pref.debug_mode:
            hg_delete(hg_pose)

        self._human.props.hashes["$pose"] = str(hash(self))

    @injected_context
    def save_to_library(
        self,
        name: str,
        category: str = "Custom",
        thumbnail: Optional[Image] = None,
        context: C = None,
    ) -> None:
        """Save current pose to the Human Generator pose library.

        Args:
            name (str): Name to save the pose as.
            category (str): Category to save the pose in. If the category
                does not exist, a new folder is created. Defaults to "Custom".
            thumbnail (Optional[Image]): Thumbnail to use for the pose. If None, no
                thumbnail is saved. Defaults to None.
            context (C): Context to use. Defaults to None.
        """
        folder = os.path.join(get_prefs().filepath, "poses", category)

        pose_object = self._human.rig_obj.copy()
        pose_object.data = pose_object.data.copy()
        pose_object.name = "HG_Pose"
        context.collection.objects.link(pose_object)

        save_objects_optimized(
            context,
            [
                pose_object,
            ],
            folder,
            name,
        )

        if thumbnail:
            thumb_name = thumbnail.name
            save_thumb(folder, thumb_name, name)

        hg_delete(pose_object)

    def as_dict(self) -> dict[str, Any]:
        """Pose settings as dict.

        Returns:
            dict[str, Any]: Pose settings as dict.
        """
        return {"set": self._active}

    def _import_pose(self, preset: str, context: bpy.types.Context) -> bpy.types.Object:
        """Import selected pose object.

        Args:
            preset (str): Name of the pose to set, you can get options from the
                `get_options` method.
            context (C): Context to use. Defaults to None.

        Returns:
            bpy.types.Object: Armature containing this pose
        """
        pref = get_prefs()

        blendfile = str(pref.filepath) + preset
        with bpy.data.libraries.load(blendfile, link=False) as (
            _,
            data_to,
        ):
            data_to.objects = ["HG_Pose"]

        hg_pose: bpy.types.Object = data_to.objects[0]  # type:ignore[assignment]
        if not hg_pose:
            hg_log(
                "Could not load pose:",
                bpy.context.window_manager.humgen3d.pcoll.pose,
                level="WARNING",
            )

        scene = context.window_manager
        scene.collection.objects.link(hg_pose)

        return hg_pose

    def _match_roll(
        self,
        hg_rig: bpy.types.Object,
        hg_pose: bpy.types.Object,
        context: bpy.types.Context,
    ) -> None:
        """Matches roll on bones in rig.

        Some weird issue caused changed to the rig to change the roll values on
        bones. This caused imported poses that still use the original armature to
        not copy properly to the human

        Args:
            hg_rig (Object): HumGen human armature
            hg_pose (Object): imported armature set to a certain pose
            context (Context): Context from Blender
        """
        # TODO check if still needed
        context.view_layer.objects.active = hg_pose
        hg_rig.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        for bone in hg_rig.data.edit_bones:
            b_name = bone.name if bone.name != "neck" else "spine.004"
            if b_name in hg_pose.data.edit_bones:
                bone.roll = hg_pose.data.edit_bones[b_name].roll
        bpy.ops.object.mode_set(mode="OBJECT")

    def _match_rotation_mode(
        self,
        hg_rig: bpy.types.Object,
        hg_pose: bpy.types.Object,
        context: bpy.types.Context,
    ) -> None:
        context.view_layer.objects.active = hg_pose
        hg_rig.select_set(True)
        bpy.ops.object.mode_set(mode="POSE")
        for bone in hg_rig.pose.bones:
            b_name = bone.name if bone.name != "neck" else "spine.004"
            if b_name in hg_pose.pose.bones:  # type:ignore # TODO does do anything?
                bone.rotation_mode = hg_pose.pose.bones[  # type:ignore
                    b_name  # type:ignore
                ].rotation_mode = "QUATERNION"
        bpy.ops.object.mode_set(mode="OBJECT")

    def _copy_pose(self, context: bpy.types.Context, pose: bpy.types.Object) -> None:
        """Copies pose from one human to the other.

        Args:
            context (C): Blender context. bpy.context if not provided.
            pose (Object): armature to copy from
        """
        for obj in context.selected_objects:
            obj.select_set(False)

        pose.select_set(True)
        context.view_layer.objects.active = pose

        bpy.ops.object.mode_set(mode="POSE")

        for posebone in pose.pose.bones:
            posebone.bone.select = True

        bpy.ops.pose.copy()
        bpy.ops.object.mode_set(mode="OBJECT")

    def __hash__(self) -> int:
        armature = self._human.rig_obj

        SKIP_GROUPS = (
            "eye_scale_grp",
            "eye_settings_grp",
            "eyeball_lookat_grp",
            "facial_rig_grp",
            "facial_rig_lips_grp",
        )

        bone_rotations = []
        for bone in armature.pose.bones:
            if bone.name.lower().startswith("eye"):
                continue
            if bone.bone_group and bone.bone_group.name in SKIP_GROUPS:
                continue

            rotation_mode = bone.rotation_mode
            if rotation_mode == "QUATERNION":
                rotation_attr = "rotation_quaternion"
            else:
                rotation_attr = "rotation_euler"

            bone_rotations.append(tuple(getattr(bone, rotation_attr)))

        return hash(tuple(bone_rotations))
