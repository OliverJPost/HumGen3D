# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

import pytest
from HumGen3D.tests.test_fixtures import *


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_pose_set(human, context):
    hash_before = hash(human.pose)
    chosen_pose = human.pose.get_options(context)[3]

    human.pose.set(chosen_pose, context)

    assert (
        hash(human.pose) != hash_before
    ), f"Hash is the same after setting {chosen_pose=}"


def test_pose_hash(male_human, context):
    hash_before = hash(male_human.pose)
    options = male_human.pose.get_options(context)
    a_pose = next(opt for opt in options if "a_pose" in opt)
    male_human.pose.set(a_pose, context)
    # assert hash_before == hash(male_human.pose) # FIXME this fails

    male_human.objects.rig.pose.bones.get("spine").rotation_euler = (125, 123, 76)

    assert hash_before != hash(male_human.pose)
