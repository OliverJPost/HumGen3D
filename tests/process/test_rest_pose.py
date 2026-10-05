# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

import math

import bpy
import numpy as np
import pytest
from mathutils import Matrix

from HumGen3D.common.exceptions import HumGenException
from HumGen3D.human.process import rest_pose
from HumGen3D.tests.test_fixtures import *
from pytest_lazyfixture import lazy_fixture

NON_RIGIFY_FIXTURES = [lazy_fixture("male_human"), lazy_fixture("female_human")]


def _evaluated_coords(obj, context):
    depsgraph = context.evaluated_depsgraph_get()
    depsgraph.update()
    obj_eval = obj.evaluated_get(depsgraph)
    coords = np.empty(len(obj_eval.data.vertices) * 3, dtype=np.float64)
    obj_eval.data.vertices.foreach_get("co", coords)
    return coords


def _rest_direction(human, original_name):
    bone = human.pose.get_posebone_by_original_name(original_name).bone
    return (bone.tail_local - bone.head_local).normalized()


@pytest.mark.parametrize("human", NON_RIGIFY_FIXTURES)
def test_t_pose_rest_bone_directions(human, context):
    human.process.set_t_pose_as_rest(context)

    assert human.process.has_t_pose_rest
    for suffix, side in ((".L", 1), (".R", -1)):
        for bone_name in ("upper_arm", "hand"):
            direction = _rest_direction(human, bone_name + suffix)
            assert direction.x * side == pytest.approx(1, abs=1e-5)

        # Elbow has to be bent slightly forward
        forearm_direction = _rest_direction(human, "forearm" + suffix)
        assert forearm_direction.y == pytest.approx(
            -math.sin(rest_pose.ELBOW_BEND), abs=1e-5
        )
        assert forearm_direction.z == pytest.approx(0, abs=1e-5)

        assert _rest_direction(human, "thigh" + suffix).z < -0.999


@pytest.mark.parametrize("human", NON_RIGIFY_FIXTURES)
def test_t_pose_rest_keeps_shape(human, context):
    rig = human.objects.rig
    mesh_objs = [obj for obj in human.objects if obj.type == "MESH"]

    # Put the human in the same T-pose, without baking it
    context.view_layer.objects.active = rig
    rest_pose._remove_side_raise_shapekeys(human)
    rest_pose._reset_pose(rig)
    rest_pose._set_t_pose(rig, context)
    posed_coords = [_evaluated_coords(obj, context) for obj in mesh_objs]

    human.process.set_t_pose_as_rest(context)

    for pose_bone in rig.pose.bones:
        assert pose_bone.matrix_basis.is_identity
    for obj, coords in zip(mesh_objs, posed_coords):
        np.testing.assert_allclose(_evaluated_coords(obj, context), coords, atol=1e-5)


def _corrective_values(human, context):
    depsgraph = context.evaluated_depsgraph_get()
    depsgraph.update()
    key = human.objects.body.evaluated_get(depsgraph).data.shape_keys
    return {sk.name: sk.value for sk in key.key_blocks if sk.name.startswith("cor_")}


@pytest.mark.parametrize("human", NON_RIGIFY_FIXTURES)
def test_t_pose_rest_correctives(human, context):
    rig = human.objects.rig
    bend = {
        "forearm.L": Matrix.Rotation(math.radians(60), 4, "X"),
        "forearm.R": Matrix.Rotation(math.radians(60), 4, "X"),
        "shin.L": Matrix.Rotation(math.radians(80), 4, "X"),
        "shin.R": Matrix.Rotation(math.radians(80), 4, "X"),
    }

    # Corrective values for the A-pose and a T-pose with bent elbows and knees, with
    # the A-pose as rest pose
    context.view_layer.objects.active = rig
    rest_pose._remove_side_raise_shapekeys(human)
    rest_pose._reset_pose(rig)
    rest_pose._set_t_pose(rig, context)
    t_pose = {bone.name: bone.matrix_basis.copy() for bone in rig.pose.bones}
    for bone_name, rotation in bend.items():
        rig.pose.bones[bone_name].matrix_basis = t_pose[bone_name] @ rotation
    values_bent = _corrective_values(human, context)
    assert values_bent["cor_ElbowBend_Lt"] > 0.2
    rest_pose._reset_pose(rig)
    values_a_pose = _corrective_values(human, context)

    human.process.set_t_pose_as_rest(context)

    key = human.objects.body.data.shape_keys
    assert not [sk for sk in key.key_blocks if sk.name.startswith("cor_ShoulderSide")]
    for driver in key.animation_data.drivers:
        assert driver.is_valid
        assert driver.driver.is_simple_expression

    for bone_name, rotation in bend.items():
        rig.pose.bones[bone_name].matrix_basis = rotation
    for sk_name, value in _corrective_values(human, context).items():
        assert value == pytest.approx(values_bent[sk_name], abs=0.01)

    for pose_bone in rig.pose.bones:
        pose_bone.matrix_basis = t_pose[pose_bone.name].inverted()
    for sk_name, value in _corrective_values(human, context).items():
        assert value == pytest.approx(values_a_pose[sk_name], abs=0.05)


def test_t_pose_rest_rigify(male_rigify_human, context):
    with pytest.raises(HumGenException):
        male_rigify_human.process.set_t_pose_as_rest(context)
