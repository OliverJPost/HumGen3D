# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

# type:ignore
# flake8: noqa D101

from typing import TYPE_CHECKING, Any, no_type_check, Iterable

import bpy
import numpy as np

from HumGen3D.common import find_multiple_in_list
from HumGen3D.common.context import context_override
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.objects import (
    bake_shape_key,
    delete_object,
    duplicate_object,
    remove_all_shapekeys,
    transfer_as_shape_key,
)
from HumGen3D.common.type_aliases import C  # type: ignore
from HumGen3D.human.keys.keys import apply_shapekeys

if TYPE_CHECKING:
    from HumGen3D.backend.properties.scene_main_properties import HG_SETTINGS

from HumGen3D.backend import hg_log
from HumGen3D.common.drivers import build_driver_dict
from HumGen3D.user_interface.content_panel.operators import (
    refresh_hair_ul,
    refresh_shapekeys_ul,
)

NON_TOPOLOGY_CHANGING_MODIFIERS = {
    "DATA_TRANSFER",
    "MESH_CACHE",
    "NORMAL_EDIT",
    "WEIGHTED_NORMAL",
    "UV_PROJECT",
    "UV_WARP",
    "VERTEX_WEIGHT_EDIT",
    "VERTEX_WEIGHT_MIX",
    "VERTEX_WEIGHT_PROXIMITY",
    "ARMATURE",
    "CAST",
    "CURVE",
    "DISPLACE",
    "HOOK",
    "LAPLACIANDEFORM",
    "LATTICE",
    "MESH_DEFORM",
    "SHRINKWRAP",
    "SIMPLE_DEFORM",
    "SMOOTH",
    "CORRECTIVE_SMOOTH",
    "LAPLACIANSMOOTH",
    "SURFACE_DEFORM",
    "WARP",
    "WAVE",
    "CLOTH",
    "COLLISION",
    "DYNAMIC_PAINT",
    "PARTICLE_SYSTEM",
    "SOFT_BODY",
}

# Modifiers that only move vertices. Applying them is writing the evaluated
# coordinates, which is also possible for every shape key.
DEFORM_ONLY_MODIFIERS = {
    "ARMATURE",
    "CAST",
    "CURVE",
    "DISPLACE",
    "HOOK",
    "LAPLACIANDEFORM",
    "LATTICE",
    "MESH_DEFORM",
    "SHRINKWRAP",
    "SIMPLE_DEFORM",
    "SMOOTH",
    "CORRECTIVE_SMOOTH",
    "LAPLACIANSMOOTH",
    "SURFACE_DEFORM",
    "WARP",
    "WAVE",
}


@injected_context
def apply_modifiers(human, context: C = None) -> None:  # noqa CCR001
    # The code of this function is based on the code from https://github.com/przemir/ApplyModifierForObjectWithShapeKeys/
    # The original code is licensed under the MIT license. Made by Przemysław Bągard
    # The code contains substantial changes to the original code.

    col = context.scene.modapply_col
    objs = list(human.objects)
    objs.remove(human.objects.rig)
    selected_modifier_types = {item.mod_type for item in col if item.enabled}
    human.hair.set_connected(False, context)

    for obj in objs:
        obj_modifier_types = {mod.type for mod in obj.modifiers}
        modifiers_to_apply = selected_modifier_types.intersection(obj_modifier_types)
        if not modifiers_to_apply:
            continue

        if not obj.data.shape_keys or len(obj.data.shape_keys.key_blocks) == 0:
            apply_selected_modifiers(modifiers_to_apply, obj, context)
            continue

        if modifiers_to_apply.issubset(DEFORM_ONLY_MODIFIERS) and _can_evaluate(
            obj, context
        ):
            apply_deform_modifiers(context, modifiers_to_apply, obj, human)
        else:
            apply_topology_changing_modifiers(
                context, modifiers_to_apply, obj, human
            )

    human.hair.set_connected(True, context)
    refresh_modapply(None, context)


def apply_topology_changing_modifiers(context, modifier_types, obj, human):
    sk_cache_object = duplicate_object(obj, context)
    driver_dict = build_driver_dict(obj)
    remove_all_shapekeys(obj)
    apply_selected_modifiers(modifier_types, obj, context)
    for sk in sk_cache_object.data.shape_keys.key_blocks:
        if sk.name.startswith("Basis"):
            continue

        temp_sk_object = duplicate_object(sk_cache_object, context)
        temp_sk_object.name = sk.name
        sk_value = sk.value
        remove_all_shapekeys(temp_sk_object, apply_last=sk.name)
        apply_selected_modifiers(modifier_types, temp_sk_object, context)
        transfer_as_shape_key(temp_sk_object, obj)
        new_sk = obj.data.shape_keys.key_blocks[sk.name]
        new_sk.value = sk_value
        if sk.name in driver_dict:
            human.keys._add_driver(new_sk, driver_dict[sk.name])
        delete_object(temp_sk_object)

    _bake_live_keys(obj)
    delete_object(sk_cache_object)


