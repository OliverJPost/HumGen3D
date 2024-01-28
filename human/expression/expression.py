# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements class for manipulating human expression or face rig."""

import json
import os
from typing import TYPE_CHECKING

import bpy
import numpy as np
from HumGen3D.common.type_aliases import C
from HumGen3D.human.keys.keys import ShapeKeyItem

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.backend import get_prefs, remove_broken_drivers
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.human.common_baseclasses.pcoll_content import PreviewCollectionContent

FACE_RIG_BONE_NAMES = [
    "brow_inner_up",
    "pucker_cheekPuf",
    "jaw_dwn_mouth_clsd",
    "jaw_open_lt_rt_frwd",
    "brow_dwn_L",
    "eye_blink_open_L",
    "eye_squint_L",
    "brow_outer_up_L",
    "nose_sneer_L",
    "cheek_squint_L",
    "mouth_smile_frown_L",
    "mouth_stretch_L",
    "brow_dwn_R",
    "brow_outer_up_R",
    "eye_blink_open_R",
    "eye_squint_R",
    "cheek_squint_R",
    "mouth_smile_frown_R",
    "mouth_stretch_R",
    "nose_sneer_R",
    "brow_inner_up",
    "pucker_cheekPuf",
    "mouth_shrug_roll_upper",
    "mouth_lt_rt_funnel",
    "mouth_roll_lower",
    "jaw_dwn_mouth_clsd",
    "jaw_open_lt_rt_frwd",
    "brow_dwn_L",
    "eye_blink_open_L",
    "eye_squint_L",
    "brow_outer_up_L",
    "nose_sneer_L",
    "cheek_squint_L",
    "mouth_dimple_L",
    "mouth_smile_frown_L",
    "mouth_upper_up_L",
    "mouth_lower_down_L",
    "mouth_stretch_L",
    "brow_dwn_R",
    "brow_outer_up_R",
    "eye_blink_open_R",
    "eye_squint_R",
    "cheek_squint_R",
    "mouth_dimple_R",
    "mouth_lower_down_R",
    "mouth_upper_up_R",
    "mouth_smile_frown_R",
    "mouth_stretch_R",
    "nose_sneer_R",
    "tongue_out_lt_rt_up_dwn",
]


class ExpressionSettings(PreviewCollectionContent):
    """Class for manipulating human expression.

    Either using 1-click expressions or with the facial rig.
    """

    def __init__(self, _human: "Human") -> None:
        self._human = _human
        self._pcoll_name = "expression"
        self._pcoll_gender_split = False

    @property
    def has_facial_rig(self) -> bool:
        return "facial_rig" in self._human.objects.body

    @property
    def keys(self) -> list[ShapeKeyItem]:
        """Filtered list from HumGen3D.human.keys for keys part of expressions.

        Returns:
            list[ShapeKeyItem]: List of shape keys that are on this human and of type
                expression.
        """
        return self._human.keys.filtered("expressions")

    def set(self, preset: str) -> None:  # noqa: A003
        """Loads the passed 1-click expression preset on the human.

        This will import the shapekey from the .npz file and set the value to 1.0.

        Args:
            preset (str): Preset to load. You can get a list of available presets
                with `get_options()`.
        """
        pref = get_prefs()

        if preset == "none":
            return

        self._active = preset

        sk_name, _ = os.path.splitext(os.path.basename(preset))

        filepath = os.path.join(pref.filepath, preset)

        hg_rig = self._human.objects.rig
        hg_body = hg_rig.HG.body_obj
        sk_names = [sk.name for sk in hg_body.data.shape_keys.key_blocks]

        if "expr_{}".format(sk_name) in sk_names:
            new_key = hg_body.data.shape_keys.key_blocks["expr_{}".format(sk_name)]
        else:
            new_key = self._human.keys.load_from_npz(filepath)
            new_key.name = "e_" + new_key.name

        for sk in self.keys:
            sk.value = 0

        new_key.mute = False
        new_key.value = 1

    @injected_context
    def load_facial_rig(self, context: C = None) -> None:
        """Imports all necessary shape keys and unhides the bones used to control face.

        Args:
            context (C): Blender context. bpy.context if not provided.
        """
        for b_name in FACE_RIG_BONE_NAMES:
            bone = self._human.pose.get_posebone_by_original_name(b_name).bone
            bone.hide = False

        for key in self._human.expression.keys:
            key.value = 0

        self._load_FACS_sks(context)  # type:ignore[arg-type]

        self._human.objects.body["facial_rig"] = 1  # type:ignore[index]

    def remove_facial_rig(self) -> None:
        """Remove the facial rig from the human, including all it's shape keys.

        Will also hide the bones again.

        Raises:
            HumGenException: If no facial rig is loaded on this human.
        """
        if "facial_rig" not in self._human.objects.body:  # type:ignore[operator]
            raise HumGenException("No facial rig found on this human")

        # TODO give bones custom property if they're part of the face rig
        for b_name in FACE_RIG_BONE_NAMES:
            bone = self._human.pose.get_posebone_by_original_name(b_name).bone
            bone.hide = True

        # TODO this is a bit heavy if we don't need the coordinates
        json_path = os.path.join(get_prefs().filepath, "models", "face_rig.json")
        with open(json_path, "r") as f:
            data = json.load(f)

        for sk_name in data["teeth"]:
            key_blocks = self._human.objects.lower_teeth.data.shape_keys.key_blocks
            sk = key_blocks.get(sk_name)
            self._human.objects.lower_teeth.shape_key_remove(sk)

        for sk_name in data["body"]:
            sk = self._human.keys.get(sk_name)
            self._human.objects.body.shape_key_remove(sk.as_bpy())

        del self._human.objects.body["facial_rig"]

        remove_broken_drivers()

    def _load_FACS_sks(self, context: bpy.types.Context) -> None:
        """Imports the needed FACS shapekeys to be used by the rig."""  # noqa
        json_path = os.path.join(get_prefs().filepath, "models", "face_rig.json")
        with open(json_path, "r") as f:
            data = json.load(f)

        body = self._human.objects.body
        teeth = self._human.objects.lower_teeth

        for obj, object_type in ((body, "body"), (teeth, "teeth")):
            all_sks = data[object_type]
            vert_co = np.empty(len(obj.data.vertices) * 3, dtype=np.float64)
            obj.data.vertices.foreach_get("co", vert_co)

            try:
                obj.data.shape_keys.key_blocks["Basis"]
            except AttributeError:
                obj.shape_key_add(name="Basis")

            for sk_name, sk_data in all_sks.items():
                sk = obj.shape_key_add(name=sk_name)
                sk.interpolation = "KEY_LINEAR"

                relative_sk_co = np.array(sk_data["relative_coordinates"])
                adjusted_vert_co = vert_co + relative_sk_co

                sk.data.foreach_set("co", adjusted_vert_co)

                self._human.keys._add_driver(sk, sk_data)
