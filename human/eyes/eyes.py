import random

from bpy.types import Material, Object


class EyeSettings:
    def __init__(self, human):
        self._human = human

    @property
    def eye_obj(self) -> Object:
        return next(
            child for child in self._human.objects if "hg_eyes" in child
        )

    @property
    def inner_material(self) -> Material:
        return self.eye_obj.data.materials[1]

    def randomize(self):
        nodes = self.inner_material.node_tree.nodes

        T_Class = [
            0x3F313B,  # T50
            0x633935,  # T30
            0x71533C,  # T17
            0xB26D55,  # T10
            0x41282C,  # T40
            0x6A4A47,  # T20
            0x8F7459,  # T15
            0xB37556,  # T07
        ]

        D_Class = [
            0x988856,  # D60
            0x8A815A,  # D40
            0x7D8169,  # D34
            0x52564B,  # D20
            0xAE9B73,  # D50
            0xAC9B74,  # D37
            0x9E945C,  # D30
            0x577377,  # D10
        ]

        C_Class = [
            0x747C7F,  # C40
            0x71858F,  # C20
            0x9E9D95,  # C30
        ]

        A_Class = [
            0x6E8699,  # A60
            0x9AB4A4,  # A30
            0x7FA7B3,  # A20
            0x517BA6,  # A50
            0x6EA0D1,  # A40
            0x7699B7,  # A17,
            0xA2C0D7,  # A10
        ]

        # If you think the numers used here are incorrect, please contact us at
        # support@humgen3d.com

        # Worldwide statistics, based on
        # https://www.worldatlas.com/articles/which-eye-color-is-the-most-common-in-the-world.html

        weighted_lists = {
            79: T_Class,  # Brown
            13: D_Class,  # Amber, Hazel and Green
            3: C_Class,  # Grey
            9: A_Class,  # Blue
        }

        pupil_color_hex = random.choice(
            random.choices(
                [lst for _, lst in weighted_lists.items()],
                weights=[weight for weight in weighted_lists],
            )[0]
        )

        pupil_color_rgb = self._hex_to_rgb(pupil_color_hex)

        nodes["HG_Eye_Color"].inputs[2].default_value = pupil_color_rgb

    def _srgb_to_linearrgb(self, c):
        # Source: https://blender.stackexchange.com/questions/158896/how-set-hex-in-rgb-node-python?noredirect=1#comment269316_158896
        if c < 0:
            return 0
        elif c < 0.04045:
            return c / 12.92
        else:
            return ((c + 0.055) / 1.055) ** 2.4

    def _hex_to_rgb(self, h, alpha=1):
        # Source: https://blender.stackexchange.com/questions/158896/how-set-hex-in-rgb-node-python?noredirect=1#comment269316_158896
        r = (h & 0xFF0000) >> 16
        g = (h & 0x00FF00) >> 8
        b = h & 0x0000FF
        return tuple([self._srgb_to_linearrgb(c / 0xFF) for c in (r, g, b)] + [alpha])
