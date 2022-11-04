# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import pytest
from HumGen3D.tests.fixtures import (  # noqa
    ALL_HUMAN_FIXTURES,
    context,
    female_human,
    male_human,
)


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_randomize_body(human):
    hash_before = hash(human.body)
    human.body.randomize()
    assert hash(human.body) != hash_before, "Human body hash has not changed"


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_body_keys(human):
    hash_before = hash(human.body)
    for key in human.body.keys:
        assert key.value == key.as_bpy().value
        new_value = 0.5
        key.value = new_value
        assert pytest.approx(key.value) == new_value
        assert pytest.approx(key.as_bpy().value) == new_value

        new_value = 1.2
        key.as_bpy().value = new_value
        assert pytest.approx(key.value) == new_value
        assert pytest.approx(key.as_bpy().value) == new_value
    assert hash(human.body) != hash_before, "Human body hash has not changed"
