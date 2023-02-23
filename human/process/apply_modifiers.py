# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
import contextlib

# type:ignore
# flake8: noqa D101

from typing import TYPE_CHECKING, Any, no_type_check

import bpy
import numpy as np

from HumGen3D.backend import hg_log
from HumGen3D.common import find_multiple_in_list
from HumGen3D.common.context import context_override
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C  # type: ignore
from HumGen3D.user_interface.documentation.feedback_func import ShowMessageBox

if TYPE_CHECKING:
    from HumGen3D.backend.properties.scene_main_properties import HG_SETTINGS


def _apply_selected_modifiers(context, modifiers, obj):
    with context_override(context, obj, [obj]):
        mod_list = obj.modifiers
        if modifiers:
            mod_list = [mod for mod in mod_list if mod.type in modifiers]
        for mod in mod_list:
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except RuntimeError as e:
                hg_log(e, level="ERROR")
                ShowMessageBox(
                    "Error", "Error applying modifier, see console.", "ERROR"
                )


class ShapekeyCache:
    def __init__(self, shapekey):
        self.name = shapekey.name
        self.value = shapekey.value
        coords = np.empty((len(shapekey.data) * 3), dtype=np.float64)
        shapekey.data.foreach_get("co", coords)
        self.coords = coords

    def restore(self, obj):
        # Add basis if not there
        if not obj.data.shape_keys:
            obj.shape_key_add(name="Basis", from_mix=False)

        shapekey = obj.shape_key_add(name=self.name, from_mix=False)
        shapekey.value = self.value
        shapekey.data.foreach_set("co", self.coords)
        shapekey.data.update()


class DriverCache:
    def __init__(self, driver):
        self.target_sk = driver.data_path.replace('key_blocks["', "").replace(
            '"].value', ""
        )
        self.expression = driver.driver.expression
        var = driver.driver.variables[0]
        target = var.targets[0]
        self.target_bone = target.bone_target
        self.transform_type = target.transform_type
        self.transform_space = target.transform_space

    def restore(self, obj, rig):
        shapekey = obj.data.shape_keys.key_blocks[self.target_sk]
        driver = shapekey.driver_add("value")
        driver.driver.expression = self.expression
        var = driver.driver.variables.new()
        var.name = "var"
        var.type = "TRANSFORMS"
        target = var.targets[0]
        target.id = rig
        target.bone_target = self.target_bone
        target.transform_type = self.transform_type
        target.transform_space = self.transform_space


def _build_obj_list(
    human,
    to_body: bool = True,
    to_eyes: bool = True,
    to_teeth: bool = True,
    to_clothing: bool = True,
) -> list[bpy.types.Object]:
    obj_list = []
    if to_body:
        obj_list.append(human.objects.body)
    if to_eyes:
        obj_list.append(human.objects.eyes)
    if to_teeth:
        obj_list.append(human.objects.lower_teeth)
        obj_list.append(human.objects.upper_teeth)
    if to_clothing:
        obj_list.extend(human.clothing.outfit.objects)
        obj_list.extend(human.clothing.footwear.objects)
    return obj_list


ShapeKeyDict = dict[str, list[ShapekeyCache]]
DriverDict = dict[str, list[DriverCache]]


def _copy_key_data(obj_list) -> tuple[ShapeKeyDict, DriverDict]:
    shapekeys = {}
    drivers = {}
    for obj in obj_list:
        shapekeys[obj.name] = []
        drivers[obj.name] = []
        with contextlib.suppress(AttributeError):
            for driver in obj.data.shape_keys.animation_data.drivers:
                drivers[obj.name].append(DriverCache(driver))

        with contextlib.suppress(AttributeError):
            for shapekey in obj.data.shape_keys.key_blocks:
                shapekeys[obj.name].append(ShapekeyCache(shapekey))

    return shapekeys, drivers


def _remove_drivers(obj):
    with contextlib.suppress(AttributeError):
        for driver in obj.data.shape_keys.animation_data.drivers[:]:
            obj.data.shape_keys.animation_data.drivers.remove(driver)


def _restore_key_data(obj_list, shapekey_dict: ShapeKeyDict, driver_dict: DriverDict):
    for obj in obj_list:
        for key in shapekey_dict[obj.name]:
            key.restore(obj)
        for driver in driver_dict[obj.name]:
            driver.restore(obj, obj.parent)


def get_selected_modifiers(context: C) -> list[str]:
    col = context.scene.modapply_col
    return list(set(item.mod_type for item in col if item.enabled))


class HG_OT_SELECTMODAPPLY(bpy.types.Operator):
    bl_idname = "hg3d.selectmodapply"
    bl_label = "Select all/none modifiers"
    bl_description = "Select all/none modifiers"
    bl_options = {"UNDO"}

    select_all: bpy.props.BoolProperty()

    @no_type_check
    def execute(self, context):
        col = context.scene.modapply_col

        refresh_modapply(self, context)

        for item in col:
            item.enabled = self.select_all

        return {"FINISHED"}


def refresh_modapply(self: Any, context: bpy.types.Context) -> None:  # noqa CCR001
    sett = context.scene.HG3D  # type:ignore[attr-defined]
    col = context.scene.modapply_col
    currently_enabled = [item.mod_type for item in col if item.enabled]
    col.clear()
    objs = build_object_list(context, sett)

    for obj in objs:
        for mod in obj.modifiers:
            if mod.type == "PARTICLE_SYSTEM":
                continue

            add_to_collection(col, mod, currently_enabled)  # type:ignore[arg-type]


def build_object_list(
    context: bpy.types.Context, sett: "HG_SETTINGS"
) -> list[bpy.types.Object]:
    from HumGen3D.human.human import Human

    rigs = find_multiple_in_list(context.selected_objects)
    ma_sett = sett.process.modapply
    objs = []
    for rig in rigs:
        human = Human.from_existing(rig)
        if ma_sett.apply_body:
            objs.append(human.objects.body)
        if ma_sett.apply_eyes:
            objs.append(human.objects.eyes)
        if ma_sett.apply_teeth:
            objs.append(human.objects.lower_teeth)
            objs.append(human.objects.upper_teeth)
        if ma_sett.apply_clothing:
            objs.extend(human.clothing.outfit.objects)
            objs.extend(human.clothing.footwear.objects)

    return objs


def add_to_collection(
    col: bpy.types.CollectionProperty, mod: bpy.types.Modifier, enabled: list[str]
) -> None:
    existing = [item for item in col if item.mod_type == mod.type]
    if existing:
        item = existing[0]
        item.count += 1
        return

    item = col.add()
    item.mod_name = mod.type.title().replace("_", " ")
    item.mod_type = mod.type
    item.count = 1
    if mod.type in enabled:
        item.enabled = True
        return

    if mod.type in ["ARMATURE", "SUBSURF"]:
        item.enabled = False
    else:
        item.enabled = True
