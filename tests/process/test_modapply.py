# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

import bpy
import numpy as np
import pytest

from HumGen3D.human.process.apply_modifiers import apply_modifiers, refresh_modapply
from HumGen3D.tests.test_fixtures import *
from pytest_lazyfixture import lazy_fixture


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_armature_apply(human, context):
    # human as context.object
    context.view_layer.objects.active = human.objects.rig
    refresh_modapply(None, context)
    col = context.scene.modapply_col

    for item in col:
        if item.mod_type == "ARMATURE":
            item.enabled = True
            break
    apply_modifiers(human, context=context)


def _evaluated_coords(obj, context):
    depsgraph = context.evaluated_depsgraph_get()
    depsgraph.update()
    obj_eval = obj.evaluated_get(depsgraph)
    coords = np.empty(len(obj_eval.data.vertices) * 3, dtype=np.float64)
    obj_eval.data.vertices.foreach_get("co", coords)
    return coords


def _shapekey_offsets(obj):
    offsets = {}
    for sk in obj.data.shape_keys.key_blocks:
        if sk.name.startswith(("Basis", "LIVE_KEY")):
            continue
        coords = np.empty(len(sk.data) * 3, dtype=np.float64)
        sk.data.foreach_get("co", coords)
        basis_coords = np.empty(len(sk.data) * 3, dtype=np.float64)
        sk.relative_key.data.foreach_get("co", basis_coords)
        offsets[sk.name] = coords - basis_coords

    return offsets


@pytest.mark.parametrize(
    "human", [lazy_fixture("male_human"), lazy_fixture("female_human")]
)
def test_modapply_keeps_shape(human, context):
    body = human.objects.body
    for obj in context.selected_objects:
        obj.select_set(False)
    human.objects.rig.select_set(True)
    context.view_layer.objects.active = human.objects.rig
    refresh_modapply(None, context)
    for item in context.scene.modapply_col:
        item.enabled = item.mod_type == "ARMATURE"

    coords = _evaluated_coords(body, context)
    sk_offsets = _shapekey_offsets(body)
    apply_modifiers(human, context=context)

    assert not [mod for mod in body.modifiers if mod.type == "ARMATURE"]
    np.testing.assert_allclose(_evaluated_coords(body, context), coords, atol=1e-5)
    # Applying the live keys should not change what the other shape keys do
    for sk_name, offsets in _shapekey_offsets(body).items():
        np.testing.assert_allclose(offsets, sk_offsets[sk_name], atol=1e-5)
