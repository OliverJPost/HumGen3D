import random
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from human.human import Human


def test_pose_set(human: Human, context):
    current_rots = [bone.rotation_euler for bone in human.pose_bones]
    options = human.finalize_phase.pose.get_options()
    chosen = random.choice(options)
    while "a_pose" in chosen.lower():
        chosen = random.choice(options)

    human.finalize_phase.pose.set(chosen, context)

    new_rots = [bone.rotation_euler for bone in human.pose_bones]
    assert not all(b_old == b_new for b_old, b_new in zip(current_rots, new_rots))
