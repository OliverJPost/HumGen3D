import os
import random

from HumGen3D.human.base.exceptions import HumGenException
from HumGen3D.tests.fixtures import ALL_FINALIZE_FIXTURES, context
from HumGen3D.tests.fixtures import *

@pytest.mark.parametrize("human", ALL_FINALIZE_FIXTURES)
def test_facial_rig(human, context):
    inital_sk_count = len(human.shape_keys)
    human.finalize_phase.expression.load_facial_rig(context)

    for bone_name in human.finalize_phase.expression._get_frig_bones():
        assert not human.pose_bones.get(bone_name).bone.hide

    human.finalize_phase.expression.remove_facial_rig()

    for bone_name in human.finalize_phase.expression._get_frig_bones():
        assert human.pose_bones.get(bone_name).bone.hide

    try:
        human.finalize_phase.expression.remove_facial_rig()
        assert False, "Should throw exception"
    except HumGenException:
        assert True

    assert len(human.shape_keys) == inital_sk_count

@pytest.mark.parametrize("human", ALL_FINALIZE_FIXTURES)
def test_set(human):
    options = human.finalize_phase.expression.get_options()
    assert options

    chosen = random.choice(options)
    human.finalize_phase.expression.set(chosen)
    sk_name, _ = os.path.splitext(os.path.basename(chosen))

    sk = human.shape_keys.get(sk_name)
    assert sk
    assert sk.value
    assert not sk.mute
