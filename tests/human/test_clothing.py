import random
from typing import TYPE_CHECKING

import pytest
from HumGen3D.tests.fixtures import context
from HumGen3D.tests.fixtures import finalize_phase_human as human


def test_set_outfit(human, context):
    old_child_count = len(list(human.children))
    options = human.finalize_phase.outfit.get_options()
    chosen = random.choice(options)
    human.finalize_phase.outfit.set(chosen, context)

    assert old_child_count != len(list(human.children))
    assert human.finalize_phase.outfit.objects


@pytest.fixture(scope="class")
def human_with_outfit(human):
    options = human.finalize_phase.outfit.get_options()
    chosen = options[0]
    human.finalize_phase.outfit.set(chosen)
    yield human


def test_remove_outfit(human_with_outfit, context):
    old_child_count = len(list(human_with_outfit.children))
    human_with_outfit.finalize_phase.outfit.remove(context)

    assert len(list(human_with_outfit.children)) < old_child_count


def test_set_texture_resolution(human_with_outfit):
    for obj in human_with_outfit.finalize_phase.outfit.objects:
        for res_categ in ("high", "performance", "medium"):
            human_with_outfit.finalize_phase.outfit.set_texture_resolution(
                obj, res_categ
            )
            # TODO add asserts


def test_randomize_colors(human_with_outfit, context):
    for obj in human_with_outfit.finalize_phase.outfit.objects:
        human_with_outfit.finalize_phase.outfit.randomize_colors(obj, context)


def test_load_pattern(human_with_outfit, context):
    for obj in human_with_outfit.finalize_phase.outfit.objects:
        human_with_outfit.finalize_phase.outfit.pattern.set_random(obj)
