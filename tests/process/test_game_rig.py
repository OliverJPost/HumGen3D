# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

import os

import numpy as np
import pytest

from HumGen3D.common.exceptions import HumGenException
from HumGen3D.human.process import game_rig
from HumGen3D.human.process.export import fbx_kwargs
from HumGen3D.human.process.game_rig import PRESETS
from HumGen3D.human.process.settings import OutputSettings
from HumGen3D.tests.test_fixtures import *

# Bones Unity, Godot and VRM need to recognize a humanoid
HUMANOID_REQUIRED = (
    "Hips",
    "Spine",
    "Head",
    "LeftUpperArm",
    "LeftLowerArm",
    "LeftHand",
    "LeftUpperLeg",
    "LeftLowerLeg",
    "LeftFoot",
    "RightUpperArm",
    "RightLowerArm",
    "RightHand",
    "RightUpperLeg",
    "RightLowerLeg",
    "RightFoot",
)
UNREAL_SAMPLE = ("root", "pelvis", "spine_01", "clavicle_l", "lowerarm_r", "calf_l", "ball_r")
MIXAMO_SAMPLE = (
    "mixamorig:Hips",
    "mixamorig:Spine2",
    "mixamorig:LeftArm",
    "mixamorig:RightHandThumb1",
    "mixamorig:LeftUpLeg",
    "mixamorig:RightToeBase",
)


@pytest.fixture
def human(male_human, context):
    """A copy of the male human, as converting the rig can't be undone."""
    human = male_human.duplicate(context)
    yield human
    human.delete()


def _evaluated_coords(obj, context):
    depsgraph = context.evaluated_depsgraph_get()
    depsgraph.update()
    obj_eval = obj.evaluated_get(depsgraph)
    coords = np.empty(len(obj_eval.data.vertices) * 3, dtype=np.float64)
    obj_eval.data.vertices.foreach_get("co", coords)
    return coords


def _skinned_meshes(human):
    return [obj for obj in human.objects if obj.type == "MESH" and obj.vertex_groups]


def _bone_weights(obj, bone_names):
    """Per vertex the weights of the vertex groups that belong to bones."""
    weights = []
    for vertex in obj.data.vertices:
        weights.append(
            [
                group.weight
                for group in vertex.groups
                if obj.vertex_groups[group.group].name in bone_names and group.weight > 0
            ]
        )
    return weights


def _driver_bone_targets(obj):
    key = obj.data.shape_keys
    if not key or not key.animation_data:
        return set()
    return {
        target.bone_target
        for fcurve in key.animation_data.drivers
        for variable in fcurve.driver.variables
        for target in variable.targets
        if target.bone_target
    }


@pytest.mark.parametrize("preset", list(PRESETS))
def test_game_rig_is_clean(human, context, preset):
    if PRESETS[preset]["rest_pose"] == "t_pose":
        human.process.set_t_pose_as_rest(context)
    human.process.convert_to_game_rig(preset=preset, context=context)
    rig = human.objects.rig
    bone_names = {bone.name for bone in rig.data.bones}

    assert human.process.has_game_rig
    assert human.process.game_rig_preset == preset
    assert not any(pose_bone.constraints for pose_bone in rig.pose.bones)
    assert not any(
        key.startswith("rigify") for pose_bone in rig.pose.bones for key in pose_bone.keys()
    )
    # Collections of the removed face rig are gone
    assert not any(
        not collection.bones for collection in rig.data.collections_all
    )

    roots = [bone for bone in rig.data.bones if not bone.parent]
    assert len(roots) == 1
    root_name = PRESETS[preset]["root_bone"]
    if root_name:
        assert roots[0].name == root_name
        assert roots[0].head_local.length == pytest.approx(0, abs=1e-6)
        assert not roots[0].use_deform
        assert len(roots[0].children) == 1

    # Every other bone deforms a mesh and no driver reads a removed bone
    weighted = set()
    for obj in _skinned_meshes(human):
        for vertex in obj.data.vertices:
            for group in vertex.groups:
                if group.weight > 0:
                    weighted.add(obj.vertex_groups[group.group].name)
    for bone in rig.data.bones:
        if bone.use_deform:
            assert bone.name in weighted, bone.name
    for name in _driver_bone_targets(human.objects.body):
        assert name in bone_names, name


def test_humanoid_names(human, context):
    human.process.set_t_pose_as_rest(context)
    human.process.convert_to_game_rig(preset="humanoid", context=context)
    bone_names = {bone.name for bone in human.objects.rig.data.bones}
    for name in HUMANOID_REQUIRED + ("LeftEye", "Jaw", "LeftThumbMetacarpal", "RightLittleDistal"):
        assert name in bone_names, name
    # Metacarpals are merged into the hand by default
    assert "LeftIndexMetacarpal" not in bone_names


def test_unreal_names(human, context):
    human.process.convert_to_game_rig(preset="unreal", keep_metacarpals=True, context=context)
    bone_names = {bone.name for bone in human.objects.rig.data.bones}
    for name in UNREAL_SAMPLE + ("index_metacarpal_l", "thumb_03_r", "eye_l"):
        assert name in bone_names, name
    # Unreal keeps the A-pose
    upper_arm = human.objects.rig.data.bones["upperarm_l"]
    assert (upper_arm.tail_local - upper_arm.head_local).normalized().z < -0.5


def test_mixamo_names(human, context):
    human.process.set_t_pose_as_rest(context)
    human.process.convert_to_game_rig(preset="mixamo", context=context)
    bones = human.objects.rig.data.bones
    for name in MIXAMO_SAMPLE:
        assert name in bones, name
    # Mixamo has the hips as root bone
    assert not bones["mixamorig:Hips"].parent


