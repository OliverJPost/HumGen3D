# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import pytest
from HumGen3D.tests.fixtures import (
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

# @pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
# def test_set_bone_scale(human, context):
#     bone_types = [
#         "head",
#         "neck",
#         "chest",
#         "shoulder",
#         "breast",
#         "forearm",
#         "upper_arm",
#         "hips",
#         "thigh",
#         "shin",
#         "foot",
#         "hand",
#     ]

#     for bone_type in bone_types:
#         set_scale = human.body.set_bone_scale
#         for value in (28, -3, 5.2, 0, 1):
#             set_scale(value, bone_type, context)
