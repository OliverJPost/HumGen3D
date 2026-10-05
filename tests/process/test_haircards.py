# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

import math

import bpy
import numpy as np
import pytest
from mathutils import Euler

from HumGen3D.common.math import create_kdtree
from HumGen3D.human.hair import haircards
from HumGen3D.human.human import Human
from HumGen3D.tests.test_fixtures import *
from HumGen3D.tests.test_fixtures import _create_human
from pytest_lazyfixture import lazy_fixture

LONG_HAIRSTYLE = "Medium Side Part"
SHORT_HAIRSTYLE = "Buzzcut Fade"
CARD_QUALITIES = ["ultra", "high", "medium", "low"]


def _human_with_hair(gender, hairstyle, context) -> Human:
    human = _create_human(gender)
    options = human.hair.regular_hair.get_options(context)
    human.hair.regular_hair.set(
        next(option for option in options if hairstyle in option), context
    )
    return human


@pytest.fixture
def long_haired_human(context) -> Human:
    human = _human_with_hair("female", LONG_HAIRSTYLE, context)
    yield human
    human.delete()


@pytest.fixture
def short_haired_human(context) -> Human:
    human = _human_with_hair("female", SHORT_HAIRSTYLE, context)
    yield human
    human.delete()


@pytest.fixture
def long_haired_rigify_human(context) -> Human:
    human = _human_with_hair("male", LONG_HAIRSTYLE, context)
    human.pose.rigify.generate(context)
    yield human
    human.delete()


def _triangle_count(obj) -> int:
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def _evaluated_world_coords(obj, context) -> np.ndarray:
    depsgraph = context.evaluated_depsgraph_get()
    depsgraph.update()
    obj_eval = obj.evaluated_get(depsgraph)
    coords = np.empty(len(obj_eval.data.vertices) * 3, dtype=np.float64)
    obj_eval.data.vertices.foreach_get("co", coords)
    matrix = np.array(obj.matrix_world)
    return coords.reshape((-1, 3)) @ matrix[:3, :3].T + matrix[:3, 3]


def _card_vert_mask(obj) -> np.ndarray:
    """Mask of the vertices that belong to the cards instead of the haircap."""
    mask = np.zeros(len(obj.data.vertices), dtype=bool)
    for polygon in obj.data.polygons:
        if polygon.material_index == 1:
            mask[list(polygon.vertices)] = True
    return mask


def _colors(obj) -> np.ndarray:
    colors = np.empty(len(obj.data.vertices) * 4, dtype=np.float32)
    attribute = obj.data.color_attributes[haircards.COLOR_ATTRIBUTE]
    attribute.data.foreach_get("color", colors)
    return colors.reshape((-1, 4))


def _hair_node_value(material, input_name) -> float:
    node = next(
        node for node in material.node_tree.nodes if node.bl_idname == "ShaderNodeGroup"
    )
    return node.inputs[input_name].default_value


@pytest.mark.parametrize("quality", CARD_QUALITIES)
def test_triangle_budget(long_haired_human, context, quality):
    human = long_haired_human
    budget = haircards.QUALITY_TRIANGLE_BUDGETS[quality]

    hair_obj = human.hair.regular_hair.convert_to_haircards(quality, context)

    assert 0.9 * budget <= _triangle_count(hair_obj) <= budget
    assert human.process.has_haircards
    assert human.hair.regular_hair.haircard_obj == hair_obj
    assert len(hair_obj.data.materials) == 2


def test_custom_triangle_budget(long_haired_human, context):
    hair_obj = long_haired_human.hair.regular_hair.convert_to_haircards(
        "high", context, triangle_budget=6000
    )

    assert 5400 <= _triangle_count(hair_obj) <= 6000


def test_haircap_only(long_haired_human, context):
    human = long_haired_human

    hair_obj = human.hair.regular_hair.convert_to_haircards("haircap_only", context)

    assert len(hair_obj.data.materials) == 1
    # This hairstyle has no density vertex groups, the density comes from the roots
    density = _colors(hair_obj)[:, 0]
    assert density.max() == pytest.approx(1)
    assert 0.2 < density.mean() < 0.95


