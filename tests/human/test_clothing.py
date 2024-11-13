# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8: noqa F811

import os

import bpy
import pytest  # type:ignore
from pytest_lazyfixture import lazy_fixture
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.geometry import hash_mesh_object
from HumGen3D.common.objects import import_objects_to_scene_collection
from HumGen3D.tests.test_fixtures import *
from HumGen3D.tests.test_fixtures import (
    ALL_HUMAN_FIXTURES,
    CLIPPING_THRESHOLD,
    TESTFILES_PATH,
)


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_set_outfit(human, context):
    old_child_count = len(list(human.children))
    options = human.clothing.outfit.get_options(context)
    human.clothing.outfit.set(options[1], context)

    assert old_child_count != len(list(human.children))
    assert human.clothing.outfit.objects
    assert human.clothing.outfit._calc_percentage_clipping_vertices(context) < 0.05


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_add_obj(human):
    if not os.path.exists(TESTFILES_PATH):
        pytest.skip("Testfiles not found")
    path = os.path.join(TESTFILES_PATH, "clothing", "test_add_obj.blend")
    test_cloth_obj = import_objects_to_scene_collection(path, "test_cloth")
    reference_path = os.path.join(
        get_prefs().filepath, "outfits", "male", "Casual", "Casual_Weekday.blend"
    )
    reference_cloth_obj = import_objects_to_scene_collection(
        reference_path, "HG_TSHIRT_Male.001"
    )
    test_cloth_obj.location = (5, 5, 5)
    try:
        human.clothing.outfit.add_obj(test_cloth_obj)
        assert False, "Should throw exception"
    except HumGenException:
        assert True

    test_cloth_obj.location = human.location
    human.clothing.outfit.add_obj(test_cloth_obj)
    assert (
        human.clothing.outfit._calc_percentage_clipping_vertices(bpy.context)
        < CLIPPING_THRESHOLD
    )
    assert hash_mesh_object(test_cloth_obj) == hash_mesh_object(reference_cloth_obj)


@pytest.fixture(scope="class")
def human_with_outfit(male_human):
    options = male_human.clothing.outfit.get_options(bpy.context)
    chosen = options[0]
    male_human.clothing.outfit.set(chosen, bpy.context)
    yield male_human


@pytest.fixture(scope="class")
def rigify_human_with_outfit(male_rigify_human):
    options = male_rigify_human.clothing.outfit.get_options(bpy.context)
    chosen = options[0]
    male_rigify_human.clothing.outfit.set(chosen, bpy.context)
    yield male_rigify_human


@pytest.mark.parametrize(
    "human",
    [lazy_fixture(f) for f in ["human_with_outfit", "rigify_human_with_outfit"]],
)
def test_remove_outfit(human):
    old_child_count = len(list(human.children))
    cloth_obj_len = len(human.clothing.outfit.objects)
    assert len(list(mod for mod in human.objects.body.modifiers if mod.type == "MASK")) != 0

    human.clothing.outfit.remove()

    assert len(list(human.children)) == old_child_count - cloth_obj_len
    assert len(list(mod for mod in human.objects.body.modifiers if mod.type == "MASK")) == 0

@pytest.mark.parametrize(
    "human",
    [lazy_fixture(f) for f in ["human_with_outfit", "rigify_human_with_outfit"]],
)
def test_remove_outfit_without_removing_masks(human):
    old_child_count = len(list(human.children))
    cloth_obj_len = len(human.clothing.outfit.objects)
    assert len(list(mod for mod in human.objects.body.modifiers if mod.type == "MASK")) != 0

    human.clothing.outfit.remove(remove_masks=False)

    assert len(list(human.children)) == old_child_count - cloth_obj_len
    assert len(list(mod for mod in human.objects.body.modifiers if mod.type == "MASK")) != 0


@pytest.mark.parametrize(
    "human",
    [lazy_fixture(f) for f in ["human_with_outfit", "rigify_human_with_outfit"]],
)
def test_set_texture_resolution(human):
    for obj in human.clothing.outfit.objects:
        for res_categ in ("high", "low", "medium"):
            human.clothing.outfit.set_texture_resolution(obj, res_categ)
            # TODO add asserts


# FIXME fix later
# def test_randomize_colors(human_with_outfit, context):
#     for obj in human_with_outfit.finalize_phase.outfit.objects:
#         human_with_outfit.finalize_phase.outfit.randomize_colors(obj, context)

# FIXME fix later
# def test_load_pattern(human_with_outfit, context):
#     for obj in human_with_outfit.finalize_phase.outfit.objects:
#         human_with_outfit.finalize_phase.outfit.pattern.set_random(obj)
