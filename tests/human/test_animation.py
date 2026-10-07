# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

import math
import os

import bpy
import pytest
from HumGen3D.backend import get_prefs
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.human.animation import mixamo, retarget
from HumGen3D.human.animation.clip import read_clip
from HumGen3D.human.process import rest_pose
from HumGen3D.tests.test_fixtures import *
from mathutils import Quaternion, Vector
from pytest_lazyfixture import lazy_fixture

NON_RIGIFY_FIXTURES = [lazy_fixture("male_human"), lazy_fixture("female_human")]
WALK = os.path.join("animations", "Walking", "HG_Walk_Loop.json")
IDLE = os.path.join("animations", "Idle", "HG_Idle_Loop.json")
KNEEL = os.path.join("animations", "Interaction", "HG_Fixing_Kneeling.json")
FOOT_BONES = ("foot", "toe", "heel.02")


def _lowest_foot_point(human, context):
    """Lowest point of the feet per frame, returns the min and max over all frames."""
    lowest = []
    for frame in range(context.scene.frame_start, context.scene.frame_end + 1):
        context.scene.frame_set(frame)
        points = []
        for suffix in (".L", ".R"):
            for bone_name in FOOT_BONES:
                pose_bone = human.pose.get_posebone_by_original_name(bone_name + suffix)
                points.extend((pose_bone.head.z, pose_bone.tail.z))
        lowest.append(min(points))
    return min(lowest), max(lowest)


@pytest.mark.parametrize("human", NON_RIGIFY_FIXTURES)
def test_reference_pose_matches_t_pose(human, context):
    """The analytic reference pose has to deform the mesh like the T-pose of
    rest_pose, which changes the rolls of the bones."""
    rig = human.objects.rig
    reference = retarget.reference_pose(rig)
    deformations = {
        bone.name: reference[bone.name] @ bone.matrix_local.inverted()
        for bone in rig.data.bones
    }

    context.view_layer.objects.active = rig
    rig.select_set(True)
    rest_pose._reset_pose(rig)
    muted = rest_pose._mute_constraints(rig)
    rest_pose._set_t_pose(rig, context)
    context.view_layer.update()

    for pose_bone in rig.pose.bones:
        expected = deformations[pose_bone.name]
        actual = pose_bone.matrix @ pose_bone.bone.matrix_local.inverted()
        for row_actual, row_expected in zip(actual, expected):
            assert list(row_actual) == pytest.approx(list(row_expected), abs=1e-4)

    for bone_name, constraint_name in muted:
        rig.pose.bones[bone_name].constraints[constraint_name].mute = False
    human.pose.reset()


@pytest.mark.parametrize("human", NON_RIGIFY_FIXTURES)
def test_animation_set(human, context):
    options = human.animation.get_options(context)
    assert WALK in options

    human.animation.set(WALK, context)

    animation = human.animation
    assert animation.is_active
    assert animation.loop
    # 41 clip frames at 30 fps, resampled to whole scene frames
    scene_frames = round(40 * context.scene.render.fps / 30) + 1
    assert animation.frame_count == scene_frames
    assert animation.as_dict()["set"] == WALK
    assert context.scene.frame_start == 1
    # The last frame is the same as the first
    assert context.scene.frame_end == scene_frames - 1
    for bone_name in ("spine", "thigh.L", "f_index.01.R", "palm.01.L"):
        pose_bone = human.pose.get_posebone_by_original_name(bone_name)
        assert pose_bone.rotation_mode == "QUATERNION"
    # All keys on whole frames
    for fcurve in retarget._channels(animation.action)[0]:
        frames = [point.co.x for point in fcurve.keyframe_points]
        assert all(frame == round(frame) for frame in frames)
        assert len(frames) == scene_frames

    human.animation.remove()
    assert not human.animation.is_active
    assert not human.objects.rig.animation_data.action
    assert human.pose.get_posebone_by_original_name("thigh.L").matrix_basis.is_identity


