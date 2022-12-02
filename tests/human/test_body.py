# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from typing import TYPE_CHECKING

import pytest
from HumGen3D.common.context import context_override
from HumGen3D.tests.fixtures import *

if TYPE_CHECKING:
    from human.human import Human


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_randomize_body(human, context):
    hash_before = hash(human.body)
    human.body.randomize()
    assert hash(human.body) != hash_before, "Human body hash has not changed"
    assert len([k for k in human.body.keys if k.value > 0.001]) > 10

    converted_key = human.body.keys[0].to_shapekey()
    randomized_values = []
    for i in range(4):
        if i == 0:
            human.body.randomize()
        else:
            human.body.randomize(context)
        randomized_values.append(converted_key.value)
    assert sum(randomized_values) != 0, "Randomized values are always 0"


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_reset_body(human: "Human", context):
    human.body.randomize()
    human.body.reset_values()
    assert all(x.value == 0 for x in human.body.keys)

    converted_key = human.body.keys[0].to_shapekey()
    converted_key.value = 0.567
    human.body.reset_values(context)
    assert converted_key.value == 0


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_body_keys(human, context):
    hash_before = hash(human.body)

    assert human.body.keys

    # Override context for as_bpy() to work
    with context_override(context, human.objects.rig, [human.objects.rig]):
        for i, key in enumerate(human.body.keys):
            assert key.value == key.as_bpy().value
            new_value = 0.5
            key.value = new_value
            assert pytest.approx(key.value) == new_value
            assert (
                pytest.approx(key.as_bpy().value) == new_value
            ), f"Failed for key: {key.name}, {i = }"

            new_value = 1.2
            key.as_bpy().value = new_value
            assert pytest.approx(key.value) == new_value
            assert pytest.approx(key.as_bpy().value) == new_value

    assert hash(human.body) != hash_before, "Human body hash has not changed"
