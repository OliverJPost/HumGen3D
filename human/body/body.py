# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import random
from typing import TYPE_CHECKING

import bpy
from HumGen3D.human.base.decorators import injected_context

if TYPE_CHECKING:
    from HumGen3D import Human


class BodySettings:
    def __init__(self, human):
        self._human: Human = human

    @property
    def keys(self):
        return self._human.keys.filtered("body_proportions")

    def randomize(self):
        """Randomizes the body type sliders of the active human

        Args:
            hg_rig (Object): HumGen armature
        """

        for sk in self._human.keys.body_proportions:
            if sk.name.startswith("bp_skinny"):
                sk.value = random.uniform(0, 0.7)
            else:
                sk.value = random.uniform(0, 1.0)

    @injected_context
    def set_bone_scale(self, scale, bone_type, context=None):
        sett = context.scene.HG3D
        if sett.update_exception:
            return

        sc = self._get_scaling_data(scale, bone_type)
        for bone_name in sc["bones"]:
            bone = self._human.rig_obj.pose.bones[bone_name]
            x = sc["x"]
            y = sc["x"] if sc["y"] == "copy" else sc["y"]
            z = sc["x"] if sc["z"] == "copy" else sc["z"]

            bone.scale = (
                x if sc["x"] else bone.scale[0],
                y if sc["y"] else bone.scale[1],
                z if sc["z"] else bone.scale[2],
            )

    def _get_scaling_data(self, scale, bone_type, return_whole_dict=False) -> dict:
        """Gets the scaling dict that determines how to scale this body part

        Args:
            bone_type (str): name of slider, which body part to scale
            sett (PropertyGRoup): HumGen props

        Returns:
            dict:
                key (str) 'x', 'y', 'z': local scaling axis
                    value (AnyType): float scaling factor or 'copy' if same as 'x'
                        scaling factor
                key (str) 'bones':
                    value (list of str): list of bone names to scale
        """

        scaling_dict = {
            "head": {
                "x": scale / 5 + 0.9,
                "y": "copy",
                "z": "copy",
                "bones": ["head"],
            },
            "neck": {
                "x": (scale + 2.5) / 3,
                "y": "copy",
                "z": "copy",
                "bones": ["neck"],
            },
            "chest": {
                "x": (scale + 2.5) / 3,
                "y": "copy",
                "z": "copy",
                "bones": ["spine.002", "spine.003"],
            },
            "shoulder": {
                "x": (scale + 2.5) / 3,
                "y": "copy",
                "z": "copy",
                "bones": ["shoulder.L", "shoulder.R"],
            },
            "breast": {
                "x": (scale + 2.5) / 3,
                "y": "copy",
                "z": "copy",
                "bones": ["breast.L", "breast.R"],
            },
            "forearm": {
                "x": (scale + 2.5) / 3,
                "y": "copy",
                "z": "copy",
                "bones": ["forearm.L", "forearm.R"],
            },
            "upper_arm": {
                "x": (scale + 2.5) / 3,
                "y": "copy",
                "z": "copy",
                "bones": ["upper_arm.L", "upper_arm.R"],
            },
            "hips": {
                "x": (scale + 2.5) / 3,
                "y": "copy",
                "z": "copy",
                "bones": ["spine.001", "spine"],
            },
            "thigh": {
                "x": (scale + 2.5) / 3,
                "y": "copy",
                "z": "copy",
                "bones": ["thigh.L", "thigh.R"],
            },
            "shin": {
                "x": (scale + 2.5) / 3,
                "y": "copy",
                "z": "copy",
                "bones": ["shin.L", "shin.R"],
            },
            "foot": {
                "x": (scale + 2.5) / 3,
                "y": "copy",
                "z": "copy",
                "bones": ["foot.L", "foot.R"],
            },
            "hand": {
                "x": (scale + 2.5) / 3,
                "y": "copy",
                "z": "copy",
                "bones": ["hand.L", "hand.R"],
            },
        }

        sc = scaling_dict[bone_type]
        if return_whole_dict:
            return scaling_dict
        else:
            return sc

    def adapt_rig_to_proportions(self) -> None:
        """Change the base pose of the rig to the new body proportions."""
        rig_obj = self._human.rig_obj
        body_obj = self._human.body_obj

        bpy.ops.object.mode_set(mode="EDIT")
        for ebone in rig_obj.edit_bones:
            head = ebone.head
            tail = ebone.tail

        bpy.ops.object.mode_set(mode="OBJECT")
