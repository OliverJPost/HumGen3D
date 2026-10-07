# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8: noqa F811

import contextlib
import os

import bpy
import pytest  # type:ignore
from pytest_lazyfixture import lazy_fixture
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.common.geometry import world_coords_from_obj
from HumGen3D.common.objects import import_objects_to_scene_collection
from HumGen3D.human.clothing.saving import is_valid_clothing_object
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
    test_cloth_obj.location = human.location
    bpy.context.view_layer.update()
    worn_coords = world_coords_from_obj(test_cloth_obj)

    solver = human.clothing.outfit.add_obj(test_cloth_obj, "torso")
    assert solver != "closest_point"
    assert (
        human.clothing.outfit._calc_percentage_clipping_vertices(bpy.context)
        < CLIPPING_THRESHOLD
    )

    # Only weighted to deform bones, and every vertex is weighted
    bones = human.objects.rig.data.bones
    assert all(vg.name in bones for vg in test_cloth_obj.vertex_groups)
    assert all(len(v.groups) > 0 for v in test_cloth_obj.data.vertices)

    # On the human it was added to, the object still looks like it did
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = test_cloth_obj.evaluated_get(depsgraph)
    new_coords = world_coords_from_obj(evaluated, data=evaluated.data.vertices)
    assert abs(new_coords - worn_coords).max() < 0.002


@contextlib.contextmanager
def _content_library(path):
    """Point the add-on at another content folder for the duration of the block."""
    pref = get_prefs()
    original = pref.filepath_
    os.makedirs(os.path.join(path, "content_packs"), exist_ok=True)
    # Only the existence of this file is checked when loading content
    with open(os.path.join(path, "content_packs", "Base_Humans.json"), "w") as f:
        f.write("{}")
    pref.filepath_ = str(path)
    try:
        yield
    finally:
        pref.filepath_ = original


def _tube_on_torso(human, context):
    """A cylinder around the torso with a texture that only exists in memory."""
    rig = human.objects.rig
    bones = rig.pose.bones
    bottom = (rig.matrix_world @ bones["spine.001"].head).z
    top = (rig.matrix_world @ bones["spine.003"].tail).z
    center = rig.matrix_world @ bones["spine.001"].head
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=32,
        radius=0.22,
        depth=top - bottom,
        location=(center.x, center.y, (top + bottom) / 2),
    )
    tube = context.object
    tube.name = "pytest_shirt"
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.subdivide(number_cuts=4)
    bpy.ops.object.mode_set(mode="OBJECT")

    mat = bpy.data.materials.new("pytest_shirt_mat")
    mat.use_nodes = True
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = bpy.data.images.new("pytest_shirt_albedo", 16, 16)
    tube.data.materials.append(mat)
    return tube


def test_save_and_load_outfit(female_human, male_human, context, tmp_path):
    """Add a mesh as clothing, save it for both genders and load it on a male."""
    human = female_human
    human.clothing.outfit.remove()
    shirt = _tube_on_torso(human, context)
    human.clothing.outfit.add_obj(shirt, "torso", context=context)
    assert is_valid_clothing_object(shirt)

    library = tmp_path / "content"
    with _content_library(library):
        processes = human.clothing.outfit.save_to_library(
            "pytest_shirt", category="Pytest", context=context
        )
        for process in processes:
            assert process.wait(timeout=180) == 0
        # Saving leaves the scene as it was
        assert shirt.name == "pytest_shirt"
        assert human.clothing.outfit.objects == [shirt]

        for gender in ("male", "female"):
            path = library / "outfits" / gender / "Pytest" / "pytest_shirt.blend"
            assert path.is_file()
            with bpy.data.libraries.load(str(path)) as (data_from, _):
                assert "pytest_shirt" in data_from.objects
                # Everything else is stripped by a Blender executable. Without
                # one (bpy as module) set HG_BLENDER_BINARY to test this too.
                if processes:
                    assert data_from.objects == ["pytest_shirt"]
                    assert not data_from.armatures
                    assert data_from.materials == ["pytest_shirt_mat"]
        textures = os.listdir(library / "outfits" / "textures")
        assert textures == ["pytest_shirt_albedo.png"]

        male_human.clothing.outfit.remove()
        object_count = len(bpy.data.objects)
        male_human.clothing.outfit.set(
            os.path.join("outfits", "male", "Pytest", "pytest_shirt.blend"), context
        )
    loaded = male_human.clothing.outfit.objects
    # .001 because the original is still in the scene
    assert [obj.name for obj in loaded] == ["pytest_shirt.001"]
    if processes:
        assert len(bpy.data.objects) == object_count + 1
    keys = loaded[0].data.shape_keys
    assert "Body Proportions" in keys.key_blocks
    assert all(
        driver.driver.variables[0].targets[0].id == male_human.objects.rig
        for driver in keys.animation_data.drivers
    )
    assert (
        male_human.clothing.outfit._calc_percentage_clipping_vertices(context)
        < CLIPPING_THRESHOLD
    )


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
