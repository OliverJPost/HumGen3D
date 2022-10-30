# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy
from bpy.props import (  # type:ignore
    BoolProperty,
    EnumProperty,
    FloatProperty,
    PointerProperty,
    StringProperty,
)


class LodProps(bpy.types.PropertyGroup):
    _register_priority = 3

    suffix: StringProperty(default="_LOD0")
    body_lod: EnumProperty(
        items=[
            ("0", "Original resolution", "", 0),
            ("1", "Lower face resolution", "", 1),
            ("2", "1/4th original resolution", "", 2),
        ],
        default="0",
    )
    decimate_ratio: FloatProperty(min=0, max=1, default=0.15)
    remove_clothing_subdiv: BoolProperty(default=True)
    remove_clothing_solidify: BoolProperty(default=True)


class HaircardProps(bpy.types.PropertyGroup):
    _register_priority = 3

    quality: EnumProperty(
        name="Quality",
        items=[
            ("ultra", "Ultra", "", 0),
            ("high", "High", "", 1),
            ("medium", "Medium", "", 2),
            ("low", "Low", "", 3),
            ("haircap_only", "Haircap only", "", 4),
        ],
        default="high",
    )


class ProcessProps(bpy.types.PropertyGroup):
    _register_priority = 4

    lod: PointerProperty(type=LodProps)
    haircards: PointerProperty(type=HaircardProps)

    bake: BoolProperty(default=False)
    lod_enabled: BoolProperty(default=False)
    modapply_enabled: BoolProperty(default=True)
    human_list_isopen: BoolProperty(default=False)
    haircards_enabled: BoolProperty(default=False)
    rig_enabled: BoolProperty(default=False)

    output: EnumProperty(
        items=[
            ("replace", "Replace humans", "", 0),
            ("duplicate", "Duplicate humans", "", 1),
            ("export", "Export humans", "", 2),
        ]
    )

    presets: EnumProperty(
        items=[
            ("1", "Bake high res", "", 0),
            ("2", "Unity export", "", 1),
            ("3", "Apply all modifiers", "", 2),
        ]
    )
