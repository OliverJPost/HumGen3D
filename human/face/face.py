# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements class for manipulating facial proportions of human."""

from typing import TYPE_CHECKING, List, Union

import numpy as np
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.human.keys.keys import LiveKeyItem, ShapeKeyItem

from ..common_baseclasses.prop_collection import PropCollection


class FaceSettings(PropCollection):
    """Class for manipulating the facial proportions of the human."""

    def __init__(self, human: "Human") -> None:
        self._human = human

    @property
    def keys(self) -> List[Union[LiveKeyItem, ShapeKeyItem]]:
        """Filtered subset of human.keys for keys related to facial proportions.

        Returns:
            List[Union[LiveKeyItem, ShapeKeyItem]]: Keys related to facial proportions.
        """
        return self._human.keys.filtered("face_proportions")

    @injected_context
    def reset(self, context: C = None) -> None:
        """Reset all facial proportions to 0.

        Args:
            context (C): Blender context. bpy.context if not provided.
        """
        for key in self.keys:
            if hasattr(key, "set_without_update"):
                key.set_without_update(0)
            else:
                key.value = 0

        self._human.keys.update_human_from_key_change(context)

    @injected_context
    def randomize(
        self, subcategory: str = "all", use_bell_curve: bool = False, context: C = None
    ) -> None:
        """Randomize facial proportions.

        Args:
            subcategory (str): Subcategory of facial proportions to randomize. Defaults
                to "all".
            use_bell_curve (bool): Whether to use a bell curve for randomization.
            context (C): Blender context. bpy.context if not provided.
        """
        if subcategory.lower() == "all":
            keys = [key for key in self.keys if key.subcategory != "special"]
        else:
            keys = [key for key in self.keys if key.subcategory == subcategory]
        all_v = 0.0
        for key in keys:
            if use_bell_curve:
                new_value = np.random.normal(loc=0, scale=0.5)
            else:
                new_value = np.random.normal(loc=0, scale=0.5)
            all_v += new_value
            key.set_without_update(new_value)

        self._human.keys.update_human_from_key_change(context)
