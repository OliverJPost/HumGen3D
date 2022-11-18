# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements class for changing the height of the human."""

import random
from typing import TYPE_CHECKING, cast

import bpy
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.geometry import world_coords_from_obj
from HumGen3D.common.type_aliases import C
from HumGen3D.human.keys.key_slider_update import HG3D_OT_SLIDER_SUBSCRIBE
from mathutils import Vector

from ...common.math import centroid

if TYPE_CHECKING:
    from HumGen3D import Human

import numpy as np


def apply_armature(obj: bpy.types.Object) -> None:
    """Applies all armature modifiers on this object.

    Args:
        obj (Object): object to apply armature modifiers on
    """
    bpy.context.view_layer.objects.active = obj
    armature_mods = [mod.name for mod in obj.modifiers if mod.type == "ARMATURE"]
    for mod_name in armature_mods:
        bpy.ops.object.modifier_apply(modifier=mod_name)


class HeightSettings:
    """Class for changing height of human."""

    def __init__(self, human: "Human") -> None:
        self._human: "Human" = human

    @property
    def centimeters(self) -> int:
        """Height of human in centimeters.

        Returns:
            int: Height of human in centimeters.
        """
        return int(self.meters * 100)

    @property
    def meters(self) -> float:
        """Height of human in meters.

        Returns:
            float: Height of human in meters.
        """
        rig_obj = self._human.objects.rig

        top_coord = rig_obj.data.bones["head"].tail_local.z
        bottom_coord = rig_obj.data.bones["heel.02.L"].tail_local.z

        return cast(float, top_coord - bottom_coord)

    @injected_context
    def set(  # noqa: A003
        self, value_cm: float, context: C = None, realtime: bool = False
    ) -> None:  # noqa A001
        """Sets height of human.

        Args:
            value_cm (float): Height of human in centimeters.
            context (C): Blender context. Defaults to None.
            realtime (bool): Whether to update the human in realtime. Only
                needed for sliders in the UI. Defaults to False.
        """
        if context.scene.HG3D.update_exception:
            return

        if value_cm > 184:
            value = (value_cm - 184) / (200 - 184)
            livekey_name = "height_200"
        else:
            value = -((value_cm - 150) / (184 - 150) - 1)
            livekey_name = "height_150"

        if not value:
            return

        if realtime and not HG3D_OT_SLIDER_SUBSCRIBE.is_running():
            context.scene.HG3D.slider_is_dragging = True
            bpy.ops.hg3d.slider_subscribe("INVOKE_DEFAULT", hide_armature=True)

        self.name = livekey_name
        if realtime:
            self._human.keys[livekey_name].as_bpy().value = value
        else:
            self._human.keys[livekey_name].value = value
            self._correct_armature(context)
            self._correct_eyes()
            self._correct_teeth()
            for cloth_obj in self._human.clothing.outfit.objects:
                self._human.clothing.outfit.deform_cloth_to_human(context, cloth_obj)
            for shoe_obj in self._human.clothing.footwear.objects:
                self._human.clothing.footwear.deform_cloth_to_human(context, shoe_obj)

    def as_dict(self) -> dict[str, float]:
        """Returns height of human as dictionary.

        Returns:
            dict[str, float]: Height of human as dictionary.
        """
        return {"set": self.centimeters}

    @injected_context
    def set_from_dict(self, data: dict[str, float], context: C = None) -> list[str]:
        """Sets height of human from dictionary.

        Args:
            data (dict[str, float]): Dictionary with height of human.
            context (C): Blender context. Defaults to None.

        Returns:
            list[str]: List of occurred errors.
        """
        self.set(data["set"], context)

        return []

    @injected_context
    def _correct_armature(self, context: C = None) -> None:
        """Corrects armature to fit the new height.

        Args:
            context (C): Blender context. bpy.context if not provided.
        """
        # FIXME symmetry
        body = self._human.objects.body
        rig = self._human.objects.rig

        vert_count = len(body.data.vertices)
        body_key_coords = np.empty(vert_count * 3, dtype=np.float64)
        self._human.objects.body.data.vertices.foreach_get("co", body_key_coords)

        permanent_key_coords = np.empty(vert_count * 3, dtype=np.float64)
        self._human.keys.permanent_key.data.foreach_get("co", permanent_key_coords)

        temp_key_coords = np.empty(vert_count * 3, dtype=np.float64)
        self._human.keys.temp_key.data.foreach_get("co", temp_key_coords)
        temp_value = self._human.keys.temp_key.value

        eval_coords = (
            temp_key_coords - body_key_coords
        ) * temp_value + permanent_key_coords
        eval_coords = eval_coords.reshape((-1, 3))

        # Context override for mode_set does not work, see #T88051
        old_active = context.view_layer.objects.active
        rig.hide_viewport = False
        rig.hide_set(False)
        context.view_layer.objects.active = rig
        selected_objects = context.selected_objects
        for obj in selected_objects:
            obj.select_set(False)
        rig.select_set(True)

        bpy.ops.object.mode_set(mode="EDIT")
        for ebone in rig.data.edit_bones:
            if "head_verts" not in ebone:
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
        rig.select_set(False)
        for obj in selected_objects:
            obj.select_set(True)

    @injected_context
    def randomize(self, context: C = None) -> None:
        """Randomize human height.

        Args:
            context (C): Blender context. bpy.context if not provided.
        """
        chosen_height_cm = random.uniform(150, 200)
        self.set(chosen_height_cm, context)

    def _correct_eyes(self) -> None:
        """Corrects eyes to fit the new height."""
        eye_obj = self._human.objects.eyes

        body_world_coords = world_coords_from_obj(
            self._human.objects.body, data=self._human.keys.all_deformation_shapekeys
        )
        eye_width = np.linalg.norm(body_world_coords[1109] - body_world_coords[7010])
        eye_size_value = 94 * eye_width - 2.0
        sks = self._human.objects.eyes.data.shape_keys.key_blocks
        sks["eyeball_size"].value = eye_size_value

        eye_vert_count = len(eye_obj.data.vertices)
        eye_verts = np.empty(eye_vert_count * 3, dtype=np.float64)
        if eye_obj.data.shape_keys:
            eye_obj.data.shape_keys.key_blocks["Basis"].data.foreach_get(
                "co", eye_verts
            )
        else:
            eye_obj.data.vertices.foreach_get("co", eye_verts)
        eye_verts = eye_verts.reshape((-1, 3))

        eye_verts_right, eye_verts_left = np.split(eye_verts, 2)
        eye_verts_right, eye_verts_left = eye_verts_right.copy(), eye_verts_left.copy()

        armature = self._human.objects.rig.data
        left_head_co = armature.bones.get("eyeball.L").tail_local
        right_head_co = armature.bones.get("eyeball.R").tail_local

        reference_left = centroid(eye_verts_left) + Vector((0.001, -0.0175, 0.0))
        reference_right = centroid(eye_verts_right) + Vector((-0.001, -0.0175, 0.0))

        transformation_left = np.array(left_head_co - reference_left)
        transformation_right = np.array(right_head_co - reference_right)

        eye_verts_left += transformation_left
        eye_verts_right += transformation_right

        eye_verts_corrected = np.concatenate((eye_verts_right, eye_verts_left))

        eye_verts_displacement = eye_verts_corrected - eye_verts
        eye_verts_displacement = eye_verts_displacement.reshape((-1))

        if eye_obj.data.shape_keys:
            for key in eye_obj.data.shape_keys.key_blocks:
                orig_key_data = np.empty(eye_vert_count * 3, dtype=np.float64)
                key.data.foreach_get("co", orig_key_data)
                key_corrected = orig_key_data + eye_verts_displacement
                key.data.foreach_set("co", key_corrected)
                key.data.update()
        else:
            eye_obj.data.vertices.foreach_set("co", eye_verts_corrected.reshape((-1)))

    def _correct_teeth(self) -> None:
        """Corrects teeth to fit the new height."""
        armature = self._human.objects.rig.data
        teeth_obj_lower = self._human.objects.lower_teeth
        teeth_obj_upper = self._human.objects.upper_teeth

        self._correct_teeth_obj(
            teeth_obj_lower, "jaw", Vector((-0.0000, 0.0128, 0.0075)), armature
        )
        self._correct_teeth_obj(
            teeth_obj_upper, "jaw_upper", Vector((-0.0000, 0.0247, -0.0003)), armature
        )

    @staticmethod
    def _correct_teeth_obj(
        obj: bpy.types.Object,
        bone_name: str,
        reference_vector: Vector,
        armature: bpy.types.Armature,
    ) -> None:
        vert_count = len(obj.data.vertices)
        verts = np.empty(vert_count * 3, dtype=np.float64)
        obj.data.vertices.foreach_get("co", verts)
        verts = verts.reshape((-1, 3))

        reference_bone_tail_co = armature.bones.get(bone_name).tail_local
        transformation = np.array(
            reference_bone_tail_co - centroid(verts) + reference_vector  # type:ignore
        )

        verts += transformation

        verts = verts.reshape((-1))
        obj.data.vertices.foreach_set("co", verts)
        obj.data.update()
