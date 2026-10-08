# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

import math

import bpy
import numpy as np
import pytest
from mathutils import Euler

from HumGen3D.common.math import create_kdtree
from HumGen3D.human.hair import hair_binding, haircap, haircards
from HumGen3D.human.hair.hair import HAIRCAP_TRIS
from HumGen3D.human.human import Human
from HumGen3D.tests.test_fixtures import *
from HumGen3D.tests.test_fixtures import _create_human
from pytest_lazyfixture import lazy_fixture

LONG_HAIRSTYLE = "Medium Side Part"
SHORT_HAIRSTYLE = "Buzzcut Fade"
BEARD = "Full_Beard_1"
STUBBLE = "Stubble_Short"
EXPRESSION = "big_surprise"
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


def _bearded_human(face_hairstyle, context) -> Human:
    human = _create_human("male")
    options = human.hair.face_hair.get_options(context)
    human.hair.face_hair.set(
        next(option for option in options if face_hairstyle in option), context
    )
    return human


@pytest.fixture
def bearded_human(context) -> Human:
    human = _bearded_human(BEARD, context)
    yield human
    human.delete()


@pytest.fixture
def stubble_human(context) -> Human:
    human = _bearded_human(STUBBLE, context)
    yield human
    human.delete()


def _set_expression(human, context) -> None:
    options = human.expression.get_options(context)
    human.expression.set(next(option for option in options if EXPRESSION in option))
    context.view_layer.update()


def _max_distance_to_body(human, hair_obj, vert_mask, context) -> float:
    body_coords = _evaluated_world_coords(human.objects.body, context)
    kd = create_kdtree(body_coords)
    hair_coords = _evaluated_world_coords(hair_obj, context)
    return max(kd.find(hair_coords[idx])[2] for idx in np.flatnonzero(vert_mask))


def _haircap_image(hair_obj):
    group_node = next(
        node
        for node in hair_obj.data.materials[0].node_tree.nodes
        if node.bl_idname == "ShaderNodeGroup"
    )
    return next(
        node.image
        for node in group_node.node_tree.nodes
        if node.bl_idname == "ShaderNodeTexImage"
    )


def _driven_key_names(hair_obj) -> set[str]:
    keys = hair_obj.data.shape_keys
    if not keys or not keys.animation_data:
        return set()
    return {
        fcurve.data_path.split('"')[1]
        for fcurve in keys.animation_data.drivers
        if fcurve.is_valid
    }


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
    # This hairstyle has no density vertex groups, the density comes from the hairs
    density = _colors(hair_obj)[:, 0]
    assert density.max() == pytest.approx(1)
    assert density.min() == pytest.approx(0)
    assert density.mean() > 0.2


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
    proxy = haircards.HeadProxy.from_human(human)
    with haircards.rest_pose(human.objects.rig, context):
        body = haircards.BodyReference(human, context)
        strands = haircards.extract_strands(
            human, list(human.hair.regular_hair.modifiers), context
        ).card_strands()

    geometry = haircards.build_card_geometry(strands, proxy, body, 4000)
    geometry_again = haircards.build_card_geometry(strands, proxy, body, 4000)
    smaller_geometry = haircards.build_card_geometry(strands, proxy, body, 1000)

    assert np.array_equal(geometry.vertices, geometry_again.vertices)
    assert np.array_equal(geometry.uvs, geometry_again.uvs)
    assert geometry.triangle_count <= 4000
    assert smaller_geometry.triangle_count <= 1000
    assert smaller_geometry.card_count < geometry.card_count


@pytest.mark.parametrize("pack", [True, False])
def test_bake_packs_alpha(long_haired_human, context, tmp_path, pack):
    """The alpha of the cards goes into the color texture, or a texture of its own."""
    from HumGen3D.human.process.settings import TextureSettings

    human = long_haired_human.duplicate(context)
    try:
        hair_obj = human.hair.regular_hair.convert_to_haircards("low", context)
        textures = TextureSettings(
            resolution={key: 128 for key in TextureSettings().resolution},
            pack_hair_alpha=pack,
        )
        human.process.bake_textures(textures, str(tmp_path), only_sets=("hair",), context=context)

        cards = hair_obj.data.materials[1]
        nodes = cards.node_tree.nodes
        color_image = nodes["base_color"].image
        # The images are reloaded from disk, so this checks the saved files
        if pack:
            assert color_image.alpha_mode == "CHANNEL_PACKED"
            assert "alpha" not in nodes
            alpha = np.array(color_image.pixels)[3::4]
            assert nodes["Principled BSDF"].inputs["Alpha"].links[0].from_node == nodes["base_color"]
        else:
            assert color_image.alpha_mode != "CHANNEL_PACKED"
            alpha = np.array(nodes["alpha"].image.pixels)[::4]
            assert nodes["Principled BSDF"].inputs["Alpha"].links[0].from_node == nodes["alpha"]
        assert alpha.max() > alpha.min() + 0.1
        assert (alpha < 0.5).mean() > 0.2, "Most of a card is transparent"
    finally:
        human.delete()


