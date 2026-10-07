# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

# type:ignore
# flake8: noqa D101

"""Applies modifiers to the meshes of a human while keeping their shape keys.

Blender refuses to apply a modifier to a mesh with shape keys. Deform-only
modifiers are applied here by evaluating the mesh once per key and writing the
result back, modifiers that change the topology by applying them to a copy per
key and transferring the keys. Exposed as `human.process.apply_modifiers`, for
scripts and API users; the steps of the process system apply the modifiers
they are about with bmesh or in edit mode.
"""

from typing import Iterable

import bpy
import numpy as np

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
from HumGen3D.common.drivers import build_driver_dict

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
# Never applied: particle hair is not a mesh change, decimate is the LOD step
SKIP_MODIFIERS = {"PARTICLE_SYSTEM", "DECIMATE"}


@injected_context
def apply_modifiers(
    human,
    modifier_types: Iterable[str],
    objects: Iterable[bpy.types.Object] = None,
    apply_hidden: bool = False,
    context: C = None,
) -> None:
    """Applies the modifiers of these types to the meshes of the human.

    The shape keys and their drivers are kept, see the module docstring.

    Args:
        human (Human): Human whose meshes to change, in place.
        modifier_types (Iterable[str]): Types to apply, like "MASK" or "SUBSURF".
        objects (Iterable[Object]): Meshes to apply to, all meshes of the human
            when None.
        apply_hidden (bool): Also apply modifiers hidden in the viewport.
        context (C): Blender context. bpy.context if not provided.
    """
    # The code of this function is based on the code from https://github.com/przemir/ApplyModifierForObjectWithShapeKeys/
    # The original code is licensed under the MIT license. Made by Przemysław Bągard
    # The code contains substantial changes to the original code.
    selected_modifier_types = set(modifier_types) - SKIP_MODIFIERS
    if objects is None:
        objects = [obj for obj in human.objects if obj.type == "MESH"]
    human.hair.set_connected(False, context)

    for obj in objects:
        obj_modifier_types = {
            mod.type for mod in obj.modifiers if _is_applied(mod, apply_hidden)
        }
        modifiers_to_apply = selected_modifier_types.intersection(obj_modifier_types)
        if not modifiers_to_apply:
            continue

        if not obj.data.shape_keys or len(obj.data.shape_keys.key_blocks) == 0:
            apply_selected_modifiers(modifiers_to_apply, obj, context, apply_hidden)
            continue

        if modifiers_to_apply.issubset(DEFORM_ONLY_MODIFIERS) and _can_evaluate(
            obj, context
        ):
            apply_deform_modifiers(context, modifiers_to_apply, obj, human, apply_hidden)
        else:
            apply_topology_changing_modifiers(
                context, modifiers_to_apply, obj, human, apply_hidden
            )

    human.hair.set_connected(True, context)


def apply_topology_changing_modifiers(
    context, modifier_types, obj, human, apply_hidden: bool = True
):
    sk_cache_object = duplicate_object(obj, context)
    driver_dict = build_driver_dict(obj)
    remove_all_shapekeys(obj)
    apply_selected_modifiers(modifier_types, obj, context, apply_hidden)
    for sk in sk_cache_object.data.shape_keys.key_blocks:
        if sk.name.startswith("Basis"):
            continue

        temp_sk_object = duplicate_object(sk_cache_object, context)
        temp_sk_object.name = sk.name
        sk_value = sk.value
        remove_all_shapekeys(temp_sk_object, apply_last=sk.name)
        apply_selected_modifiers(modifier_types, temp_sk_object, context, apply_hidden)
        transfer_as_shape_key(temp_sk_object, obj)
        new_sk = obj.data.shape_keys.key_blocks[sk.name]
        new_sk.value = sk_value
        if sk.name in driver_dict:
            human.keys._add_driver(new_sk, driver_dict[sk.name])
        delete_object(temp_sk_object)

    _bake_live_keys(obj)
    delete_object(sk_cache_object)


def apply_deform_modifiers(context, modifier_types, obj, human, apply_hidden: bool = False):
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
        if mod.type in modifier_types and _is_applied(mod, apply_hidden)
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


def _is_applied(mod, apply_hidden: bool):
    if apply_hidden:
        return True
    return mod.show_render and mod.show_viewport


def _bake_live_keys(obj):
    """Bakes the live keys into the basis, they are not needed on a processed human."""
    if not obj.data.shape_keys:
        return
    for sk in list(obj.data.shape_keys.key_blocks):
        if sk.name.startswith("LIVE_KEY"):
            bake_shape_key(sk, obj)


def apply_selected_modifiers(modifier_types, obj, context, apply_hidden: bool = True):
    for mod in reversed(obj.modifiers):
        if not mod.type in modifier_types:
            continue
        if not _is_applied(mod, apply_hidden):
            continue
        mod_name = mod.name
        with context_override(context, obj, [obj]):
            bpy.ops.object.modifier_apply(modifier=mod_name)
        assert mod_name not in obj.modifiers
