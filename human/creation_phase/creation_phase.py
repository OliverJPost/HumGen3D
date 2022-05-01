from typing import TYPE_CHECKING

import bpy
from bpy.types import Context
from HumGen3D.human.base.prop_collection import PropCollection

from ...backend.preview_collections import refresh_pcoll
from ..base.collections import add_to_collection
from ..shape_keys.shape_keys import apply_shapekeys
from .body.body import BodySettings
from .face.face import FaceKeys
from .length.length import LengthSettings, apply_armature

if TYPE_CHECKING:
    from HumGen3D import Human


class CreationPhaseSettings:
    def __init__(self, human):
        self._human: Human = human

    @property
    def body(self) -> BodySettings:
        if not hasattr(self, "_body"):
            self._body = BodySettings(self._human)
        return self._body

    @property
    def length(self) -> LengthSettings:
        if not hasattr(self, "_length"):
            self._length = LengthSettings(self._human)
        return self._length

    @property
    def face(self) -> FaceKeys:
        if not hasattr(self, "_face"):
            self._face = FaceKeys(self._human)
        return self._face

    # FIXME this will crash blender when accessed after modified
    @property
    def stretch_bones(self):
        if not hasattr(self, "_stretch_bones"):
            stretch_bones = []
            for bone in self._human.pose_bones:
                if [c for c in bone.constraints if c.type == "STRETCH_TO"]:
                    stretch_bones.append(bone)
            self._stretch_bones = PropCollection(stretch_bones)

        return self._stretch_bones

    def finish(self, context):
        """For full feature breakdown, see HG_FINISH_CREATION

        Args:
            hg_rig (Object): HumGen armature
            hg_body (Object): HumGen body object
        """
        human = self._human
        hg_rig = human.rig_obj
        hg_rig.select_set(True)
        hg_rig.hide_set(False)
        hg_rig.hide_viewport = False
        context.view_layer.objects.active = hg_rig
        for obj in context.selected_objects:
            if obj != hg_rig:
                obj.select_set(False)

        human.hair.set_children_hide_state(True)

        old_shading = context.space_data.shading.type
        context.space_data.shading.type = "SOLID"

        human.hair.eyebrows.remove_unused(_internal=True)

        self._create_backup_human(context)

        sk_dict, driver_dict = human.shape_keys._extract_permanent_keys(
            context
        )

        apply_shapekeys(human.body_obj)
        apply_shapekeys(human.eyes.eye_obj)

        for obj in human.children:
            apply_armature(obj)

        human.creation_phase.length.apply(context)

        human.creation_phase.remove_stretch_bones()

        for obj in human.children:
            self._add_applied_armature(obj)
        human.shape_keys._reapply_permanent_keys(sk_dict, driver_dict, context)

        context.view_layer.objects.active = hg_rig

        self._remove_teeth_constraint()
        self._set_teeth_parent()

        refresh_pcoll(self, context, "poses")

        human.props.length = hg_rig.dimensions[2]

        # force recalculation of shapekeys
        sk = human.shape_keys
        sk["cor_ShoulderSideRaise_Lt"].mute = True
        sk["cor_ShoulderSideRaise_Lt"].mute = False

        context.space_data.shading.type = old_shading

    def _create_backup_human(self, context: Context = None):
        if not context:
            context = bpy.context

        hg_rig = self._human.rig_obj
        hg_backup = hg_rig.copy()
        hg_rig.HG.backup = hg_backup
        hg_backup.data = hg_backup.data.copy()
        hg_backup.name = hg_rig.name + "_Backup"

        context.collection.objects.link(hg_backup)
        hg_backup.hide_viewport = True
        hg_backup.hide_render = True
        add_to_collection(
            context, hg_backup, collection_name="HumGen_Backup [Don't Delete]"
        )

        for obj in hg_rig.children:
            obj_copy = obj.copy()
            obj_copy.data = obj_copy.data.copy()
            context.collection.objects.link(obj_copy)

            add_to_collection(
                context,
                obj_copy,
                collection_name="HumGen_Backup [Don't Delete]",
            )
            obj_copy.parent = hg_backup

            armatures = [
                mod for mod in obj_copy.modifiers if mod.type == "ARMATURE"
            ]
            if armatures:
                armatures[0].object = hg_backup
            obj_copy.hide_viewport = True
            obj_copy.hide_render = True

        hg_backup.matrix_parent_inverse = hg_rig.matrix_world.inverted()
        hg_backup.select_set(False)

    def remove_stretch_bones(self):
        """Removes all bones on this rig that have a stretch_to constraint

        Args:
            hg_rig (Object): HumGen human armature
        """
        bpy.ops.object.mode_set(mode="POSE")
        for bone in self._human.pose_bones:
            stretch_constraints = [
                c for c in bone.constraints if c.type == "STRETCH_TO"
            ]

            for c in stretch_constraints:
                bone.constraints.remove(c)

        bpy.ops.object.mode_set(mode="EDIT")
        remove_list = []
        for bone in self._human.edit_bones:
            if bone.name.startswith("stretch"):
                remove_list.append(bone)

        for bone in remove_list:
            self._human.edit_bones.remove(bone)

        bpy.ops.object.mode_set(mode="OBJECT")

    def _add_applied_armature(self, obj):
        """Adds an armature modifier to the passed object, linking it to the passed
        rig

        Args:
            hg_rig (Object): HumGen armature
            obj (Object): object to add armature modifier to
        """
        bpy.context.view_layer.objects.active = self._human.rig_obj
        obj.select_set(True)

        armature = obj.modifiers.new("Armature", "ARMATURE")
        armature.object = self._human.rig_obj

        bpy.context.view_layer.objects.active = obj
        # use old method for versions older than 2.90
        if (2, 90, 0) > bpy.app.version:
            while obj.modifiers.find("Armature") != 0:
                bpy.ops.object.modifier_move_up(
                    {"object": obj}, modifier="Armature"
                )
        else:
            bpy.ops.object.modifier_move_to_index(modifier="Armature", index=0)

        bpy.context.view_layer.objects.active = self._human.rig_obj

    def _remove_teeth_constraint(self):
        """Remove child_of constraints from the teeth

        Args:
            hg_rig (Object): HumGen armature
        """
        p_bones = self._human.pose_bones
        p_bones["jaw"].constraints["Damped Track"].mute = False

        for bone in [p_bones["jaw"], p_bones["jaw_upper"]]:
            child_constraints = [
                c for c in bone.constraints if c.type == "CHILD_OF"
            ]
            for c in child_constraints:
                bone.constraints.remove(c)

    def _set_teeth_parent(self):
        """Sets the head bone as parent of the jaw bones

        Args:
            hg_rig (Object): HumGen armature
        """
        bpy.ops.object.mode_set(mode="EDIT")
        e_bones = self._human.edit_bones
        for b_name in ["jaw", "jaw_upper"]:
            e_bones[b_name].parent = e_bones["head"]
        bpy.ops.object.mode_set(mode="OBJECT")
