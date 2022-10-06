from __future__ import annotations

import os
from os import PathLike
from typing import TYPE_CHECKING, Union

import bpy
from HumGen3D.backend import get_prefs, hg_delete, hg_log
from HumGen3D.human.base.decorators import injected_context
from HumGen3D.human.base.pcoll_content import PreviewCollectionContent
from HumGen3D.human.base.savable_content import SavableContent

if TYPE_CHECKING:
    from human.human import Human

from HumGen3D.custom_content.content_saving import Content_Saving_Operator


class PoseSettings(PreviewCollectionContent, SavableContent):
    def __init__(self, _human):
        self._human: Human = _human
        self._pcoll_name = "pose"
        self._pcoll_gender_split = False

    @injected_context
    def set(self, preset, context=None):
        """Gets called by pcoll_pose to add selected pose to human"""

        sett = context.scene.HG3D
        pref = get_prefs()

        if sett.load_exception:
            return

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

    @injected_context
    def save_to_library(
        self,
        name: str,
        category: str = "Custom",
        thumbnail: Union[None, str, PathLike] = "auto",
        context=None,
    ) -> None:
        folder = os.path.join(get_prefs().filepath, "poses", category)

        pose_object = self._human.rig_obj.copy()
        pose_object.data = pose_object.data.copy()
        pose_object.name = "HG_Pose"
        context.collection.objects.link(pose_object)

        Content_Saving_Operator.save_objects_optimized(
            context,
            [
                pose_object,
            ],
            folder,
            name,
        )

        if thumbnail:
            if thumbnail == "auto":
                thumb_name = self._human.render_thumbnail()

            self.save_thumb(folder, thumb_name, name)

        hg_delete(pose_object)

    def _import_pose(self, preset, context) -> bpy.types.Object:
        """Import selected pose object

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

        hg_pose = data_to.objects[0]
        if not hg_pose:
            hg_log(
                "Could not load pose:",
                context.scene.HG3D.pcoll.pose,
                level="WARNING",
            )

        scene = context.scene
        scene.collection.objects.link(hg_pose)

        return hg_pose

    def _match_roll(self, hg_rig, hg_pose, context):
        """Some weird issue caused changed to the rig to change the roll values on
        bones. This caused imported poses that still use the original armature to
        not copy properly to the human

        Args:
            hg_rig (Object): HumGen human armature
            hg_pose (Object): imported armature set to a certain pose
        """
        context.view_layer.objects.active = hg_pose
        hg_rig.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        for bone in hg_rig.data.edit_bones:
            b_name = bone.name if bone.name != "neck" else "spine.004"
            if b_name in hg_pose.data.edit_bones:
                bone.roll = hg_pose.data.edit_bones[b_name].roll
        bpy.ops.object.mode_set(mode="OBJECT")

    def _match_rotation_mode(self, hg_rig, hg_pose, context):
        context.view_layer.objects.active = hg_pose
        hg_rig.select_set(True)
        bpy.ops.object.mode_set(mode="POSE")
        for bone in hg_rig.pose.bones:
            b_name = bone.name if bone.name != "neck" else "spine.004"
            if b_name in hg_pose.pose.bones:
                bone.rotation_mode = hg_pose.pose.bones[
                    b_name
                ].rotation_mode = "QUATERNION"
        bpy.ops.object.mode_set(mode="OBJECT")

    def _copy_pose(self, context, pose):
        """Copies pose from one human to the other

        Args:
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

            bone_rotations.append(tuple(bone.rotation_euler))

        return hash(tuple(bone_rotations))