def test_animation_resample_keys():
    """Resampling keeps the first and last key and lands on whole frames."""
    rotations = [Quaternion((1, 0, 0), math.radians(angle)) for angle in range(0, 50, 10)]
    locations = [Vector((i, 0, 0)) for i in range(5)]
    keys = {"spine": (rotations, locations), "thigh.L": (rotations, None)}

    resampled = retarget.resample_keys(keys, 24 / 30)
    new_rotations, new_locations = resampled["spine"]
    assert len(new_rotations) == round(4 * 24 / 30) + 1 == 4
    assert new_rotations[0].rotation_difference(rotations[0]).angle < 1e-6
    assert new_rotations[-1].rotation_difference(rotations[-1]).angle < 1e-6
    assert list(new_locations[0]) == pytest.approx(list(locations[0]))
    assert list(new_locations[-1]) == pytest.approx(list(locations[-1]))
    # Evenly spaced in between
    assert new_locations[1].x == pytest.approx(4 / 3)
    assert resampled["thigh.L"][1] is None

    assert retarget.resample_keys(keys, 1) is keys


def test_animation_fake_user_kept(male_human, context):
    """An action the user protected with a fake user is not deleted."""
    male_human.animation.set(WALK, context)
    action = male_human.animation.action
    action.use_fake_user = True
    name = action.name

    male_human.animation.set(IDLE, context)
    assert name in bpy.data.actions
    assert male_human.animation.action.name != name

    bpy.data.actions.remove(bpy.data.actions[name])
    male_human.animation.remove()


def test_animation_refresh_in_place(male_human, context):
    """Refreshing keeps the action, its start frame and channels of other bones."""
    human = male_human
    human.animation.set(IDLE, context)
    action = human.animation.action
    name = action.name
    fcurves, _ = retarget._channels(action)

    # A channel the user added, the animation only keys the location of the root
    head = human.pose.get_posebone_by_original_name("head")
    user_path = f'pose.bones["{head.name}"].location'
    user_fcurve = fcurves.new(user_path, index=2)
    user_fcurve.keyframe_points.insert(1, 0.1)
    # Slide the animation to start later
    for fcurve in fcurves:
        if fcurve.data_path == user_path:
            continue
        for point in fcurve.keyframe_points:
            point.co.x += 20
        fcurve.update()
    count_before = len(fcurves)

    human.height.set(190, context)

    assert human.animation.action == action
    assert action.name == name
    fcurves, _ = retarget._channels(action)
    assert len(fcurves) == count_before
    assert any(f.data_path == user_path for f in fcurves)
    spine = human.pose.get_posebone_by_original_name("spine")
    spine_fcurve = next(
        f for f in fcurves if f.data_path == f'pose.bones["{spine.name}"].location'
    )
    assert spine_fcurve.keyframe_points[0].co.x == 21

    human.height.set(170, context)
    human.animation.remove()


def test_animation_strips(male_human, context):
    """Animations can be chained as NLA strips and are refreshed with the rig."""
    human = male_human
    rig = human.objects.rig
    human.animation.set(WALK, context)
    walk = human.animation.action

    idle = human.animation.set(IDLE, context, as_strip=True)
    # The active action is pushed down first
    assert human.animation.action is None
    assert human.animation.is_active
    strips = human.animation.strips
    assert [strip.action for strip in strips] == [walk, idle]
    assert strips[1].frame_start == strips[0].frame_end
    assert all(strip.action_slot for strip in strips)

    human.animation.set_scene_frame_range(context)
    assert context.scene.frame_start == round(strips[0].frame_start)
    assert context.scene.frame_end == round(strips[1].frame_end)

    # Strips are retargeted too, in place
    human.height.set(200, context)
    assert [strip.action for strip in human.animation.strips] == [walk, idle]
    assert walk["hg_frame_count"] == human.animation.strips[0].action_frame_end
    lowest, highest = _lowest_foot_point(human, context)
    assert lowest > -0.04
    assert highest < 0.04

    # Setting an active animation leaves the strips alone
    human.animation.set(KNEEL, context)
    assert len(human.animation.strips) == 2
    human.animation.remove()
    assert len(human.animation.strips) == 2
    walk_name, idle_name = walk.name, idle.name
    assert idle_name in bpy.data.actions

    human.animation.remove(strips=True)
    assert not human.animation.is_active
    assert not rig.animation_data.nla_tracks
    assert walk_name not in bpy.data.actions
    assert idle_name not in bpy.data.actions
    human.height.set(170, context)


