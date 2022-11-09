# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Module containing ClothingSettings class for adding/modifying human's clothing."""

from typing import TYPE_CHECKING, Literal

import bpy
from HumGen3D.common.type_aliases import C

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.common.decorators import injected_context

from .base_clothing import BaseClothing


class OutfitSettings(BaseClothing):
    """Class for adding/changing the outfit of a human.

    Most of the functionality of this class comes from the [[BaseClothing]] class,
    since outfits and footwear work the same.
    """

    def __init__(self, human: "Human") -> None:
        """Create new instance to change outfit of human.

        Args:
            human (Human): Human instance.
        """
        self._human = human
        self._pcoll_name = "outfit"
        self._pcoll_gender_split = True

    @property
    def objects(self) -> list[bpy.types.Object]:
        """Get a list of the objects this human's outfit consists of.

        Returns:
            list[bpy.types.Object]: List of Blender outfit objects on this human.
        """
        return [obj for obj in self._human.objects if "cloth" in obj]

    @injected_context
    def add_obj(
        self,
        cloth_obj: bpy.types.Object,
        cloth_type: Literal["pants", "top", "full"],
        context: C = None,
    ) -> None:
        """Add an object you created yourself as footwear to this human.

        Args:
            cloth_obj (bpy.types.Object): Blender object to add as footwear. Make
                sure it's located in the correct place (on the feet of this human).
            cloth_type (Literal["pants", "top", "full"]): What part of the body
                this clothing item covers. This influences what corrective shapekeys
                are added to the item.
            context (C): Blender context. bpy.context if not provided.
        """
        super().add_obj(cloth_obj, cloth_type, context)
