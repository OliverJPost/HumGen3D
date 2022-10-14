# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE


import bpy
import pytest  # type:ignore
from HumGen3D.tests.fixtures import (  # noqa
    ALL_HUMAN_FIXTURES,
    context,
    female_human,
    male_human,
)


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_set_outfit(human, context):
    old_child_count = len(list(human.children))
    options = human.outfit.get_options(context)
    human.outfit.set(options[1], context)

    assert old_child_count != len(list(human.children))
    assert human.outfit.objects
    assert human.outfit._calc_percentage_clipping_vertices(context) < 0.05


@pytest.fixture(scope="class")
def human_with_outfit(male_human):
    options = male_human.outfit.get_options(bpy.context)
    chosen = options[0]
    male_human.outfit.set(chosen, bpy.context)
    yield male_human


def test_remove_outfit(human_with_outfit):
    old_child_count = len(list(human_with_outfit.children))
    cloth_obj_len = len(human_with_outfit.outfit.objects)
    human_with_outfit.outfit.remove()

    assert len(list(human_with_outfit.children)) == old_child_count - cloth_obj_len


def test_set_texture_resolution(human_with_outfit):
    for obj in human_with_outfit.outfit.objects:
        for res_categ in ("high", "performance", "optimised"):
            human_with_outfit.outfit.set_texture_resolution(obj, res_categ)
            # TODO add asserts


# FIXME fix later
# def test_randomize_colors(human_with_outfit, context):
#     for obj in human_with_outfit.finalize_phase.outfit.objects:
#         human_with_outfit.finalize_phase.outfit.randomize_colors(obj, context)

# FIXME fix later
# def test_load_pattern(human_with_outfit, context):
#     for obj in human_with_outfit.finalize_phase.outfit.objects:
#         human_with_outfit.finalize_phase.outfit.pattern.set_random(obj)
