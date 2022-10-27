# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import random
from typing import TYPE_CHECKING, Union, cast

from HumGen3D.common.type_aliases import C
from HumGen3D.common.decorators import injected_context

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

    @injected_context
    def randomize(self, context: C = None) -> None:
        """Randomizes the body type sliders of the active human.

        Args:
            hg_rig (Object): HumGen armature
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