def _world_rotation_error(human, clip, reference, frame, bone_name):
    pose_bone = human.pose.get_posebone_by_original_name(bone_name)
    delta = Quaternion(clip["rotations"][bone_name][frame]).to_matrix()
    expected = delta @ reference[pose_bone.name].to_3x3()
    difference = expected.inverted() @ pose_bone.matrix.to_3x3()
    return math.degrees(difference.to_quaternion().angle)


@pytest.mark.parametrize("human", NON_RIGIFY_FIXTURES)
def test_animation_rotations(human, context):
    """Bones have to get the clip rotation on top of their reference rotation.

    Except the middle bones of the spine, which get the bend spread over them.
    """
    rig = human.objects.rig
    clip = read_clip(os.path.join(get_prefs().filepath, IDLE))
    reference = retarget.reference_pose(rig, clip)
    context.scene.render.fps = clip["fps"]
    human.animation.set(IDLE, context, finger_curl=1.0)

    frame = 10
    context.scene.frame_set(context.scene.frame_start + frame)
    smoothed = retarget.SPINE_CHAIN[1:-1]
    for bone_name in clip["rotations"]:
        if bone_name in smoothed:
            continue
        error = _world_rotation_error(human, clip, reference, frame, bone_name)
        assert error < 0.01, bone_name

    # The fingers point exactly in the direction of the source rig
    for bone_name in ("thumb.01.L", "f_index.01.R"):
        pose_bone = human.pose.get_posebone_by_original_name(bone_name)
        direction = reference[pose_bone.name].to_3x3() @ Vector((0, 1, 0))
        expected = Vector(clip["reference_directions"][bone_name])
        assert math.degrees(direction.angle(expected)) < 0.01, bone_name

    human.animation.remove()


def test_animation_spine_smoothing(male_human, context):
    """The bend between hips and chest is spread over the spine bones."""
    human = male_human
    rig = human.objects.rig
    clip = read_clip(os.path.join(get_prefs().filepath, KNEEL))
    reference = retarget.reference_pose(rig, clip)
    context.scene.render.fps = clip["fps"]
    human.animation.set(KNEEL, context)

    frame = clip["frame_count"] // 2
    context.scene.frame_set(context.scene.frame_start + frame)
    for bone_name in (retarget.SPINE_CHAIN[0], retarget.SPINE_CHAIN[-1]):
        assert _world_rotation_error(human, clip, reference, frame, bone_name) < 0.01

    # The source bends 55 degrees at one joint, after smoothing no joint bends
    # more than half of that
    bones = [human.pose.get_posebone_by_original_name(n) for n in retarget.SPINE_CHAIN]
    for parent, child in zip(bones, bones[1:]):
        parent_direction = parent.tail - parent.head
        child_direction = child.tail - child.head
        assert math.degrees(parent_direction.angle(child_direction)) < 30

    human.animation.remove()


def test_animation_finger_curl(male_human, context):
    """With finger curl 0 the fingers keep the relaxed hand of the rest pose."""
    human = male_human
    clip = read_clip(os.path.join(get_prefs().filepath, IDLE))
    context.scene.render.fps = clip["fps"]
    human.animation.set(IDLE, context, finger_curl=0.0)
    assert human.animation.finger_curl == 0

    context.scene.frame_set(context.scene.frame_start)
    for bone_name in ("f_index.01.L", "f_index.03.L", "thumb.02.L"):
        pose_bone = human.pose.get_posebone_by_original_name(bone_name)
        assert math.degrees(pose_bone.matrix_basis.to_quaternion().angle) < 0.01

    human.animation.refresh(context, finger_curl=1.0)
    assert human.animation.finger_curl == 1.0
    human.animation.remove()


@pytest.mark.parametrize("human", NON_RIGIFY_FIXTURES)
def test_animation_feet_on_ground(human, context):
    human.animation.set(WALK, context)
    lowest, highest = _lowest_foot_point(human, context)
    assert lowest > -0.04
    assert highest < 0.04

    # The root motion has to scale with the legs
    human.height.set(200, context)
    assert human.animation.is_active
    lowest, highest = _lowest_foot_point(human, context)
    assert lowest > -0.04
    assert highest < 0.04

    human.height.set(170, context)
    human.animation.remove()