@pytest.mark.parametrize("quality", CARD_QUALITIES)
def test_face_hair_cards(bearded_human, context, quality):
    human = bearded_human
    budget = haircards.FACE_SETTINGS.triangle_budgets[quality]

    hair_obj = human.hair.face_hair.convert_to_haircards(quality, context)

    assert _triangle_count(hair_obj) <= budget
    assert human.hair.face_hair.haircard_obj == hair_obj
    is_card = _card_vert_mask(hair_obj)
    if quality in ("ultra", "high"):
        assert len(hair_obj.data.materials) == 2
        assert is_card.sum() > 100
        # The cards of a beard are small
        card_coords = _evaluated_world_coords(hair_obj, context)[is_card]
        assert np.ptp(card_coords, axis=0).max() < 0.3
        assert _max_distance_to_body(human, hair_obj, is_card, context) < 0.03


@pytest.mark.parametrize(
    "human", [lazy_fixture("bearded_human"), lazy_fixture("stubble_human")]
)
def test_face_hair_texture(human, context):
    hair_obj = human.hair.face_hair.convert_to_haircards("haircap_only", context)

    assert len(hair_obj.data.materials) == 1
    image = _haircap_image(hair_obj)
    assert tuple(image.size) == (haircap.TEXTURE_SIZE, haircap.TEXTURE_SIZE)
    assert image.packed_file, "Drawn texture would be lost when saving the file"
    # Black hairs on a white background
    pixels = np.array(image.pixels)[::4]
    assert pixels.max() == pytest.approx(1)
    assert pixels.min() < 0.5
    assert 0.01 < (pixels < 0.9).mean() < 0.9

    uvs = np.empty(len(hair_obj.data.loops) * 2, dtype=np.float32)
    hair_obj.data.uv_layers.active.data.foreach_get("uv", uvs)
    # The haircap only has polygons where hair is, which fill the texture
    assert uvs.min() >= 0 and uvs.max() <= 1
    assert np.ptp(uvs.reshape((-1, 2)), axis=0).min() > 0.9


@pytest.mark.parametrize("expression_first", [True, False])
def test_follows_expression(bearded_human, context, expression_first):
    human = bearded_human
    if expression_first:
        _set_expression(human, context)

    hair_objs = [
        human.hair.face_hair.convert_to_haircards("medium", context),
        human.hair.eyebrows.convert_to_haircards("medium", context),
    ]
    if not expression_first:
        _set_expression(human, context)

    body = human.objects.body
    expression_key = next(
        key for key in body.data.shape_keys.key_blocks if EXPRESSION in key.name
    )
    coords = {}
    for value in (0, 1):
        expression_key.value = value
        context.view_layer.update()
        coords[value] = [
            _evaluated_world_coords(obj, context) for obj in [body] + hair_objs
        ]

    body_movement = coords[1][0] - coords[0][0]
    for hair_obj, neutral, expressive in zip(hair_objs, coords[0][1:], coords[1][1:]):
        assert expression_key.name in _driven_key_names(hair_obj)
        # Every vertex moves along with the skin it is attached to
        body_vert_idxs = hair_binding.get_attachment(human, hair_obj.data)
        skin_movement = body_movement[body_vert_idxs]
        assert np.abs(skin_movement).max() > 0.003
        assert np.abs(expressive - neutral - skin_movement).max() < 1e-4

        # In both cases the hair has to be on the skin of the neutral face
        on_skin = ~_card_vert_mask(hair_obj)
        expression_key.value = 0
        context.view_layer.update()
        assert _max_distance_to_body(human, hair_obj, on_skin, context) < 0.008


def test_face_rig_shape_keys(bearded_human, context):
    human = bearded_human
    beard_obj = human.hair.face_hair.convert_to_haircards("low", context)
    eyelash_obj = human.hair.eyelashes.convert_to_haircards("low", context)
    keys_before = _driven_key_names(eyelash_obj)

    human.expression.load_facial_rig(context)

    body_key_names = {key.name for key in human.objects.body.data.shape_keys.key_blocks}
    assert "jawOpen" in _driven_key_names(beard_obj)
    assert "eyeBlink_L" in _driven_key_names(eyelash_obj)
    for hair_obj in (beard_obj, eyelash_obj):
        key_names = {key.name for key in hair_obj.data.shape_keys.key_blocks[1:]}
        assert key_names <= body_key_names
        assert key_names == _driven_key_names(hair_obj)

    human.expression.remove_facial_rig()

    assert _driven_key_names(eyelash_obj) == keys_before
    for hair_obj in (beard_obj, eyelash_obj):
        keys = hair_obj.data.shape_keys
        if keys and keys.animation_data:
            assert all(fcurve.is_valid for fcurve in keys.animation_data.drivers)


