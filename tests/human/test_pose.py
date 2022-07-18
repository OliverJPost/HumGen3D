import random
from HumGen3D.tests.fixtures import finalize_phase_human as human, context


def test_pose_set(human, context):
    current_rots = [bone.rotation_euler for bone in human.pose_bones]
    options = human.finalize_phase.pose.get_options()
    chosen = random.choice(options)
    while "a_pose" in chosen.lower():
        chosen = random.choice(options)

    human.finalize_phase.pose.set(chosen, context)

    new_rots = [bone.rotation_euler for bone in human.pose_bones]
    assert not all(b_old == b_new for b_old, b_new in zip(current_rots, new_rots))
