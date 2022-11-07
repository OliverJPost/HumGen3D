# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Contains FootWearSettings class. Used for changing footwear of human."""

from typing import TYPE_CHECKING, Any

import bpy
from HumGen3D.common.type_aliases import C

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.common.decorators import injected_context

from .base_clothing import BaseClothing


class FootwearSettings(BaseClothing):
    """Interface class for adding/modifying footwear of human.

    Most of the functionality of this class comes from the [[BaseClothing]] class,
    since outfits and footwear work the same.
    """

    def __init__(self, human: "Human") -> None:
        """Create new instance to manipulate footwear of human.

        Args:
            human (Human): Human instance.
        """
        self._human = human
        self._pcoll_name = "footwear"
        self._pcoll_gender_split = True

    @property
    def objects(self) -> list[bpy.types.Object]:
        """Get a list of this human's Blender footwear objects. Usually only one.

        Returns:
            list[bpy.types.Object]: List of Blender footwear objects on this human.
        """
        return [
            obj for obj in self._human.objects if "shoe" in obj  # type:ignore[operator]
        ]

    @injected_context
    def add_obj(self, cloth_obj: bpy.types.Object, context: C = None) -> None:
        """Add an object you created yourself as footwear to this human.

        Args:
            cloth_obj (bpy.types.Object): Blender object to add as footwear. Make
                sure it's located in the correct place (on the feet of this human).
            context (C): Blender context. bpy.context if not provided.
        """
        super().add_obj(cloth_obj, "footwear", context)
