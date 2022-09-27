# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""
context.scene.HG3D.bone_sizes
Contains floatproperties for driving the scale of the different bones during creation
phase.
"""

import bpy
from bpy.props import BoolProperty, FloatProperty  # type:ignore
from HumGen3D.human.human import Human


def create_bone_props(bone_names):
    """Currently inactive, used for automatic generation of FloatProperties"""
    prop_dict = {}
    for name in bone_names:
        prop_dict[name] = FloatProperty(
            default=0.5,
            soft_min=0,
            soft_max=1,
            # update=lambda s, c: Human.from_existing(
            #     c.object
            # ).body.set_bone_scale(getattr(s, name), name, c),
        )

    return prop_dict


class BoneSizeProps(bpy.types.PropertyGroup):
    """Subclass of HG_SETTINGS, contains float properties for scaling bones"""

    # TODO automatic generation of properties
    # def __new__(cls, *args, **kwargs):
    #     cls.__annotations__.update(
    #         create_bone_props(
    #             [
    #                 "head",
    #                 "neck",
    #                 "chest",
    #                 "shoulder",
    #                 "breast",
    #                 "hips",
    #                 "upper_arm",
    #                 "forearm",
    #                 "hand",
    #                 "thigh",
    #                 "shin",
    #                 "foot",
    #             ]
    #         )
    #     )
    #     self = super().__new__(*args, **kwargs)
    #     return self

    head: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(c.object).body.set_bone_scale(
            s.head, "head", c
        ),
    )
    neck: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(c.object).body.set_bone_scale(
            s.neck, "neck", c
        ),
    )

    chest: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(c.object).body.set_bone_scale(
            s.chest, "chest", c
        ),
    )
    shoulder: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(c.object).body.set_bone_scale(
            s.shoulder, "shoulder", c
        ),
    )
    breast: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(c.object).body.set_bone_scale(
            s.breast, "breast", c
        ),
    )
    hips: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(c.object).body.set_bone_scale(
            s.hips, "hips", c
        ),
    )

    upper_arm: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(c.object).body.set_bone_scale(
            s.upper_arm, "upper_arm", c
        ),
    )
    forearm: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(c.object).body.set_bone_scale(
            s.forearm, "forearm", c
        ),
    )
    hand: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(c.object).body.set_bone_scale(
            s.hand, "hand", c
        ),
    )

    thigh: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(c.object).body.set_bone_scale(
            s.thigh, "thigh", c
        ),
    )
    shin: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(c.object).body.set_bone_scale(
            s.shin, "shin", c
        ),
    )
    foot: FloatProperty(
        default=0.5,
        soft_min=0,
        soft_max=1,
        update=lambda s, c: Human.from_existing(c.object).body.set_bone_scale(
            s.foot, "foot", c
        ),
    )
