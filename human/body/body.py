# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Module containing subpart of Human class to edit body proportions of the human."""

import random
from typing import TYPE_CHECKING, Union, cast

from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C

if TYPE_CHECKING:
    from HumGen3D import Human
    from HumGen3D.human.keys.keys import LiveKeyItem, ShapeKeyItem


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
    def randomize(self, context: C = None) -> None:
        """Randomizes the values of the body keys of this human.

        Uses a random value retreived from a normal distrubition with mean 0 and sigma
        of 0.5.

        Args:
            context (C): Blender context
        """
        for key in self.keys:
            if key.name == "skinny":
                key.set_without_update(random.uniform(0, 0.7))
            else:
                key.set_without_update(random.uniform(0, 1.0))

        self._human.keys.update_human_from_key_change(context)

    def __hash__(self) -> int:
        sk_values = [sk.value for sk in self._human.body.keys]

        return hash(tuple(sk_values))
