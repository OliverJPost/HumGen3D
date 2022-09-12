import json
import os
import random
from typing import TYPE_CHECKING

import bpy
from bpy.types import Context
from HumGen3D.human.base.decorators import injected_context
from mathutils import Vector

from ...scripts.bone_vert_builder import centroid
from ..base import live_keys  # type:ignore

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
        self._human: Human = human

    @property
    def centimeters(self) -> int:
        return int(self.meters * 100)

    @property
    def meters(self) -> float:
        return self._human.rig_obj.dimensions[2]

    @injected_context
    def correct_armature(self, context=None):
        body = self._human.body_obj
        rig = self._human.rig_obj

        vert_count = len(body.data.vertices)
        body_key_coords = np.empty(vert_count * 3, dtype=np.float64)
        self._human.body_obj.data.vertices.foreach_get("co", body_key_coords)

        permanent_key_coords = np.empty(vert_count * 3, dtype=np.float64)
        self._human.shape_keys.permanent_key.data.foreach_get(
            "co", permanent_key_coords
        )

        temp_key_coords = np.empty(vert_count * 3, dtype=np.float64)
        self._human.shape_keys.temp_key.data.foreach_get("co", temp_key_coords)
        temp_value = self._human.shape_keys.temp_key.value

        eval_coords = (
            temp_key_coords - body_key_coords
        ) * temp_value + permanent_key_coords
        eval_coords = eval_coords.reshape((-1, 3))

        # Context override for mode_set does not work, see #T88051
        old_active = context.view_layer.objects.active
        context.view_layer.objects.active = rig
        for obj in context.selected_objects:
            obj.select_set(False)
        rig.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        for ebone in rig.data.edit_bones:
            if not "head_verts" in ebone:
                continue

            target_verts_head = ebone["head_verts"]
            centroid_co = centroid(eval_coords[target_verts_head])
            vert_vec_head = Vector(ebone["head_relative_co"])

            ebone.head = centroid_co + vert_vec_head

            target_verts_tail = ebone["tail_verts"]
            centroid_co = centroid(eval_coords[target_verts_tail])
            vert_vec_tail = Vector(ebone["tail_relative_co"])

            ebone.tail = centroid_co + vert_vec_tail

        bpy.ops.object.mode_set(mode="OBJECT")
        context.view_layer.objects.active = old_active

    @injected_context
    def set(self, value_cm: float, context: Context = None, realtime=False):
        if context.scene.HG3D.update_exception:
            return

        value = 0

        if value_cm > 184:
            value = (value_cm - 184) / (200 - 184)
            livekey_name = "hg_taller"
        else:
            value = -((value_cm - 150) / (184 - 150) - 1)
            livekey_name = "hg_shorter"

        if not value:
            return

        if realtime and not context.scene.HG3D.slider_is_dragging:
            context.scene.HG3D.slider_is_dragging = True
            bpy.ops.hg3d.slider_subscribe("INVOKE_DEFAULT").subscribe_type = "ARMATURE"

        self.name = livekey_name
        self.path = os.path.join("livekeys", "body_proportions", livekey_name + ".npy")
        live_keys.set_livekey(self, value)

        if not realtime:
            self.correct_armature(context)

    @injected_context
    def randomize(self, context=None):
        chosen_length_cm = random.uniform(150, 200)
        self.set(chosen_length_cm, context)

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
