# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8: noqa F811

import bpy
import pytest  # type:ignore
from HumGen3D import Human
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.tests.fixtures import (  # noqa
    ALL_HUMAN_FIXTURES,
    context,
    female_human,
    male_human,
)


def assert_vector_tuple_equality(vec, tup):
    for value_vec, value_tup in zip(vec, tup):
        assert round(value_vec, 1) == round(value_tup, 1)


@pytest.mark.parametrize("gender", ["male", "female"])
def test_get_preset_options(gender, context):
    assert Human.get_preset_options(gender, context), "No preset options returned"


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
class TestHumanCommonMethods:
    @staticmethod
    def test_repr(human):
        assert human.__repr__

    @staticmethod
    def test_from_existing(human):
        for obj in human.objects:
            found_human = Human.from_existing(obj)
            assert found_human

    @staticmethod
    def test_objects(human):
        assert len(human.objects), "No objects returned"

    @staticmethod
    def test_children(human):
        assert human.children, "No children returned"

    @staticmethod
    def test_body_obj(human):
        assert human.objects.body

    @staticmethod
    def test_eye_obj(human):
        assert human.objects.eyes

    @staticmethod
    def test_gender(human):
        assert human.gender

        try:
            human.gender = "female"
            assert False, "Should throw exception"
        except AttributeError:
            assert True

    @staticmethod
    def test_name(human):
        assert human.name
        human.name = "Steve"
        human.name = "Julia"

        assert human.name == "Julia"

    @staticmethod
    def test_pose_bones(human):
        assert len(human.pose_bones)

    # @staticmethod
    # def test_edit_bones(human):
    #     assert len(human.edit_bones)  # FIXME

    @staticmethod
    def test_location(human):
        old_loc = human.location
        assert old_loc
        # assert isinstance(old_loc, FloatVectorProperty)

        new_loc = (1.2, 5.8, 3.1)
        human.location = new_loc
        assert_vector_tuple_equality(human.location, new_loc)
        assert_vector_tuple_equality(human.objects.rig.location, new_loc)

        human.location = old_loc
        assert_vector_tuple_equality(human.objects.rig.location, old_loc)

    @staticmethod
    def test_rotation_euler(human):
        old_rot = human.rotation_euler
        assert old_rot
        # assert isinstance(old_rot, FloatVectorProperty)

        new_rot = (35.1, 2.1, 84.9)
        human.rotation_euler = new_rot
        assert_vector_tuple_equality(human.rotation_euler, new_rot)
        assert_vector_tuple_equality(human.objects.rig.rotation_euler, new_rot)

        human.rotation_euler = old_rot
        assert_vector_tuple_equality(human.objects.rig.rotation_euler, old_rot)

    @staticmethod
    def test_props(human):
        assert human.props
        assert human.props.ishuman
        assert human.props.body_obj

    @staticmethod
    def test_hide_set(human):
        def is_hidden():
            human.hide_set(True)
            for obj in human.objects:
                assert obj.hide_viewport
                assert not obj.visible_get()

        def is_visible():
            human.hide_set(False)
            for obj in human.objects:
                assert not obj.hide_viewport
                assert obj.visible_get()

        is_hidden()
        is_hidden()
        is_visible()
        is_visible()


# TODO implement batch_human
# def test_is_batch(batch_human):
#     rig_obj = batch_human.objects.rig
#     assert Human._is_applied_batch_result(rig_obj)


def test_from_existing_fail():
    def assert_failure(obj):
        try:
            Human.from_existing(obj)
            assert False, "Should throw exception"
        except HumGenException:
            assert True

    mesh = bpy.data.meshes.new("Basic_Cube")
    cube = bpy.data.objects.new("Basic_Cube", mesh)
    bpy.context.scene.collection.objects.link(cube)
    assert_failure(cube)

    cam = bpy.data.cameras.new("Camera")
    non_mesh = bpy.data.objects.new("Camera", cam)
    bpy.context.scene.collection.objects.link(non_mesh)
    assert_failure(non_mesh)
