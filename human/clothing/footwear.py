# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from typing import TYPE_CHECKING
import bpy
from HumGen3D.common.type_aliases import C

if TYPE_CHECKING:
    from HumGen3D.human.human import Human
from HumGen3D.common.decorators import injected_context

from .base_clothing import BaseClothing


class FootwearSettings(BaseClothing):
    def __init__(self, human: "Human") -> None:
        """Create new instance to manipulate footwear of human."""
        self._human = human
        self._pcoll_name = "footwear"
        self._pcoll_gender_split = True

    @property
    def objects(self) -> list[bpy.types.Object]:
        return [
            obj for obj in self._human.objects if "shoe" in obj  # type:ignore[operator]
        ]

    @injected_context
    def add_obj(self, cloth_obj: bpy.types.Object, context: C = None) -> None:
        super().add_obj(cloth_obj, "footwear", context)
