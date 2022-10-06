# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""
object.HG
Properties added to every object when Human Generator is installed. Used for storing
information about the human in a way that doesn't get lost when transfering between
files/computers.
"""

import bpy
from bpy.props import (  # type: ignore
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    IntVectorProperty,
    PointerProperty,
    StringProperty,
)


class HG_SK_VALUES(bpy.types.PropertyGroup):
    testprop: BoolProperty()


class HG_HASHES(bpy.types.PropertyGroup):
    pass


class HG_OBJECT_PROPS(bpy.types.PropertyGroup):
    """
    Properties added to every Blender object as object.HG
    Used for storing information about the human itself.
    """

    ishuman: BoolProperty(name="Is Human", default=False)
    gender: EnumProperty(
        name="gender",
        description="",
        items=[
            ("male", "male", "", 0),
            ("female", "female", "", 1),
        ],
        default="male",
    )
    body_obj: PointerProperty(name="hg_body", type=bpy.types.Object)
    batch_result: BoolProperty(default=False)
    sk_values: PointerProperty(type=HG_SK_VALUES)
    hashes: PointerProperty(type=HG_HASHES)
    version: IntVectorProperty(default=(3, 0, 0), min=0, max=99, size=3)
    # Legacy props
    experimental: BoolProperty(default=False)
    length: FloatProperty()
    backup: PointerProperty(type=bpy.types.Object)
    phase: EnumProperty(
        name="phase",
        items=[
            ("base_human", "base_human", "", 0),
            ("body", "body", "", 1),
            ("face", "face", "", 2),
            ("skin", "skin", "", 3),
            ("hair", "hair", "", 4),
            ("length", "length", "", 5),
            ("clothing", "clothing", "", 6),
            ("footwear", "footwear", "", 7),
            ("pose", "pose", "", 8),
            ("expression", "expression", "", 9),
            ("simulation", "simulation", "", 10),
            ("compression", "compression", "", 11),
            ("completed", "completed", "", 12),
            ("creator", "creator", "", 13),
        ],
        default="base_human",
    )