def test_game_rig_keeps_shape(human, context):
    """Merging weights and baking constraints does not move the mesh in rest pose.

    The eye and jaw bones are kept, as their constraints turn them a little even
    in rest pose, which merging them into the head would undo.
    """
    meshes = _skinned_meshes(human)
    before = [_evaluated_coords(obj, context) for obj in meshes]

    human.process.convert_to_game_rig(
        preset="generic_a",
        keep_breasts=False,
        keep_metacarpals=False,
        max_influences=0,
        context=context,
    )

    for obj, coords in zip(meshes, before):
        np.testing.assert_allclose(_evaluated_coords(obj, context), coords, atol=1e-5)


def test_game_rig_keeps_posed_shape(human, context):
    """With all bones kept the posed mesh is the same after the conversion."""
    human.pose.set(human.pose.get_options(context)[0], context)
    meshes = _skinned_meshes(human)
    before = [_evaluated_coords(obj, context) for obj in meshes]

    human.process.convert_to_game_rig(
        preset="generic_a", keep_metacarpals=True, max_influences=0, context=context
    )

    for obj, coords in zip(meshes, before):
        np.testing.assert_allclose(_evaluated_coords(obj, context), coords, atol=1e-4)


def test_merged_weights(human, context):
    body = human.objects.body
    bone_names = {bone.name for bone in human.objects.rig.data.bones}
    sums_before = [sum(weights) for weights in _bone_weights(body, bone_names)]

    human.process.convert_to_game_rig(
        preset="generic_a",
        keep_eyes=False,
        keep_jaw=False,
        keep_breasts=False,
        keep_metacarpals=False,
        max_influences=0,
        context=context,
    )

    bone_names = {bone.name for bone in human.objects.rig.data.bones}
    for name in ("eyeball.L", "jaw", "jaw_upper", "breast.R", "palm.01.L"):
        assert name not in bone_names
    # The eyes and teeth now follow the head, the fingers the hand
    assert [group.name for group in human.objects.eyes.vertex_groups] == ["head"]
    assert [group.name for group in human.objects.lower_teeth.vertex_groups] == ["head"]
    sums_after = [sum(weights) for weights in _bone_weights(body, bone_names)]
    np.testing.assert_allclose(sums_after, sums_before, atol=1e-5)


def test_unused_vertex_groups_removed(human, context):
    body = human.objects.body
    group_names = {group.name for group in body.vertex_groups}
    # Groups of bones that no longer exist and groups Blender only needs
    assert {"Head", "pelvis.L", "heel.R", "lip_upper_vg"} <= group_names
    # The eyebrows grow where this group is, so it stays in use
    used_groups = game_rig._referenced_vertex_groups(body)
    assert "Hair_Eyebrows" in used_groups

    human.process.convert_to_game_rig(preset="generic_a", context=context)

    group_names = {group.name for group in body.vertex_groups}
    bone_names = {bone.name for bone in human.objects.rig.data.bones}
    assert not {"Head", "pelvis.L", "heel.R", "lip_upper_vg"} & group_names
    assert used_groups <= group_names
    assert group_names <= bone_names | used_groups


@pytest.mark.parametrize("limit", (4, 2))
def test_influence_limit(human, context, limit):
    human.process.convert_to_game_rig(
        preset="generic_a", max_influences=limit, context=context
    )
    bone_names = {bone.name for bone in human.objects.rig.data.bones}
    for obj in _skinned_meshes(human):
        for weights in _bone_weights(obj, bone_names):
            assert len(weights) <= limit
            if weights:
                assert sum(weights) == pytest.approx(1, abs=1e-4)


def test_removed_bone_drivers_are_baked(human, context):
    human.expression.load_facial_rig(context)
    # The slider bones move along their local Z within a centimeter
    smile = human.pose.get_posebone_by_original_name("mouth_smile_frown_L")
    smile.location.z = 0.005
    body = human.objects.body
    depsgraph = context.evaluated_depsgraph_get()
    depsgraph.update()
    key_eval = body.evaluated_get(depsgraph).data.shape_keys
    driven_value = key_eval.key_blocks["mouthSmile_L"].value
    assert driven_value > 0.01

    human.process.convert_to_game_rig(preset="generic_a", context=context)

    key = body.data.shape_keys
    assert "mouthSmile_L" in key.key_blocks
    assert key.key_blocks["mouthSmile_L"].value == pytest.approx(driven_value, abs=1e-4)
    assert "eyeLookUpLeft" in key.key_blocks
    # The correctives read bones that still exist, so they are still driven
    assert "forearm.L" in _driver_bone_targets(body)
    assert "mouth_smile_frown_L" not in _driver_bone_targets(body)


def test_game_rig_export(human, context, tmp_path):
    human.process.convert_to_game_rig(preset="unreal", context=context)
    path = os.path.join(tmp_path, "unreal.fbx")
    kwargs = fbx_kwargs(OutputSettings(), PRESETS["unreal"]["units"])
    assert kwargs["apply_scale_options"] == "FBX_SCALE_ALL"
    human.export.to_fbx(path, context=context, **kwargs)
    assert os.path.getsize(path) > 0


def test_game_rig_twice_raises(human, context):
    human.process.convert_to_game_rig(context=context)
    with pytest.raises(HumGenException):
        human.process.convert_to_game_rig(context=context)


def test_unknown_preset_raises(human, context):
    with pytest.raises(ValueError):
        human.process.convert_to_game_rig(preset="nonexistent", context=context)


def test_rigify_raises(male_rigify_human, context):
    with pytest.raises(HumGenException):
        male_rigify_human.process.convert_to_game_rig(context=context)
