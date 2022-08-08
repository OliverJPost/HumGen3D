import random
from typing import TYPE_CHECKING
import bpy
import pytest # type:ignore
from HumGen3D.tests.fixtures import ALL_FINALIZE_FIXTURES, context
from HumGen3D.tests.fixtures import *

@pytest.mark.parametrize("human", ALL_FINALIZE_FIXTURES)
def test_set_outfit(human, context):
    old_child_count = len(list(human.children))
    options = human.finalize_phase.outfit.get_options(context)
    chosen = random.choice(options)
    human.finalize_phase.outfit.set(chosen, context)

    assert old_child_count != len(list(human.children))
    assert human.finalize_phase.outfit.objects


@pytest.fixture(scope="class")
def human_with_outfit(finalize_phase_human):
    options = finalize_phase_human.finalize_phase.outfit.get_options(bpy.context)
    chosen = options[0]
    finalize_phase_human.finalize_phase.outfit.set(chosen, bpy.context)
    yield finalize_phase_human


def test_remove_outfit(human_with_outfit, context):
    old_child_count = len(list(human_with_outfit.children))
    human_with_outfit.finalize_phase.outfit.remove()

    assert len(list(human_with_outfit.children)) < old_child_count


def test_set_texture_resolution(human_with_outfit):
    for obj in human_with_outfit.finalize_phase.outfit.objects:
        for res_categ in ("high", "performance", "optimised"):
            human_with_outfit.finalize_phase.outfit.set_texture_resolution(
                obj, res_categ
            )
            # TODO add asserts

#FIXME fix later
# def test_randomize_colors(human_with_outfit, context):
#     for obj in human_with_outfit.finalize_phase.outfit.objects:
#         human_with_outfit.finalize_phase.outfit.randomize_colors(obj, context)

# FIXME fix later
# def test_load_pattern(human_with_outfit, context):
#     for obj in human_with_outfit.finalize_phase.outfit.objects:
#         human_with_outfit.finalize_phase.outfit.pattern.set_random(obj)
