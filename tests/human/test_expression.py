# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

import os
import random

import pytest
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.human.expression.expression import FACE_RIG_BONE_NAMES
from HumGen3D.tests.test_fixtures import *


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_facial_rig(human, context):
    human.expression.load_facial_rig(context)

    for bone_name in FACE_RIG_BONE_NAMES:
        bone = human.pose.get_posebone_by_original_name(bone_name).bone
        assert not bone.hide

    human.expression.remove_facial_rig()

    for bone_name in FACE_RIG_BONE_NAMES:
        bone = human.pose.get_posebone_by_original_name(bone_name).bone
        assert bone.hide

    try:
        human.expression.remove_facial_rig()
        assert False, "Should throw exception"
    except HumGenException:
        assert True

    # FIXME not all shapekeys are deleted
    # assert len(human.keys) == inital_sk_count


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_set(human, context):
    options = human.expression.get_options(context)
    assert options

    chosen = random.choice(options)
    human.expression.set(chosen)
    sk_name, _ = os.path.splitext(os.path.basename(chosen))

    sk = human.keys.get(sk_name)
    assert sk
    assert sk.value
    assert not sk.as_bpy().mute