def test_short_hair_only_gets_haircap(short_haired_human, context):
    human = short_haired_human

    hair_obj = human.hair.regular_hair.convert_to_haircards("ultra", context)

    assert len(hair_obj.data.materials) == 1
    assert _triangle_count(hair_obj) < haircards.QUALITY_TRIANGLE_BUDGETS["low"]


def test_conversion_restores_human(long_haired_human, context):
    human = long_haired_human
    rig = human.objects.rig
    particle_systems = list(human.hair.regular_hair.particle_systems)
    children_before = [ps.settings.child_percent for ps in particle_systems]
    mesh_count_before = len(bpy.data.meshes)

    human.hair.regular_hair.convert_to_haircards("low", context)

    assert rig.data.pose_position == "POSE"
    assert children_before == [ps.settings.child_percent for ps in particle_systems]
    # Only the mesh of the haircard object itself is added
    assert len(bpy.data.meshes) == mesh_count_before + 1


def test_hair_color(long_haired_human, context):
    human = long_haired_human
    human.hair.regular_hair.lightness.value = 1.7
    human.hair.regular_hair.redness.value = 0.3

    hair_obj = human.hair.regular_hair.convert_to_haircards("low", context)

    for material in hair_obj.data.materials:
        assert _hair_node_value(material, "Lightness") == pytest.approx(1.7)
        assert _hair_node_value(material, "Redness") == pytest.approx(0.3)

    human.hair.regular_hair.lightness.value = 0.4
    for material in hair_obj.data.materials:
        assert _hair_node_value(material, "Lightness") == pytest.approx(0.4)

    assert human.materials.haircap == [hair_obj.data.materials[0]]
    assert human.materials.haircards == [hair_obj.data.materials[1]]


def test_card_mesh_data(long_haired_human, context):
    hair_obj = long_haired_human.hair.regular_hair.convert_to_haircards("high", context)
    mesh = hair_obj.data
    is_card = _card_vert_mask(hair_obj)

    assert mesh.has_custom_normals

    colors = _colors(hair_obj)[is_card]
    assert colors.min() >= 0 and colors.max() <= 1
    # Root to tip in red, a value per card in green and the layer in blue
    for channel in range(3):
        assert colors[:, channel].min() == pytest.approx(0, abs=0.01)
        assert colors[:, channel].max() == pytest.approx(1, abs=0.01)

    uvs = np.empty(len(mesh.loops) * 2, dtype=np.float32)
    mesh.uv_layers.active.data.foreach_get("uv", uvs)
    uvs = uvs.reshape((-1, 2))
    assert uvs.min() >= 0 and uvs.max() <= 1
    for polygon in mesh.polygons:
        if polygon.material_index != 1:
            continue
        assert polygon.area > 1e-10
        polygon_uvs = uvs[list(polygon.loop_indices)]
        assert np.ptp(polygon_uvs, axis=0).min() > 1e-5, "Face has no area in UV map"


@pytest.mark.parametrize(
    "human",
    [lazy_fixture("long_haired_human"), lazy_fixture("long_haired_rigify_human")],
)
def test_skinned_to_rig(human, context):
    rig = human.objects.rig

    hair_obj = human.hair.regular_hair.convert_to_haircards("medium", context)

    assert hair_obj.parent == rig
    assert hair_obj.parent_type == "OBJECT"
    assert [mod.object for mod in hair_obj.modifiers if mod.type == "ARMATURE"] == [rig]

    deform_bones = {bone.name for bone in rig.data.bones if bone.use_deform}
    assert {vg.name for vg in hair_obj.vertex_groups} <= deform_bones
    for vert in hair_obj.data.vertices:
        assert 1 <= len(vert.groups) <= haircards.MAX_BONE_INFLUENCES
        assert sum(group.weight for group in vert.groups) == pytest.approx(1, abs=1e-3)


