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

    face_hair: BoolProperty(default=False, name="Face hair")


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


class MaterialRenaming(bpy.types.PropertyGroup):
    _register_priority = 2

    use_suffix: BoolProperty(name="Use suffix", default=True)

    body: StringProperty(name="Body", default=".Human")

    haircards: StringProperty(name="Haircards", default="HG_Haircards")
    haircap: StringProperty(name="Haircap", default="HG_Haircap")
    eye_hair: StringProperty(name="Eye hair", default=".HG_Hair_Eye")
    face_hair: StringProperty(name="Face hair", default=".HG_Hair_Face")
    head_hair: StringProperty(name="Main hair", default=".HG_Hair_Head")

    eye_outer: StringProperty(name="Eye outer", default=".HG_Eyes_Outer_FAST")
    eye_inner: StringProperty(name="Eye inner", default=".HG_Eyes_Inner")

    teeth: StringProperty(name="Teeth", default=".HG_Teeth")

    clothing: StringProperty(name="Clothing", default=".{original_name}")


class RenamingProps(bpy.types.PropertyGroup):
    _register_priority = 3

    custom_token: StringProperty(name="Custom token", default="")
    suffix: StringProperty(name="Suffix", default="")
    use_suffix: BoolProperty(name="Use suffix", default=True)

    materials: PointerProperty(type=MaterialRenaming)
    rig_obj: StringProperty(name="Rig", default="HG_{name}")
    body_obj: StringProperty(name="Body", default="HG_Body")
    eye_obj: StringProperty(name="Eye", default="HG_Eyes")
    upper_teeth_obj: StringProperty(name="Teeth Upper", default="HG_TeethUpper")
    lower_teeth_obj: StringProperty(name="Teeth Lower", default="HG_TeethLower")
    haircards_obj: StringProperty(name="Haircards", default="HG_Haircards")
    clothing: StringProperty(name="Clothing", default="{original_name}")


class ProcessProps(bpy.types.PropertyGroup):
    _register_priority = 4

    lod: PointerProperty(type=LodProps)

    haircards: PointerProperty(type=HaircardProps)
    rig_naming: PointerProperty(type=RigRenamingProps)
    renaming: PointerProperty(type=RenamingProps)

    bake: BoolProperty(default=False)
    lod_enabled: BoolProperty(default=False)
    modapply_enabled: BoolProperty(default=False)
    human_list_isopen: BoolProperty(default=False)
    haircards_enabled: BoolProperty(default=False)
    rig_renaming_enabled: BoolProperty(default=False)
    renaming_enabled: BoolProperty(default=False)

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
