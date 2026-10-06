# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

import pytest

from HumGen3D.tests.test_fixtures import *

ORIGINAL_TEETH_TRIS_COUNT = 12_360
MAX_TEETH_TRIS_COUNTS = {1: 5000, 2: 3600}


def _tris_count(obj):
    return sum(len(polygon.vertices) - 2 for polygon in obj.data.polygons)


def _teeth_tris_count(human):
    return _tris_count(human.objects.upper_teeth) + _tris_count(
        human.objects.lower_teeth
    )


@pytest.mark.parametrize("lod", [1, 2])
def test_teeth_lod(male_human, context, lod):
    human = male_human
    assert _teeth_tris_count(human) == ORIGINAL_TEETH_TRIS_COUNT
    active_object = context.view_layer.objects.active

    human.process.lod.set_teeth_lod(lod, context=context)

    assert 0 < _teeth_tris_count(human) <= MAX_TEETH_TRIS_COUNTS[lod]
    assert context.mode == "OBJECT"
    assert context.view_layer.objects.active == active_object
    for obj in (human.objects.upper_teeth, human.objects.lower_teeth):
        assert obj["hg_lod"] == lod
        assert not obj.data.has_custom_normals
        # Every part is still skinned to the single jaw bone
        for vert in obj.data.vertices:
            weights = [group.weight for group in vert.groups if group.weight > 0]
            assert weights == [pytest.approx(1)]

    # The teeth can only be decimated from their original resolution
    with pytest.raises(ValueError):
        human.process.lod.set_teeth_lod(lod, context=context)


def test_teeth_lod_original(male_human, context):
    male_human.process.lod.set_teeth_lod(0, context=context)

    assert _teeth_tris_count(male_human) == ORIGINAL_TEETH_TRIS_COUNT
    assert "hg_lod" not in male_human.objects.upper_teeth


def test_teeth_lod_keeps_tongue_shape_keys(male_human, context):
    human = male_human
    human.expression.load_facial_rig(context)
    lower_teeth = human.objects.lower_teeth
    key_names = [key.name for key in lower_teeth.data.shape_keys.key_blocks]
    assert "tongue_out" in key_names

    human.process.lod.set_teeth_lod(1, context=context)

    shape_keys = lower_teeth.data.shape_keys
    assert [key.name for key in shape_keys.key_blocks] == key_names
    assert len(shape_keys.animation_data.drivers) == len(key_names) - 1
    basis = shape_keys.key_blocks["Basis"].data
    tongue_out = shape_keys.key_blocks["tongue_out"].data
    max_movement = max(
        (tongue_out[i].co - basis[i].co).length for i in range(len(basis))
    )
    assert max_movement > 0.03


def test_estimate_triangles(male_human, context):
    human = male_human
    options = human.clothing.outfit.get_options(context)
    human.clothing.outfit.set(options[0], context)

    estimate = human.process.lod.estimate_triangles()

    # Without LODs the estimate is the exact count of the base meshes
    assert estimate["body"] == _tris_count(human.objects.body)
    assert estimate["eyes"] == _tris_count(human.objects.eyes)
    assert estimate["teeth"] == _teeth_tris_count(human)
    assert estimate["clothing"] == sum(
        _tris_count(obj) for obj in human.clothing.outfit.objects
    )

    lower = human.process.lod.estimate_triangles(
        body_lod=2, clothing="low", eyes="low", teeth=2
    )
    assert all(0 < lower[key] < estimate[key] for key in estimate)
    # Keeping the subdivision modifiers multiplies the clothing count
    kept_subdiv = human.process.lod.estimate_triangles(
        remove_clothing_subdiv=False
    )
    assert kept_subdiv["clothing"] > estimate["clothing"]
