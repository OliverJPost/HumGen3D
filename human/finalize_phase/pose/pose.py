import bpy
from HumGen3D.backend.logging import hg_log
from HumGen3D.backend.memory_management import hg_delete
from HumGen3D.backend.preference_func import get_prefs


class PoseSettings:
    def __init__(self, _human):
        self._human = _human

    def set(self, preset, context=None):
        """Gets called by pcoll_pose to add selected pose to human"""

        if not context:
            context = bpy.context

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
                context.scene.HG3D.pcoll_poses,
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
