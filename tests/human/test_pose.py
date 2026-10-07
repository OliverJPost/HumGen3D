# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811
import bpy
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


def test_rigify(male_human, context):
    old_rig_name = male_human.objects.rig.name
    male_human.pose.rigify.generate(context=context)
    assert not bpy.data.objects.get(old_rig_name)
    assert male_human.objects.rig
    assert "rig_id" in male_human.objects.rig.data


def test_rigify_position(male_human, context):
    TEST_LOCATION = (5.0, 2.0, 1.0)
    male_human.location = TEST_LOCATION
    assert tuple(male_human.objects.rig.location) == TEST_LOCATION
    male_human.pose.rigify.generate(context=context)

    assert tuple(male_human.objects.rig.location) == TEST_LOCATION


def test_rigify_on_face_rig(male_human, context):
    male_human.expression.load_facial_rig(context=context)
    male_human.pose.rigify.generate(context=context)
    _assert_driver_targets_exist(male_human)


def test_rigify_driver_targets(male_human, context):
    """Every bone a shape key driver reads exists in the Rigify rig, including the
    knee correctives (shin) and the eye look keys (eye targets)."""
    male_human.pose.rigify.generate(context=context)
    _assert_driver_targets_exist(male_human)
    targets = _driver_bone_targets(male_human.objects.body)
    assert "DEF-shin.L" in targets
    # The eye targets have no Rigify type, so only their ORG copies exist
    assert "ORG-eyeball_lookat.L" in targets


def _driver_bone_targets(obj):
    return {
        target.bone_target
        for fcurve in obj.data.shape_keys.animation_data.drivers
        for variable in fcurve.driver.variables
        if variable.type == "TRANSFORMS"
        for target in variable.targets
    }


def _assert_driver_targets_exist(human):
    bones = human.objects.rig.data.bones
    for name in _driver_bone_targets(human.objects.body):
        assert name in bones, name
