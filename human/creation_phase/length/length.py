import json
import os
from typing import TYPE_CHECKING

import bpy
from bpy.types import Context

if TYPE_CHECKING:
    from HumGen3D import Human

import numpy as np


def apply_armature(obj):
    """Applies all armature modifiers on this object

    Args:
        obj (Object): object to apply armature modifiers on
    """
    bpy.context.view_layer.objects.active = obj
    armature_mods = [mod.name for mod in obj.modifiers if mod.type == "ARMATURE"]
    for mod_name in armature_mods:
        bpy.ops.object.modifier_apply(modifier=mod_name)


class LengthSettings:
    def __init__(self, human):
        self._human = human

    @property
    def centimeters(self) -> int:
        return int(self.meters * 100)

    @property
    def meters(self) -> float:
        return self._human.rig_obj.dimensions[2]

    def set(self, value_cm: float, context: Context = None):
        if context.scene.HG3D.update_exception:
            return

        multiplier = ((2 * value_cm) / 100 - 4) * -1
        old_length = self._human.rig_obj.dimensions[2]

        __location__ = os.path.realpath(
            os.path.join(os.getcwd(), os.path.dirname(__file__))
        )
        with open(os.path.join(__location__, "stretch_bones.json"), "r") as f:
            stretch_bone_dict = json.load(f)

        bones = self._human.rig_obj.pose.bones

        for stretch_bone, bone_data in stretch_bone_dict.items():
            self._set_stretch_bone_position(multiplier, bones, stretch_bone, bone_data)

        context.view_layer.update()  # Requires update to get new length of rig
        hg_rig = (
            self._human.rig_obj
        )  # Human.find(context.active_object).rig_obj  # Retrieve again
        new_length = hg_rig.dimensions[2]
        hg_rig.location[2] += self._origin_correction(
            old_length
        ) - self._origin_correction(new_length)

    def _set_stretch_bone_position(self, multiplier, bones, stretch_bone, bone_data):
        """Sets the position of this stretch bone according along the axis between
        'max_loc' and 'min_loc', based on passed multiplier

        Args:
            multiplier (float): value between 0 and 1, where 0 is 'min_loc' and
                1 is 'max_loc' #CHECK if this is correct
            bones (PoseBone list): list of all posebones on hg_rig
            stretch_bone (str): name of stretch bone to adjust
            bone_data (dict): dict passed on from stretch_bone_dict containing
                symmetry and transformation data (see _get_stretch_bone_dict.__doc__)
        """
        # TODO cleanup

        if bone_data["sym"]:
            bone_list = [
                bones[f"{stretch_bone}.R"],
                bones[f"{stretch_bone}.L"],
            ]
        else:
            bone_list = [
                bones[stretch_bone],
            ]

        xyz_substracted = np.subtract(bone_data["max_loc"], bone_data["min_loc"])
        xyz_multiplied = tuple([multiplier * x for x in xyz_substracted])
        x_y_z_location = np.subtract(bone_data["max_loc"], xyz_multiplied)

        for b in bone_list:
            b.location = x_y_z_location

    def _origin_correction(self, length):
        # TODO DOCUMENT
        return -0.553 * length + 1.0114

    def apply(self, context):
        """
        Applies the pose to the rig, Also sets the correct origin position

        Args:
            hg_rig (Object): Armature of HumGen human
        """
        hg_rig = self._human.rig_obj
        rig_length = hg_rig.dimensions[2]

        bpy.context.view_layer.objects.active = hg_rig
        bpy.ops.object.mode_set(mode="POSE")
        bpy.ops.pose.armature_apply(selected=False)

        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        for obj in bpy.context.selected_objects:
            obj.select_set(False)

        self._correct_origin(context, hg_rig, hg_rig.HG.body_obj)

        bpy.context.view_layer.objects.active = hg_rig

    def _correct_origin(self, context, obj_to_correct, hg_body):
        """Uses a formula to comensate the origina position for legnth changes"""
        context.scene.cursor.location = obj_to_correct.location

        bottom_vertex_loc = (
            hg_body.matrix_world @ hg_body.data.vertices[21085].co
        )  # RELEASE check if this is still the bottom vertex

        context.scene.cursor.location[2] = bottom_vertex_loc[2]

        context.view_layer.objects.active = obj_to_correct
        obj_to_correct.select_set(True)
        bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
