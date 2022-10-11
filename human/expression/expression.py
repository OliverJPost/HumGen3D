# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import json
import os
from typing import TYPE_CHECKING

import bpy
import numpy as np
from HumGen3D.backend.type_aliases import C

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.backend import get_prefs, hg_delete, remove_broken_drivers
from HumGen3D.human.base.decorators import injected_context
from HumGen3D.human.base.drivers import build_driver_dict
from HumGen3D.human.base.exceptions import HumGenException
from HumGen3D.human.base.pcoll_content import PreviewCollectionContent
from HumGen3D.human.base.prop_collection import PropCollection
from HumGen3D.human.height.height import apply_armature
from HumGen3D.human.keys.keys import ShapeKeyItem, apply_shapekeys, transfer_shapekey

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
    def __init__(self, _human: "Human") -> None:
        self._human = _human
        self._pcoll_name = "expression"
        self._pcoll_gender_split = False

    @property
    def shape_keys(self) -> list[ShapeKeyItem]:
        return self._human.keys.filtered("expression")

    def set(self, preset: str) -> None:
        """Loads the active expression in the preview collection"""
        pref = get_prefs()

        if preset == "none":
            return
        sk_name, _ = os.path.splitext(os.path.basename(preset))

        filepath = str(pref.filepath) + str(preset)

        hg_rig = self._human.rig_obj
        hg_body = hg_rig.HG.body_obj
        sk_names = [sk.name for sk in hg_body.data.shape_keys.key_blocks]

        if "expr_{}".format(sk_name) in sk_names:
            new_key = hg_body.data.shape_keys.key_blocks["expr_{}".format(sk_name)]
        else:
            new_key = self._human.keys.load_from_npy(filepath)
            new_key.name = "expr_" + new_key.name

        for sk in self.shape_keys:
            sk.value = 0

        new_key.mute = False
        new_key.value = 1

    @injected_context
    def load_facial_rig(self, context: C = None) -> None:

        for b_name in FACE_RIG_BONE_NAMES:
            b = self._human.pose_bones[b_name]  # type:ignore[index]
            b.bone.hide = False

        for sk in self._human.keys:
            if sk.name.startswith("expr"):
                sk.mute = True

        self._load_FACS_sks(context)  # type:ignore[arg-type]

        self._human.body_obj["facial_rig"] = 1  # type:ignore[index]

    def _load_FACS_sks(self, context: bpy.types.Context) -> None:
        """Imports the needed FACS shapekeys to be used by the rig"""

        json_path = os.path.join(get_prefs().filepath, "models", "face_rig.json")
        with open(json_path, "r") as f:
            data = json.load(f)

        body = self._human.body_obj
        teeth = self._human.lower_teeth_obj

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

    def remove_facial_rig(self) -> None:
        if "facial_rig" not in self._human.body_obj:  # type:ignore[operator]
            raise HumGenException("No facial rig found on this human")

        # TODO give bones custom property if they're part of the face rig
        for b_name in FACE_RIG_BONE_NAMES:
            b = self._human.pose_bones[b_name]  # type:ignore[index]
            b.bone.hide = True

        # TODO this is a bit heavy if we don't need the coordinates
        json_path = os.path.join(get_prefs().filepath, "models", "face_rig.json")
        with open(json_path, "r") as f:
            data = json.load(f)

        for sk_name in data["teeth"]:
            sk = self._human.lower_teeth_obj.data.shape_keys.key_blocks.get(sk_name)
            self._human.lower_teeth_obj.shape_key_remove(sk)

        for sk_name in data["body"]:
            sk = self._human.keys.get(sk_name)
            self._human.body_obj.shape_key_remove(sk.as_bpy())

        del self._human.body_obj["facial_rig"]

        remove_broken_drivers()