def apply_deform_modifiers(context, modifier_types, obj, human):
    """Applies modifiers that keep the vertex order, carrying the shape keys over.

    Instead of applying the modifiers to a copy of the object per shape key, this
    evaluates the object once per shape key with only the modifiers to apply
    enabled. The deformed shape of every key is then written back to it.
    """
    keys = obj.data.shape_keys
    key_blocks = [sk for sk in keys.key_blocks if sk != keys.reference_key]
    modifiers = [
        mod
        for mod in obj.modifiers
        if mod.type in modifier_types and _is_applied(mod, context)
    ]
    if not modifiers:
        return

    # Drivers would overwrite the values set below when the object is evaluated
    driver_dict = build_driver_dict(obj)
    values = [(sk, sk.value, sk.mute) for sk in key_blocks]
    for sk in key_blocks:
        sk.value = 0
        sk.mute = False

    visibilities = [(mod, mod.show_viewport) for mod in obj.modifiers]
    for mod in obj.modifiers:
        mod.show_viewport = mod in modifiers
    hidden = obj.hide_get()
    obj.hide_set(False)
    try:
        basis_coords = _evaluated_coords(obj, context)
        deformed_coords = []
        for sk in key_blocks:
            sk.value = 1
            deformed_coords.append(_evaluated_coords(obj, context))
            sk.value = 0
    finally:
        obj.hide_set(hidden)
        for mod, show_viewport in visibilities:
            mod.show_viewport = show_viewport

    obj.data.vertices.foreach_set("co", basis_coords)
    keys.reference_key.data.foreach_set("co", basis_coords)
    for sk, coords in zip(key_blocks, deformed_coords):
        sk.data.foreach_set("co", coords)
    for sk, value, mute in values:
        sk.value = value
        sk.mute = mute
        if sk.name in driver_dict:
            human.keys._add_driver(sk, driver_dict[sk.name])
    for mod in modifiers:
        obj.modifiers.remove(mod)
    obj.data.update()

    _bake_live_keys(obj)


def _evaluated_coords(obj, context):
    depsgraph = context.evaluated_depsgraph_get()
    mesh_eval = obj.evaluated_get(depsgraph).data
    coords = np.empty(len(mesh_eval.vertices) * 3, dtype=np.float64)
    mesh_eval.vertices.foreach_get("co", coords)
    return coords


def _can_evaluate(obj, context):
    """Whether the depsgraph evaluates this object, which it skips when the object
    is hidden in the viewport or in an excluded collection."""
    if obj.hide_viewport:
        return False
    hidden = obj.hide_get()
    obj.hide_set(False)
    try:
        depsgraph = context.evaluated_depsgraph_get()
        return obj.evaluated_get(depsgraph).is_evaluated
    finally:
        obj.hide_set(hidden)


def _is_applied(mod, context):
    if context.scene.HG3D.process.modapply.apply_hidden:
        return True
    return mod.show_render and mod.show_viewport


def _bake_live_keys(obj):
    """Bakes the live keys into the basis, they are not needed on a processed human."""
    if not obj.data.shape_keys:
        return
    for sk in list(obj.data.shape_keys.key_blocks):
        if sk.name.startswith("LIVE_KEY"):
            bake_shape_key(sk, obj)


def apply_selected_modifiers(modifier_types, obj, context):
    for mod in reversed(obj.modifiers):
        if not mod.type in modifier_types:
            continue
        if not _is_applied(mod, context):
            continue
        mod_name = mod.name
        with context_override(context, obj, [obj]):
            bpy.ops.object.modifier_apply(modifier=mod_name)
        assert mod_name not in obj.modifiers


@no_type_check
def _add_shapekeys_again(objs, sk_dict, driver_dict):
    for obj in objs:
        if not sk_dict.get(obj.name):
            continue
        for sk_name, sk_coords in sk_dict[obj.name].items():
            sk = obj.shape_key_add(name=sk_name)
            sk.data.foreach_set("co", sk_coords)
            sk.value = 1.0
        for target_sk_name, sett_dict in driver_dict[obj.name].items():
            human.keys._add_driver(sks[target_sk_name], sett_dict)


class HG_OT_REFRESH_UL(bpy.types.Operator):
    bl_idname = "hg3d.ulrefresh"
    bl_label = "Refresh list"
    bl_description = "Refresh list"

    uilist_type: bpy.props.StringProperty()

    @no_type_check
    def execute(self, context):
        if self.uilist_type == "modapply":
            refresh_modapply(self, context)
        elif self.uilist_type == "shapekeys":
            refresh_shapekeys_ul(self, context)
        elif self.uilist_type == "hair":
            refresh_hair_ul(self, context)
        return {"FINISHED"}


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


SKIP_MODIFIERS = {
    "PARTICLE_SYSTEM",
    "DECIMATE",
}


def refresh_modapply(self: Any, context: bpy.types.Context) -> None:  # noqa CCR001
    sett = context.scene.HG3D  # type:ignore[attr-defined]
    col = context.scene.modapply_col
    col.clear()

    header = col.add()
    header.mod_name = "HEADER"
    objs = build_object_list(context, sett)

    for obj in objs:

        for mod in obj.modifiers:
            if mod.type in SKIP_MODIFIERS:
                continue

            build_summary_list(col, mod)  # type:ignore[arg-type]


def build_object_list(
    context: bpy.types.Context, sett: "HG_SETTINGS"
) -> list[bpy.types.Object]:
    from HumGen3D.human.human import Human

    objs = [obj for obj in context.selected_objects if not obj.HG.ishuman]
    selected_rigs = find_multiple_in_list(context.selected_objects)
    humans: Iterable[Human] = [
        Human.from_existing(obj, strict_check=False) for obj in selected_rigs
    ]

    ma_sett = sett.process.modapply
    for human in humans:
        if not human:
            continue
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

    return list(set(objs))


def build_summary_list(
    col: bpy.types.CollectionProperty, mod: bpy.types.Modifier
) -> None:
    existing = [item for item in col if item.mod_type == mod.type]
    if existing:
        item = existing[0]
        item.count += 1
    else:
        item = col.add()
        item.mod_name = mod.type.title().replace("_", " ")
        item.mod_type = mod.type
        item.count = 1
        if mod.type in ["ARMATURE", "SUBSURF"]:
            item.enabled = False
        else:
            item.enabled = True
