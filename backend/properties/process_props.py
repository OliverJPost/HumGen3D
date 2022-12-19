# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
import ast
import json
import logging
import os

import bpy
from bpy.props import (  # type:ignore
    BoolProperty,
    EnumProperty,
    FloatProperty,
    PointerProperty,
    StringProperty,
)
from HumGen3D.backend.preferences.preference_func import get_addon_root, get_prefs
from HumGen3D.backend.properties.bake_props import BakeProps
from HumGen3D.human.process.apply_modifiers import refresh_modapply
from HumGen3D.human.process.process import ProcessSettings


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


def get_preset_list(self, context):
    """Gets all .json files from the preset folder and returns them as a list."""
    path = os.path.join(get_prefs().filepath, "process_templates")
    file_list = []
    i = 0
    prev_root = ""
    for root, _, files in os.walk(path):
        files = [file for file in files if file.endswith(".json")]
        for file in files:
            if root != prev_root:
                folder_name = os.path.split(root)[-1].capitalize()
                file_list.append(("", folder_name, ""))

            comp_path = os.path.join(get_prefs().filepath, "process_templates")
            relpath = os.path.relpath(os.path.join(root, file), comp_path)

            file_list.append((relpath, file.replace(".json", ""), "", i))
            i += 1
            prev_root = root

    return file_list


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


class ModApplyProps(bpy.types.PropertyGroup):
    _register_priority = 3

    search_objects: EnumProperty(
        name="Objects to apply",
        items=[
            ("selected", "Selected objects only", "", 0),
            ("all", "All selected humans", "", 2),
        ],
        default="all",
        update=refresh_modapply,
    )

    search_modifiers: EnumProperty(
        name="Modifier display method",
        items=[
            ("summary", "Modifier summary", "", 0),
            ("individual", "Individual modifiers", "", 1),
        ],
        default="summary",
        update=refresh_modapply,
    )

    apply_hidden: BoolProperty(default=False)
    keep_shapekeys: BoolProperty(default=True)


def get_script_list(self, context):
    folder = os.path.join(get_prefs().filepath, "scripts")
    files = [
        os.path.join(folder, file)
        for file in os.listdir(folder)
        if file.endswith(".py")
    ]
    folder = os.path.join(get_addon_root(), "scripts", "preset_scripts")
    files += [
        os.path.join(folder, file)
        for file in os.listdir(folder)
        if file.endswith(".py")
    ]
    return [(file, os.path.basename(file), "") for file in files]


def add_script_to_collection(self, context):
    """Adds a script to the collection."""
    scripts_col = context.scene.hg_scripts_col
    item = scripts_col.add()
    item.name = os.path.basename(self.available_scripts)
    item.path = os.path.dirname(self.available_scripts)
    ast_tree = _get_ast_tree(self)
    item.description = ast.get_docstring(ast_tree) or "No description found."
    _add_parameters(ast_tree, item)


def _add_parameters(ast_tree, item):
    for node in ast.walk(ast_tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            args = node.args.args[2:]
            break
    # ast list of keyword arguments
    defaults = node.args.defaults
    non_kw_args_len = len(args) - len(defaults)
    defaults = [None] * non_kw_args_len + defaults

    for i, arg in enumerate(args):
        if not arg.annotation:
            raise ValueError(
                f"Parameter {arg.arg} in {item.name} has no type annotation. Please contact creator of the script."
            )
        arg_type = arg.annotation.id
        allowed_argtypes = ["str", "int", "float", "bool"]
        if arg_type not in allowed_argtypes:
            raise TypeError(
                f"Invalid argument type: {arg_type}, can only be one of {allowed_argtypes}. "
                f"This is an error in the script, if you are not the creator of the script, "
                f"please report this to the creator."
            )

        arg_item = item.args.add()
        arg_item.name = arg.arg
        arg_item.type = arg_type
        if defaults[i]:
            arg_item.set_default(defaults[i].value)


def _get_ast_tree(self):
    with open(self.available_scripts, "r") as f:
        code = f.read()
    ast_tree = ast.parse(code)
    return ast_tree


class ScriptingProps(bpy.types.PropertyGroup):
    _register_priority = 3
    available_scripts: EnumProperty(
        items=get_script_list,
        update=add_script_to_collection,
    )


class ProcessProps(bpy.types.PropertyGroup):
    _register_priority = 4

    lod: PointerProperty(type=LodProps)
    haircards: PointerProperty(type=HaircardProps)
    rig_renaming: PointerProperty(type=RigRenamingProps)
    renaming: PointerProperty(type=RenamingProps)
    modapply: PointerProperty(type=ModApplyProps)
    baking: PointerProperty(type=BakeProps)
    scripting: PointerProperty(type=ScriptingProps)

    baking_enabled: BoolProperty(default=False)
    lod_enabled: BoolProperty(default=False)
    modapply_enabled: BoolProperty(default=False)
    haircards_enabled: BoolProperty(default=False)
    rig_renaming_enabled: BoolProperty(default=False)
    renaming_enabled: BoolProperty(default=False)
    scripting_enabled: BoolProperty(default=False)

    output_name: StringProperty(name="Output name", default="{name}")

    human_list_isopen: BoolProperty(default=False)
    output: EnumProperty(
        items=[
            ("replace", "Replace humans", "", 0),
            ("duplicate", "Duplicate humans", "", 1),
            ("export", "Export humans", "", 2),
        ]
    )
    file_type: EnumProperty(
        items=[
            (".obj", "OBJ", "", 0),
            (".fbx", "FBX", "", 1),
            (".abc", "Alembic", "", 2),
            (".glb", "glTF Binary (.glb)", "", 3),
            (".glTF", "glTF Embedded (.glTF", "", 4),
        ]
    )

    presets: EnumProperty(
        items=get_preset_list,
        update=lambda self, context: ProcessSettings.set_settings_from_template(
            os.path.join(get_prefs().filepath, "process_templates", self.presets),
            context=context,
        ),
    )
