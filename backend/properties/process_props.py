import bpy
from bpy.props import BoolProperty, EnumProperty


class ProcessProps(bpy.types.PropertyGroup):
    bake: BoolProperty(default=False)
    human_list_isopen: BoolProperty(default=False)
    output: EnumProperty(
        items=[
            ("replace", "Replace humans", "", 0),
            ("duplicate", "Duplicate humans", "", 1),
            ("export", "Export humans", "", 2),
        ]
    )
