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
def test_set_bone_scale(human, context):
    bone_types = [
        "head",
        "neck",
        "chest",
        "shoulder",
        "breast",
        "forearm",
        "upper_arm",
        "hips",
        "thigh",
        "shin",
        "foot",
        "hand",
    ]

    for bone_type in bone_types:
        set_scale = human.body.set_bone_scale
        set_scale(28, bone_type, context)
        set_scale(-3, bone_type, context)
        set_scale(5.2, bone_type, context)
        set_scale(0, bone_type, context)
        set_scale(1, bone_type, context)
