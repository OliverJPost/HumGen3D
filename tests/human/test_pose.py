import random
from HumGen3D.tests.fixtures import (
    ALL_HUMAN_FIXTURES,
    female_human,
    male_human,
    context,
)
import pytest


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_pose_set(human, context):
    current_rots = [bone.rotation_euler for bone in human.pose_bones]
    options = human.pose.get_options(context)
    chosen = random.choice(options)
    while "a_pose" in chosen.lower():
        chosen = random.choice(options)

    human.pose.set(chosen, context)

    # FIXME
    # new_rots = [bone.rotation_euler for bone in human.pose_bones]
    # assert not all([b_old == b_new for b_old, b_new in zip(current_rots, new_rots)])
