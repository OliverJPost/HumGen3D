# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import json
import os

import bpy
from bpy.props import (  # type:ignore
    BoolProperty,
    EnumProperty,
    FloatProperty,
    PointerProperty,
    StringProperty,
)
from HumGen3D.backend.preferences.preference_func import get_addon_root


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


def create_name_props():
    """Function for creating StringProperties in a loop to prevent repetition."""
    prop_dict = {}

    path = os.path.join(
        get_addon_root(), "backend", "properties", "bone_basenames.json"
    )
    with open(path, "r") as f:
        prop_names = json.load(f)

    for category, name_dict in prop_names.items():
        for name, has_left_right in name_dict.items():
            prop_dict[name.replace(".", "")] = StringProperty(
                name=name,
                default=name,
                description=f"Category: {category}, Mirrored: {has_left_right}",
            )

    return prop_dict


class RigRenamingProps(bpy.types.PropertyGroup):
    _register_priority = 3

    __annotations__.update(create_name_props())  # noqa

    suffix_L: StringProperty(name=".L", default=".L")
    suffix_R: StringProperty(name=".R", default=".R")


class ProcessProps(bpy.types.PropertyGroup):
    _register_priority = 4

    lod: PointerProperty(type=LodProps)
    rig_naming: PointerProperty(type=RigRenamingProps)

    bake: BoolProperty(default=False)
    lod_enabled: BoolProperty(default=False)
    modapply_enabled: BoolProperty(default=True)
    human_list_isopen: BoolProperty(default=False)
    haircards_enabled: BoolProperty(default=False)
    rig_renaming_enabled: BoolProperty(default=False)

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
