# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Module containing subpart of Human class to edit body proportions of the human."""

import random
from typing import TYPE_CHECKING, Union, cast

import bpy

from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C

if TYPE_CHECKING:
    from HumGen3D import Human
    from HumGen3D.human.keys.keys import LiveKeyItem, ShapeKeyItem

ALL = "ALL"


class BodySettings:
    """Class to edit body proportions of the human.

    The body proportions are changed by changing the values of the LiveKeys stored
    in the folder `livekeys/body_proportions`. These are accessible in the API under
    `human.body.keys`.

    Note: By default Human Generator does not come with shape keys for changing body
    proportions, but either by users converting them or by new 3rd party packs adding
    them you can expect shape keys too.

    For more info on LiveKeys see [[LiveKeys]].
    """

    def __init__(self, human: "Human") -> None:
        """Initiate instance for modifying body of human.

        Args:
            human (Human): Human instance.
        """
        self._human: "Human" = human

    @property
    def keys(self) -> list[Union["ShapeKeyItem", "LiveKeyItem"]]:
        """Access ShapeKeyItems and LiveKeyItems for changing body proportions.

        Gets all LiveKeyItems and ShapeKeyItems from the global Human Generator
        key collection (`Human.keys.all_keys`) that belong to the body proportion
        category.

        Returns:
            list[Union[ShapeKeyItem, LiveKeyItem]]: List of all keys that belong to the
                body proportions category.
        """
        return cast(
            list[Union["ShapeKeyItem", "LiveKeyItem"]],
            self._human.keys.filtered("body_proportions"),
        )

    @injected_context
    def randomize(
        self, category: str = ALL, use_locks: bool = False, context: C = None
    ) -> None:
        """Randomizes the values of the body keys of this human.

        Uses a random value retreived from a normal distrubition with mean 0 and sigma
        of 0.5.

        Args:
            category (str, optional): Category of keys to randomize. Defaults to ALL.
            use_locks (bool, optional): Whether to use locks shown in UI. Defaults to False.
            context (C): Blender context
        """
        locks = bpy.context.scene.HG3D.locks

        for key in self.keys:
            if category != ALL and key.subcategory != category:
                continue

            if key.subcategory.lower() == "main":
                random_value = random.uniform(0, 1.0)
                if hasattr(key, "set_without_update"):
                    key.set_without_update(random_value)
                else:
                    key.value = random_value
                continue
            if key.subcategory.lower() == "special" or "length" in key.name.lower():
                continue

            # Skip if category is locked
            if getattr(locks, key.subcategory, False) and use_locks:
                continue

            std_deviation = 0.1 if category == ALL else 0.5
            random_value = random.normalvariate(0, std_deviation)
            if hasattr(key, "set_without_update"):
                key.set_without_update(random_value)
            else:
                key.value = random_value

        self._human.keys.update_human_from_key_change(context)

    @injected_context
    def reset_values(self, context: C = None) -> None:
        """Reset all body keys to their default values.

        Args:
            context (C): Blender context
        """
        for key in self.keys:
            if hasattr(key, "set_without_update"):
                key.set_without_update(0)
            else:
                key.value = 0

        self._human.keys.update_human_from_key_change(context)

    def __hash__(self) -> int:
        sk_values = [sk.value for sk in self._human.body.keys]

        return hash(tuple(sk_values))