def test_animation_pose_set_removes_animation(male_human, context):
    male_human.animation.set(WALK, context)
    assert male_human.animation.is_active

    male_human.pose.set(male_human.pose.get_options(context)[0], context)

    assert not male_human.animation.is_active
    assert not [a for a in bpy.data.actions if a.name.endswith("Walk_Loop")]


def test_animation_t_pose_rest(male_human, context):
    male_human.animation.set(IDLE, context)
    male_human.process.set_t_pose_as_rest(context)

    assert male_human.animation.is_active
    lowest, highest = _lowest_foot_point(male_human, context)
    assert lowest > -0.04
    assert highest < 0.04


def test_animation_rigify(male_rigify_human, context):
    with pytest.raises(HumGenException):
        male_rigify_human.animation.set(WALK, context)


# A Mixamo fbx to test the import with, downloaded from mixamo.com. Not part of
# the repository, the tests that need it are skipped if it is missing.
MIXAMO_FBX = os.environ.get(
    "HG_MIXAMO_FBX", os.path.expanduser("~/Downloads/Taunt.fbx")
)
needs_mixamo_fbx = pytest.mark.skipif(
    not os.path.isfile(MIXAMO_FBX), reason="No Mixamo fbx to test with"
)


def test_mixamo_bone_map(male_human):
    """Every mapped name has to be a bone of the Human Generator rig."""
    rig = male_human.objects.rig
    bone_names = {retarget.original_name(pb) for pb in rig.pose.bones}
    for mixamo_name, hg_name in mixamo.BONE_NAME_MAP.items():
        assert hg_name in bone_names, mixamo_name
    assert mixamo.mixamo_bone_name("mixamorig:Hips") == "Hips"
    assert mixamo.mixamo_bone_name("mixamorig1:LeftArm") == "LeftArm"
    assert mixamo.mixamo_bone_name("Hips") == "Hips"


@needs_mixamo_fbx
def test_mixamo_fbx_to_clip(context):
    """The import must not leave anything of the fbx behind in the file."""
    objects, actions = set(bpy.data.objects), set(bpy.data.actions)
    frame_range = (context.scene.frame_start, context.scene.frame_end)

    clip = mixamo.fbx_to_clip(MIXAMO_FBX, context)

    assert set(bpy.data.objects) == objects
    assert set(bpy.data.actions) == actions
    assert (context.scene.frame_start, context.scene.frame_end) == frame_range
    assert clip["frame_count"] > 1
    assert set(clip["rotations"]) == set(mixamo.BONE_NAME_MAP.values())
    assert 0.6 < clip["reference_leg_length"] < 1.1
    for quaternions in clip["rotations"].values():
        assert len(quaternions) == clip["frame_count"]
    # Mixamo rigs are in a T-pose, so the first frame is not far from identity
    # for the root
    assert Quaternion(clip["rotations"]["spine"][0]).angle < math.radians(90)


@needs_mixamo_fbx
@pytest.mark.parametrize("human", NON_RIGIFY_FIXTURES)
def test_mixamo_import(human, context, tmp_path):
    """Importing saves a clip to the library and applies it to the human."""
    category = "Test_Mixamo"
    folder = os.path.join(get_prefs().filepath, "animations", category)
    try:
        preset = human.animation.import_mixamo(
            MIXAMO_FBX,
            name="Test Clip",
            category=category,
            context=context,
            render_thumbnail=False,
        )
        assert preset == os.path.join("animations", category, "Test_Clip.json")
        assert os.path.isfile(os.path.join(get_prefs().filepath, preset))
        assert human.animation.is_active
        assert human.animation.as_dict()["set"] == preset
        assert preset in human.animation.get_options(context, category)

        lowest, highest = _lowest_foot_point(human, context)
        assert lowest > -0.06
        assert highest < 0.1
    finally:
        human.animation.remove()
        if os.path.isdir(folder):
            for file_name in os.listdir(folder):
                os.remove(os.path.join(folder, file_name))
            os.rmdir(folder)
