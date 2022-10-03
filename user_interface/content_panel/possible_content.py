import bpy
from bpy.props import StringProperty, PointerProperty, EnumProperty
from bpy.types import Object


class HG_UL_POSSIBLE_CONTENT(bpy.types.UIList):
    """
    UIList showing modifiers
    """

    def draw_item(self, context, layout, data, item, *_):
        layout.label(text="test")


class POSSIBLE_CONTENT_ITEM(bpy.types.PropertyGroup):
    name: StringProperty()
    obj: PointerProperty(type=Object)
    category: EnumProperty(
        items=[
            ("key", "Key", "", 0),
            ("clothing", "Clothing", "", 1),
            ("hair", "Hairstyle", "", 2),
            ("pose", "Pose", "", 3),
        ]
    )


def find_possible_content(context):
    pass