def test_follows_pose(long_haired_human, context):
    human = long_haired_human
    human.location = (1, 2, 0)
    head_bone = human.pose.get_posebone_by_original_name("head")
    head_bone.rotation_mode = "XYZ"
    head_bone.rotation_euler = Euler((math.radians(25), math.radians(30), 0))
    context.view_layer.update()

    # Converting a posed human should give the same result as an unposed human
    hair_obj = human.hair.regular_hair.convert_to_haircards("medium", context)

    body_coords = _evaluated_world_coords(human.objects.body, context)
    kd = create_kdtree(body_coords)
    hair_coords = _evaluated_world_coords(hair_obj, context)
    is_card = _card_vert_mask(hair_obj)
    is_root = is_card & (_colors(hair_obj)[:, 0] < 1e-6)
    assert is_root.sum() > 10
    for vert_idx in np.flatnonzero(is_root | ~is_card):
        distance = kd.find(hair_coords[vert_idx])[2]
        assert distance < 0.02, "Haircap or root of card is not on the posed head"


@pytest.mark.parametrize("hair_type", ["eyebrows", "eyelashes"])
def test_eye_hair(long_haired_human, context, hair_type):
    human = long_haired_human
    rig = human.objects.rig

    hair_obj = getattr(human.hair, hair_type).convert_to_haircards("high", context)

    assert hair_obj in human.objects.haircards
    assert getattr(human.hair, hair_type).haircard_obj == hair_obj
    assert [mod.object for mod in hair_obj.modifiers if mod.type == "ARMATURE"] == [rig]
    assert all(len(vert.groups) >= 1 for vert in hair_obj.data.vertices)


def test_same_strands_give_same_cards(long_haired_human, context):
    human = long_haired_human
    body = haircards.BodyReference(human)
    proxy = haircards.HeadProxy.from_human(human)
    with haircards.rest_pose(human.objects.rig, context):
        strands = haircards.extract_strands(
            human, list(human.hair.regular_hair.modifiers), context
        )

    geometry = haircards.build_card_geometry(strands, proxy, body, 4000)
    geometry_again = haircards.build_card_geometry(strands, proxy, body, 4000)
    smaller_geometry = haircards.build_card_geometry(strands, proxy, body, 1000)

    assert np.array_equal(geometry.vertices, geometry_again.vertices)
    assert np.array_equal(geometry.uvs, geometry_again.uvs)
    assert geometry.triangle_count <= 4000
    assert smaller_geometry.triangle_count <= 1000
    assert smaller_geometry.card_count < geometry.card_count


def test_bake_packs_alpha(long_haired_human, context, tmp_path):
    human = long_haired_human
    bake_sett = context.scene.HG3D.process.baking
    bake_sett.res_haircards = "128"
    bake_sett.pack_haircard_alpha = True
    hair_obj = human.hair.regular_hair.convert_to_haircards("low", context)

    baking = human.process.baking
    baking._check_bake_render_settings(context, 4, force_cycles=True)
    baketextures = [
        baketexture
        for baketexture in baking.get_baking_list()
        if baketexture.bake_object == hair_obj
    ]
    for baketexture in baketextures:
        baking.bake_single_texture(baketexture, str(tmp_path), context=context)
    baking.set_up_new_materials(baketextures)

    for material in hair_obj.data.materials:
        color_image = material.node_tree.nodes["Base Color"].image
        alpha_image = material.node_tree.nodes["Alpha"].image
        assert color_image.alpha_mode == "CHANNEL_PACKED"
        # The images are reloaded from disk, so this checks the saved files
        packed_alpha = np.array(color_image.pixels)[3::4]
        baked_alpha = np.array(alpha_image.pixels)[::4]
        assert packed_alpha.max() > packed_alpha.min() + 0.1
        assert np.allclose(packed_alpha, baked_alpha, atol=0.02)
