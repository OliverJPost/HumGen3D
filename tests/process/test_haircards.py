# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

import math
import os

import bpy
import numpy as np
import pytest
from mathutils import Euler

from HumGen3D.common.math import create_kdtree
from HumGen3D.human.hair import card_atlas, hair_binding, haircap, haircards
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


def _cover(obj) -> np.ndarray:
    cover = np.empty(len(obj.data.vertices), dtype=np.float32)
    obj.data.attributes[haircap.COVER_ATTRIBUTE].data.foreach_get("value", cover)
    return cover


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


def test_haircap_is_solid_under_the_hair(long_haired_human, context):
    hair_obj = long_haired_human.hair.regular_hair.convert_to_haircards("high", context)

    on_cap = ~_card_vert_mask(hair_obj)
    cover = _cover(hair_obj)[on_cap]
    density = _colors(hair_obj)[on_cap, 0]
    # Solid under the mass of the hair, the see-through film it was at the hairline
    assert (cover > 0.9).mean() > 0.3
    assert cover[density == 0].max() == 0
    assert cover.min() == 0
    material = hair_obj.data.materials[0]
    shader = next(
        node
        for node in material.node_tree.nodes
        if node.bl_idname == "ShaderNodeBsdfPrincipled"
    )
    opacity = shader.inputs["Alpha"].links[0].from_node
    assert opacity.use_clamp
    assert all(socket.is_linked for socket in opacity.inputs[:2])


def test_haircap_of_short_hair_stays_see_through(short_haired_human, context):
    hair_obj = short_haired_human.hair.regular_hair.convert_to_haircards(
        "ultra", context
    )

    assert _cover(hair_obj).max() == 0


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


def _plain(value):
    return tuple(round(v, 6) for v in value) if hasattr(value, "__len__") else value


def _principled_sources(material):
    principled = next(
        n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"
    )
    return {
        socket.identifier: (
            (socket.links[0].from_node.name, socket.links[0].from_socket.identifier)
            if socket.links
            else _plain(getattr(socket, "default_value", None))
        )
        for socket in principled.inputs
        if socket.enabled
    }


def test_blender_look_is_left_out_of_the_bake(long_haired_human, context):
    context.scene.cycles.transparent_max_bounces = 8
    hair_obj = long_haired_human.hair.regular_hair.convert_to_haircards("low", context)
    material = hair_obj.data.materials[1]
    look = [
        n for n in material.node_tree.nodes if n.name.startswith(haircards.BLENDER_LOOK_PREFIX)
    ]
    assert look
    assert context.scene.cycles.transparent_max_bounces >= 64

    plain = material.copy()
    haircards.remove_blender_look(plain)
    assert not any(
        n.name.startswith(haircards.BLENDER_LOOK_PREFIX) for n in plain.node_tree.nodes
    )
    sources = _principled_sources(plain)
    assert sources["Base Color"][0] == haircards.GREY_HAIR_NODE_NAME
    assert sources["Alpha"][0] == "HG_Hair"

    again = plain.copy()
    haircards.add_blender_look(again)
    assert _principled_sources(again) != sources
    haircards.remove_blender_look(again)
    assert _principled_sources(again) == sources
    bpy.data.materials.remove(plain)
    bpy.data.materials.remove(again)


