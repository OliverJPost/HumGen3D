# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import pytest
from HumGen3D.common.context import context_override
from HumGen3D.tests.fixtures import *


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_randomize_body(human):
    hash_before = hash(human.body)
    human.body.randomize()
    assert hash(human.body) != hash_before, "Human body hash has not changed"


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_body_keys(human, context):
    hash_before = hash(human.body)

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
