# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import random
from typing import TYPE_CHECKING, Union, cast

if TYPE_CHECKING:
    from HumGen3D import Human
    from HumGen3D.human.keys.keys import LiveKeyItem, ShapeKeyItem


class BodySettings:
    def __init__(self, human: "Human") -> None:
        """Initiate instance for modifying body of human."""
        self._human: "Human" = human

    @property
    def keys(self) -> list[Union["ShapeKeyItem", "LiveKeyItem"]]:
        return cast(
            list[Union["ShapeKeyItem", "LiveKeyItem"]],
            self._human.keys.filtered("body_proportions"),
        )

    def randomize(self) -> None:
        """Randomizes the body type sliders of the active human.

        Args:
            hg_rig (Object): HumGen armature
        """
        for key in self.keys:
            if key.name == "skinny":
                key.value = random.uniform(0, 0.7)
            else:
                key.value = random.uniform(0, 1.0)

    def __hash__(self) -> int:
        sk_values = [sk.value for sk in self._human.body.keys]

        return hash(tuple(sk_values))