@pytest.mark.parametrize("quality", ["high", "medium", "low"])
def test_eyelashes_move_rigidly(long_haired_human, context, quality):
    human = long_haired_human
    eyelash_obj = human.hair.eyelashes.convert_to_haircards(quality, context)
    mesh = eyelash_obj.data

    body_vert_idxs = hair_binding.get_attachment(human, mesh)
    is_strip = haircap.EYELASH_SEGMENTS[quality] == 0
    for polygon in mesh.polygons:
        # Every card, or every station of a strip, follows one vertex of the body
        attached_to = set(body_vert_idxs[list(polygon.vertices)])
        assert len(attached_to) == (2 if is_strip else 1)


@pytest.mark.parametrize("quality", CARD_QUALITIES + ["haircap_only"])
def test_eyelash_quality(long_haired_human, context, quality):
    human = long_haired_human
    high_tris = HAIRCAP_TRIS["Eyelashes"]
    segments = haircap.EYELASH_SEGMENTS[quality]

    eyelash_obj = human.hair.eyelashes.convert_to_haircards(quality, context)

    # Lower qualities merge the segments of the lashes or replace the lashes by a
    # strip along the eyelids, the texture runs from the root to the tip either way
    mesh = eyelash_obj.data
    if segments:
        assert _triangle_count(eyelash_obj) == high_tris * segments // 4
    else:
        assert 40 < _triangle_count(eyelash_obj) <= haircap.EYELASH_STRIP_TRIS
    assert all(len(polygon.vertices) == 4 for polygon in mesh.polygons)
    uvs = np.empty(len(mesh.loops) * 2, dtype=np.float32)
    mesh.uv_layers.active.data.foreach_get("uv", uvs)
    assert np.ptp(uvs.reshape((-1, 2)), axis=0).min() > 0.1
    assert all(len(vert.groups) >= 1 for vert in mesh.vertices)
    all_verts = np.ones(len(mesh.vertices), dtype=bool)
    assert _max_distance_to_body(human, eyelash_obj, all_verts, context) < 0.01
    # The lashes of both eyes are there
    coords = _evaluated_world_coords(eyelash_obj, context)
    assert (coords[:, 0] < -0.02).any() and (coords[:, 0] > 0.02).any()
    assert np.ptp(coords[:, 2]) > 0.015


def test_height_change_moves_haircards(long_haired_human, context):
    human = long_haired_human
    hair_obj = human.hair.regular_hair.convert_to_haircards("low", context)
    eyebrow_obj = human.hair.eyebrows.convert_to_haircards("low", context)
    coords_before = _evaluated_world_coords(hair_obj, context)

    human.height.set(human.height.centimeters + 12, context)
    context.view_layer.update()

    coords_after = _evaluated_world_coords(hair_obj, context)
    assert np.abs(coords_after - coords_before).max() > 0.05
    for obj in (hair_obj, eyebrow_obj):
        on_skin = ~_card_vert_mask(obj)
        assert _max_distance_to_body(human, obj, on_skin, context) < 0.006


def test_duplicate_follows_own_body(bearded_human, context):
    human = bearded_human
    _set_expression(human, context)
    human.hair.face_hair.convert_to_haircards("low", context)

    duplicate = human.duplicate(context)

    try:
        duplicate_keys = duplicate.objects.body.data.shape_keys
        hair_keys = duplicate.hair.face_hair.haircard_obj.data.shape_keys
        targets = {
            target.id
            for fcurve in hair_keys.animation_data.drivers
            for variable in fcurve.driver.variables
            for target in variable.targets
        }
        assert targets == {duplicate_keys}
    finally:
        duplicate.delete()


def test_keeps_images_of_other_humans(bearded_human, context):
    # A second human has its own copies of the textures of the first human.
    # Removing one of those copies while the viewport uses it crashes Blender.
    other_human = _create_human("male")
    try:
        image_names = {image.name for image in bpy.data.images}

        for hair_type in ("face_hair", "eyebrows", "eyelashes"):
            getattr(bearded_human.hair, hair_type).convert_to_haircards("low", context)

        assert image_names <= {image.name for image in bpy.data.images}
    finally:
        other_human.delete()



def test_estimate_haircards_triangles(long_haired_human, bearded_human, context):
    human = long_haired_human
    for quality in CARD_QUALITIES:
        estimate = human.hair.estimate_haircards_triangles(quality)
        # The budget of the cards, plus the haircaps of the eyebrows and eyelashes
        assert estimate > haircards.QUALITY_TRIANGLE_BUDGETS[quality]
        assert estimate < haircards.QUALITY_TRIANGLE_BUDGETS[quality] + 3000
    cap_only = human.hair.estimate_haircards_triangles("haircap_only")
    assert 0 < cap_only < human.hair.estimate_haircards_triangles("low")

    # The hair on the face is included, with the budget for face hair
    face_budget = haircards.FACE_SETTINGS.triangle_budgets["high"]
    bearded_estimate = bearded_human.hair.estimate_haircards_triangles("high")
    assert face_budget < bearded_estimate < face_budget + 3000
