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
    PointerProperty,
    StringProperty,
)


class HG_OBJECT_PROPS(bpy.types.PropertyGroup):
    """
    Properties added to every Blender object as object.HG
    Used for storing information about the human itself.
    """

    ishuman: BoolProperty(name="Is Human", default=False)
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
    backup: PointerProperty(name="hg_backup", type=bpy.types.Object)
    length: FloatProperty()
    experimental: BoolProperty(default=False)
    batch_result: BoolProperty(default=False)