def test_blender_look_reads_own_atlas(long_haired_human, context):
    """The card material of a second human is a copy of the first one's."""
    second = _human_with_hair("male", LONG_HAIRSTYLE, context)
    for human in (long_haired_human, second):
        human.hair.regular_hair.convert_to_haircards("low", context)
        material = human.materials.haircards[0]
        group = next(n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeGroup")
        atlas = next(
            n.image
            for n in group.node_tree.nodes
            if n.bl_idname == "ShaderNodeTexImage" and n.image and "_ALPHA" in n.image.name
        )
        look_images = {
            n.image
            for n in material.node_tree.nodes
            if n.name.startswith(haircards.BLENDER_LOOK_PREFIX) and getattr(n, "image", None)
        }
        assert look_images == {atlas}
    second.delete()


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


def test_counts_hair_around_strands():
    """A lock on its own has no hair of other clumps around it, one in a bundle has."""
    rng = np.random.default_rng(0)
    along = np.linspace(0, 0.2, haircards.STATIONS)

    def lock(x, count):
        points = np.zeros((count, haircards.STATIONS, 3))
        points[..., 0] = x + rng.normal(0, 0.001, (count, 1))
        points[..., 1] = rng.normal(0, 0.001, (count, 1))
        points[..., 2] = -along
        return points

    # Two locks side by side and one 10 cm away
    points = np.concatenate((lock(0, 20), lock(0.004, 20), lock(0.1, 20)))
    labels = np.repeat(np.arange(3), 20)
    strands = haircards.HairStrands(
        points=points,
        system=np.zeros(60, dtype=np.int64),
        weights=np.full(60, 2.0),
        for_cards=np.ones(60, dtype=bool),
        density_points=np.zeros((0, 3)),
    )

    around = haircards._hair_around(strands, labels, 0.008)

    assert around.shape == (60, haircards.STATIONS)
    # The 20 strands of the other lock, 2 hairs each, in up to three cells along them
    assert around[:40].min() >= 40
    assert np.allclose(around[:20], around[20:40])
    assert np.allclose(around[40:], 0)


def test_loose_locks_get_a_crossing_card(long_haired_human, context):
    human = long_haired_human
    proxy = haircards.HeadProxy.from_human(human)
    with haircards.rest_pose(human.objects.rig, context):
        body = haircards.BodyReference(human, context)
        strands = haircards.extract_strands(
            human, list(human.hair.regular_hair.modifiers), context
        ).card_strands()
    # A lock of strands that hangs 10 cm away from the rest of the hair
    lock = strands.points[:8].copy()
    lock[..., 0] += lock[:, :1, 0].max() - lock[..., 0].min() + 0.1
    with_lock = haircards.HairStrands(
        points=np.concatenate((strands.points, lock)),
        system=np.concatenate((strands.system, np.full(8, strands.system.max() + 1))),
        weights=np.concatenate((strands.weights, strands.weights[:8])),
        for_cards=np.ones(len(strands.points) + 8, dtype=bool),
        density_points=strands.density_points,
        diameters=np.concatenate((strands.diameters, strands.diameters[:8])),
    )
    labels = haircards._cluster_strands(with_lock, proxy, 300)

    cards = haircards._fit_cards(with_lock, labels, proxy, body, haircards.SCALP_SETTINGS)

    lock_clumps = np.unique(labels[-8:])
    for clump in lock_clumps:
        assert (cards.clump == clump).sum() == 2, "A loose lock gets a card across it"
    assert len(cards) < 2 * (labels.max() + 1), "The hair as a whole doesn't"


@pytest.fixture
def afro_human(context) -> Human:
    human = _human_with_hair("male", "Curly Afro", context)
    yield human
    human.delete()


def _card_strands(human, context):
    proxy = haircards.HeadProxy.from_human(human)
    with haircards.rest_pose(human.objects.rig, context):
        body = haircards.BodyReference(human, context)
        strands = haircards.extract_strands(
            human, list(human.hair.regular_hair.modifiers), context
        ).card_strands()
    return strands, proxy, body


def test_straightness_tells_curls_from_bends():
    """Hair that bends around the head is straight, hair that winds is not."""
    along = np.linspace(0, 1, haircards.STATIONS)
    straight = np.stack((along * 0.2, along * 0, along * 0), axis=1)
    angle = along * math.pi / 2
    bent = np.stack((np.sin(angle) * 0.1, (1 - np.cos(angle)) * 0.1, along * 0), axis=1)
    turns = along * 2 * math.pi * 5
    curl = np.stack((along * 0.1, np.cos(turns) * 0.01, np.sin(turns) * 0.01), axis=1)

    straightness = haircards._strand_straightness(np.stack((straight, bent, curl)))

    low, high = haircards.CURLY_STRAIGHTNESS
    assert straightness[0] == pytest.approx(1, abs=0.01)
    assert straightness[1] > high
    assert straightness[2] < low


def test_standing_curls_get_shells(afro_human, context):
    """An afro is looked at along its hairs, so it gets cards across them too."""
    strands, proxy, body = _card_strands(afro_human, context)

    geometry = haircards.build_card_geometry(strands, proxy, body, 8000)

    layout = geometry.atlas
    shells = np.flatnonzero(layout.slab > 0)
    assert geometry.triangle_count <= 8000
    assert 20 < len(shells) < geometry.card_count / 2
    # A shell lies across the hair: its front is the outward direction
    middle = haircards.STATIONS // 2
    lengthwise = layout.centers[shells, -1] - layout.centers[shells, 0]
    fronts = np.cross(lengthwise, layout.sides[shells, middle])
    fronts /= np.linalg.norm(fronts, axis=1, keepdims=True)
    outward, _ = proxy.outward(layout.centers[shells, middle])
    facing = np.einsum("ni,ni->n", fronts, outward)
    assert np.median(facing) > 0.95
    assert facing.min() > 0.5
    # and is well away from the skin, where the haircap is
    assert body.distances(layout.centers[shells, middle]).min() > haircards.SHELL_MIN_HEIGHT / 2
    # One card of every tile of curls and shells draws its hair onto it, the
    # others use what it drew
    drawing = np.bincount(layout.tile_of_card, weights=layout.draw_share > 0)
    assert np.all(drawing[np.unique(layout.tile_of_card[shells])] == 1)
    assert np.all(drawing >= 1)


def test_hair_that_lies_on_the_head_gets_no_shells(long_haired_human, context):
    strands, proxy, body = _card_strands(long_haired_human, context)

    geometry = haircards.build_card_geometry(strands, proxy, body, 8000)

    layout = geometry.atlas
    assert not (layout.slab > 0).any()
    # Straight hair is averaged over the cards of a tile
    cards_per_tile = np.bincount(layout.tile_of_card)
    assert np.allclose(layout.draw_share, 1 / cards_per_tile[layout.tile_of_card])


def test_shell_is_drawn_as_a_tuft(afro_human, context):
    """A shell shows the hair below it, closed in its middle and open at its corners."""
    human = afro_human
    strands, proxy, body = _card_strands(human, context)
    geometry = haircards.build_card_geometry(strands, proxy, body, 8000)
    layout = geometry.atlas
    with haircards.rest_pose(human.objects.rig, context):
        dense = haircards.extract_strands(
            human,
            list(human.hair.regular_hair.modifiers),
            context,
            max_strands=card_atlas.DRAW_STRANDS_PER_SYSTEM,
            stations=card_atlas.DRAW_STATIONS,
        ).card_strands()
    labels = haircards.assign_clumps(dense, proxy, layout)

    images = card_atlas.draw_atlas(
        layout, dense.points, labels, dense.weights, dense.diameters
    )

    alpha = images["alpha"][..., 0]
    shell_tiles = np.unique(layout.tile_of_card[layout.slab > 0])
    middles, corners = [], []
    for x, y, w, h in layout.tiles[shell_tiles]:
        middles.append(alpha[y + h // 3 : y + 2 * h // 3, x + w // 3 : x + 2 * w // 3].mean())
        corners.append(alpha[y : y + h // 8, x : x + w // 8].mean())
    assert np.median(middles) > 0.5
    assert np.max(corners) < 0.05


def _alpha_source(nodes):
    """The node feeding the alpha of a card material, behind its cut-out node."""
    node = nodes["Principled BSDF"].inputs["Alpha"].links[0].from_node
    assert node.name == "alpha_clip" and node.operation == "GREATER_THAN", "Cards are cut out"
    return node.inputs[0].links[0].from_node


@pytest.mark.parametrize("pack", [True, False])
def test_bake_packs_alpha(long_haired_human, context, tmp_path, pack):
    """The alpha of the cards goes into the color texture, or a texture of its own."""
    from HumGen3D.human.process.settings import TextureBakeSettings

    human = long_haired_human.duplicate(context)
    try:
        hair_obj = human.hair.regular_hair.convert_to_haircards("low", context)
        textures = TextureBakeSettings(
            resolution={key: 128 for key in TextureBakeSettings().resolution},
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
            assert _alpha_source(nodes) == nodes["base_color"]
        else:
            assert color_image.alpha_mode != "CHANNEL_PACKED"
            alpha = np.array(nodes["alpha"].image.pixels)[::4]
            assert _alpha_source(nodes) == nodes["alpha"]
        assert alpha.max() > alpha.min() + 0.1
        assert (alpha < 0.5).mean() > 0.2, "Most of a card is transparent"
    finally:
        human.delete()


def test_bake_writes_flow_map(long_haired_human, context, tmp_path):
    """The cards get a flow map: the strands run from the root to the tip of the
    card, so the green channel (the v direction) is low, and the blue channel
    varies between strands."""
    from HumGen3D.human.process.settings import TextureBakeSettings

    human = long_haired_human.duplicate(context)
    try:
        hair_obj = human.hair.regular_hair.convert_to_haircards("low", context)
        textures = TextureBakeSettings(
            resolution={key: 128 for key in TextureBakeSettings().resolution},
        )
        human.process.bake_textures(textures, str(tmp_path), only_sets=("hair",), context=context)

        cards = hair_obj.data.materials[1]
        nodes = cards.node_tree.nodes
        flow_node = nodes["flow"]
        assert flow_node.image is not None
        assert not flow_node.outputs[0].links, "No material input reads the flow map"
        assert flow_node.image.name.endswith("_Flow")
        assert os.path.isfile(os.path.join(tmp_path, f"{flow_node.image.name}.png"))
        pixels = np.array(flow_node.image.pixels).reshape(-1, 4)
        assert abs(pixels[:, 0].mean() - 0.5) < 0.1, "The strands lean to neither side"
        assert pixels[:, 1].mean() < 0.3, "The strands run from the root (v max) to the tip"
        assert (np.abs(pixels[:, 2] - 0.5) > 0.02).mean() > 0.05, "A noise per strand"
        cap = hair_obj.data.materials[0]
        assert "flow" not in cap.node_tree.nodes, "The cap has no strands to follow"
    finally:
        human.delete()


def test_embedded_export_writes_flow_map_next_to_file(long_haired_human, context, tmp_path):
    """Embedded textures only carry the images a material input reads, so the
    flow map of the hair cards is written next to the file."""
    from HumGen3D.human.process.settings import OutputSettings, TextureBakeSettings

    human = long_haired_human.duplicate(context)
    try:
        human.hair.regular_hair.convert_to_haircards("low", context)
        textures = TextureBakeSettings(resolution={key: 64 for key in TextureBakeSettings().resolution})
        human.process.bake_textures(textures, folder=None, only_sets=("hair",), context=context)
        output = OutputSettings(format="glb", textures="embedded")
        path = human.export.write(os.path.join(tmp_path, "Embedded"), output, context=context)
        assert os.path.isfile(path)
        sidecars = [name for name in os.listdir(tmp_path) if name.endswith("_HairCards_Flow.png")]
        assert len(sidecars) == 1, os.listdir(tmp_path)
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
