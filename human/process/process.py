# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE


import json
from typing import TYPE_CHECKING, Optional

from .lod import LodSettings

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from .bake import BakeSettings


class ProcessSettings:
    def __init__(self, human: "Human") -> None:
        self._human = human

    @property
    def baking(self) -> BakeSettings:
        return BakeSettings(self._human)

    @property
    def lod(self) -> LodSettings:
        return LodSettings(self._human)

    def rename_bones_from_json(
        self, json_string: Optional[str] = None, json_path: Optional[str] = None
    ) -> None:
        if json_path and json_string:
            raise ValueError("Only one of json_string and json_path may be provided.")
        if json_path:
            with open(json_path, "r") as f:
                data = json.load(f)
        else:
            data = json.loads(json_string)  # type:ignore

        left_suffix = data["suffix_L"]
        right_suffix = data["suffix_R"]

        for bone_name, new_name in data.items():
            matching_bones = [
                bone
                for bone in self._human.pose_bones
                if bone["original_name"].startswith(bone_name)
            ]
            if len(matching_bones) == 2:
                left_bone = next(
                    b
                    for b in matching_bones
                    if b["original_name"].endswith((".L", "_L"))
                )
                right_bone = next(
                    b
                    for b in matching_bones
                    if b["original_name"].endswith((".R", "_R"))
                )
                left_bone.name = new_name + left_suffix
                right_bone.name = new_name + right_suffix
            elif len(matching_bones) == 1:
                matching_bones[0].name = new_name
