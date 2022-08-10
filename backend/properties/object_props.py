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


class HG_SK_VALUES(bpy.types.PropertyGroup):
    testprop: BoolProperty()


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
    length: FloatProperty()
    experimental: BoolProperty(default=False)
    batch_result: BoolProperty(default=False)
    sk_values: PointerProperty(type=HG_SK_VALUES)
