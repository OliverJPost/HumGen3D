# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements class for manipulating the eyes of the human."""

import random
from typing import TYPE_CHECKING, Any, cast

from bpy.types import Material, Object  # type:ignore
from HumGen3D.common.shadernode import NodeInput  # type:ignore
from HumGen3D.human.common_baseclasses.prop_collection import PropCollection

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
    """Class for manipulating the eyes of the human.

    Also contains properties for changing the material values.
    """

    def __init__(self, human: "Human") -> None:
        self._human = human

        self.iris_color = NodeInput(self, "HG_Eye_Color", "Color2")
        self.sclera_color = NodeInput(self, "HG_Scelera_Color", "Color2")

    @property
    def eye_obj(self) -> Object:
        """Blender object of the eyes of the human.

        Returns:
            Object: Blender object of the eyes of the human.
        """
        self._human.objects.eyes

    @property
    def outer_material(self) -> Material:
        """The material used for the outer layer of the eyes (The transparent part).

        Returns:
            Material: Material used for the outer layer of the eyes.
        """
        return cast(Material, self.objects.eyes.data.materials[0])

    @property
    def inner_material(self) -> Material:
        """The material used for the inner part of the eyes (The colored part).

        Returns:
            Material: Material used for the inner part of the eyes.
        """
        return cast(Material, self.objects.eyes.data.materials[1])

    @property
    def nodes(self) -> PropCollection:
        """Nodes of the inner eye material.

        Returns:
            PropCollection: ShaderNodes of the inner eye material.
        """
        return self.inner_material.node_tree.nodes

    def randomize(self) -> None:
        """Randomizes the color of the pupils based on worlwide statistics."""
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

    def as_dict(self) -> dict[str, tuple[float, float, float, float]]:
        """Returns the current eye settings as a dictionary.

        Returns:
            dict: Dictionary containing the current eye settings. Currently color only.
        """
        return {
            "pupil_color": self.iris_color.value,
            "sclera_color": self.sclera_color.value,
        }

    def set_from_dict(self, data: dict[str, Any]) -> None:
        """Sets the eye settings from a dictionary.

        This dict can be derived from the as_dict method.

        Args:
            data (dict[str, Any]): Dictionary to set the eye settings from.
        """
        self.iris_color.value = data["pupil_color"]
        self.sclera_color.value = data["sclera_color"]

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
