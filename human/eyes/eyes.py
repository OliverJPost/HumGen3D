# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import random
from typing import TYPE_CHECKING, Union, cast

from bpy.types import Material, Object
from HumGen3D.human.keys.keys import LiveKeyItem, ShapeKeyItem  # type:ignore

if TYPE_CHECKING:
    from HumGen3D.human.human import Human  # type:ignore

T_CLASS = [
    0x3F313B,  # T50
    0x633935,  # T30
    0x71533C,  # T17
    0xB26D55,  # T10
    0x41282C,  # T40
    0x6A4A47,  # T20
    0x8F7459,  # T15
    0xB37556,  # T07
]

D_CLASS = [
    0x988856,  # D60
    0x8A815A,  # D40
    0x7D8169,  # D34
    0x52564B,  # D20
    0xAE9B73,  # D50
    0xAC9B74,  # D37
    0x9E945C,  # D30
    0x577377,  # D10
]

C_CLASS = [
    0x747C7F,  # C40
    0x71858F,  # C20
    0x9E9D95,  # C30
]

A_CLASS = [
    0x6E8699,  # A60
    0x9AB4A4,  # A30
    0x7FA7B3,  # A20
    0x517BA6,  # A50
    0x6EA0D1,  # A40
    0x7699B7,  # A17,
    0xA2C0D7,  # A10
]


class EyeSettings:
    def __init__(self, human: "Human") -> None:
        self._human = human

    @property
    def eye_obj(self) -> Object:
        return next(
            child
            for child in self._human.objects
            if "hg_eyes" in child  # type:ignore[operator]
        )

    @property
    def inner_material(self) -> Material:
        return cast(Material, self.eye_obj.data.materials[1])

    @property
    def keys(self) -> list[Union["ShapeKeyItem", "LiveKeyItem"]]:
        return self._human.keys.filtered("special", "eyes")

    def randomize(self) -> None:
        nodes = self.inner_material.node_tree.nodes

        # If you think the numers used here are incorrect, please contact us at
        # support@humgen3d.com

        # Worldwide statistics, based on
        # https://www.worldatlas.com/articles/which-eye-color-is-the-most-common-in-the-world.html

        weighted_lists = {
            79: T_CLASS,  # Brown
            13: D_CLASS,  # Amber, Hazel and Green
            3: C_CLASS,  # Grey
            9: A_CLASS,  # Blue
        }

        pupil_color_hex = random.choice(
            random.choices(
                [lst for _, lst in weighted_lists.items()],
                weights=list(weighted_lists),
            )[0]
        )

        pupil_color_rgb = self._hex_to_rgb(pupil_color_hex)

        nodes["HG_Eye_Color"].inputs[2].default_value = pupil_color_rgb  # type:ignore

    def _srgb_to_linearrgb(self, c: float) -> float:
        # Source: https://blender.stackexchange.com/questions/158896/how-set-hex-in-rgb-node-python?noredirect=1#comment269316_158896 # noqa
        if c < 0:
            return 0
        elif c < 0.04045:
            return c / 12.92
        else:
            return cast(float, ((c + 0.055) / 1.055) ** 2.4)

    def _hex_to_rgb(
        self, h: int, alpha: float = 1.0
    ) -> tuple[float, float, float, float]:
        # Source: https://blender.stackexchange.com/questions/158896/how-set-hex-in-rgb-node-python?noredirect=1#comment269316_158896 # noqa
        r = (h & 0xFF0000) >> 16
        g = (h & 0x00FF00) >> 8
        b = h & 0x0000FF
        return cast(
            tuple[float, float, float, float],
            tuple([self._srgb_to_linearrgb(c / 0xFF) for c in (r, g, b)] + [alpha]),
        )
