from typing import TYPE_CHECKING

import bpy

if TYPE_CHECKING:
    from HumGen3D import Human


class BodySettings:
    def __init__(self, human):
        self._human: Human = human

    def set_experimental(self, turn_on: bool) -> None:
        sk_max_value = 2 if turn_on else 1
        sk_min_value_ff = -2 if turn_on else 2
        sk_min_value_body = -0.5 if turn_on else 0

        for sk in self._human.shape_keys:
            # Facial shape keys
            if sk.name.startswith("ff_"):
                sk.slider_min = sk_min_value_ff
                sk.slider_max = sk_max_value
            # Body proportion shape keys
            elif sk.name.startswith("bp_"):
                sk.slider_min = sk_min_value_body
                sk.slider_max = sk_max_value
            # Preset shape keys
            elif sk.name.startswith("pr_"):
                sk.slider_min = sk_min_value_body
                sk.slider_max = sk_max_value

        self._human.properties.experimental = turn_on
