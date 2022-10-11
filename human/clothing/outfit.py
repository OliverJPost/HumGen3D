# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from typing import TYPE_CHECKING
import bpy
from HumGen3D.backend.type_aliases import C

if TYPE_CHECKING:
    from HumGen3D.human.human import Human
from HumGen3D.human.base.decorators import injected_context

from .base_clothing import BaseClothing


class OutfitSettings(BaseClothing):
    def __init__(self, human: "Human") -> None:
        self._human = human
        self._pcoll_name = "outfit"
        self._pcoll_gender_split = True

    @property
    def objects(self) -> list[bpy.types.Object]:
        return [obj for obj in self._human.objects if "cloth" in obj]

    @injected_context
    def add_obj(
        self, cloth_obj: bpy.types.Object, cloth_type: str, context: C = None
    ) -> None:
        super().add_obj(cloth_obj, cloth_type, context)
