# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import random

import pytest  # type:ignore
from HumGen3D.tests.fixtures import (  # noqa
    ALL_HUMAN_FIXTURES,
    context,
    female_human,
    male_human,
)


def test_male_skin(male_human):
    skin_sett = male_human.skin.gender_specific
    skin_sett.mustache_shadows = 0.1
    assert (
        pytest.approx(male_human.skin.nodes["Gender_Group"].inputs[2].default_value)
        == 0.1
    )
    skin_sett.mustache_shadows = 28
    skin_sett.beard_shadow = 0.7
    assert (
        pytest.approx(male_human.skin.nodes["Gender_Group"].inputs[3].default_value)
        == 0.7
    )
    skin_sett.beard_shadow = 12


def test_female_skin(female_human):
    attr_names = [
        "foundation_amount",
        "foundation_color",
        "blush_opacity",
        "eyebrows_opacity",
        "eyebrows_color",
        "lipstick_color",
        "lipstick_opacity",
        "eyeliner_opacity",
        "eyeliner_color",
    ]
    node_data = [
        (name, name.replace("_", " ").title(), "Gender_Group") for name in attr_names
    ]
    _assert_node_inputs(female_human, node_data, True)


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_common_inputs(human):
    node_data = [
        ("tone", 1, "Skin_tone"),
        ("redness", 2, "Skin_tone"),
        ("saturation", 3, "Skin_tone"),
        ("normal_strength", 0, "Normal Map"),
        ("roughness_multiplier", 1, "R_Multiply"),
        ("light_areas", "Value", "Lighten_hsv"),
        ("dark_areas", "Value", "Darken_hsv"),
        ("skin_sagging", 1, "HG_Age"),
        ("freckles", "Pos2", "Freckles_control"),
        ("splotches", "Pos2", "Splotches_control"),
        ("beautyspots_amount", 2, "BS_Control"),
        ("beautyspots_opacity", 1, "BS_Opacity"),
        ("beautyspots_seed", 1, "BS_Control"),
    ]

    _assert_node_inputs(human, node_data, False)


def _assert_node_inputs(human, node_data, gender_specific):  # noqa CCR001
    for attr_name, input_name, node_name in node_data:
        dtype = "tuple" if "color" in attr_name else "float"

        if dtype == "float":
            value = random.uniform(0.1, 0.9)
        else:
            r = random.uniform(0.1, 0.9)
            g = random.uniform(0.1, 0.9)
            b = random.uniform(0.1, 0.9)
            value = (r, g, b, 1.0)

        if gender_specific:
            interface = human.skin.gender_specific
        else:
            interface = human.skin
        setattr(interface, attr_name, value)
        found_value = human.skin.nodes[node_name].inputs[input_name].default_value
        assert (
            pytest.approx(found_value) == value
        ), f"{attr_name} failed for {input_name}"


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_material(human):
    assert human.skin.material


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_randomize(human):
    human.skin.randomize()


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_subsurface_scattering(human, context):
    def assert_sss(value, human):
        principled_bsdf = next(
            node for node in human.skin.nodes if node.type == "BSDF_PRINCIPLED"
        )
        sss_value = principled_bsdf.inputs["Subsurface"].default_value
        assert pytest.approx(sss_value) == value

    assert_sss(0, human)

    human.skin.set_subsurface_scattering(True, context)
    assert_sss(0.015, human)

    human.skin.set_subsurface_scattering(False, context)
    assert_sss(0, human)


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_underwear(human, context):
    def assert_underwear(on: bool, human):
        underwear_node = human.skin.nodes.get("Underwear_Opacity")
        assert underwear_node.inputs[1].default_value == int(on)

    assert_underwear(True, human)
    human.skin.set_underwear(False)
    assert_underwear(False, human)
    human.skin.set_underwear(True)
    assert_underwear(True, human)


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_set_texture(human, context):
    options = human.skin.texture.get_options(context)
    chosen = random.choice(options)
    human.skin.texture.set(chosen, context)

    # TODO more extensive testing


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_nodes(human):
    node_len = len(human.skin.nodes)
    assert node_len
    human.skin.nodes.remove(human.skin.nodes[1])
    assert len(human.skin.nodes) == node_len - 1
    assert [node.name for node in human.skin.nodes]


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_links(human):
    link_len = len(human.skin.links)
    assert link_len
    human.skin.links.remove(human.skin.links[1])
    assert len(human.skin.links) == link_len - 1
    assert [link for link in human.skin.links]
