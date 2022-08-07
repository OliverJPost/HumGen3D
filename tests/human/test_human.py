import pytest # type:ignore
from bpy.props import FloatVectorProperty # type:ignore
from HumGen3D import Human
from HumGen3D.human.base.exceptions import HumGenException
from HumGen3D.tests.fixtures import (
    context,
    creation_phase_human,
    finalize_phase_human,
    reverted_human,
)
from pytest_lazyfixture import lazy_fixture # type:ignore


def assert_vector_tuple_equality(vec, tup):
    for value_vec, value_tup in zip(vec, tup):
        assert round(value_vec, 1) == round(value_tup, 1)


@pytest.mark.parametrize("gender", ["male", "female"])
def test_get_preset_options(gender, context):
    assert Human.get_preset_options(gender, context), "No preset options returned"


fixture_names = ["creation_phase_human", "finalize_phase_human", "reverted_human"]


@pytest.mark.usefixtures(*fixture_names)
@pytest.mark.parametrize("human", [lazy_fixture(name) for name in fixture_names])
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
        assert human.objects, "No objects returned"

    @staticmethod
    def test_children(human):
        assert human.children, "No children returned"

    @staticmethod
    def test_body_obj(human):
        assert human.body_obj

    @staticmethod
    def test_eye_obj(human):
        assert human.eye_obj

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

    @staticmethod
    def test_edit_bones(human):
        assert len(human.edit_bones)  # FIXME

    @staticmethod
    def test_location(human):
        old_loc = human.location
        assert old_loc
        # assert isinstance(old_loc, FloatVectorProperty)

        new_loc = (1.2, 5.8, 3.1)
        human.location = new_loc
        assert_vector_tuple_equality(human.location, new_loc)
        assert_vector_tuple_equality(human.rig_obj.location, new_loc)

        human.location = old_loc
        assert_vector_tuple_equality(human.rig_obj.location, old_loc)

    @staticmethod
    def test_rotation_euler(human):
        old_rot = human.rotation_euler
        assert old_rot
        # assert isinstance(old_rot, FloatVectorProperty)

        new_rot = (35.1, 2.1, 84.9)
        human.rotation_euler = new_rot
        assert_vector_tuple_equality(human.rotation_euler, new_rot)
        assert_vector_tuple_equality(human.rig_obj.rotation_euler, new_rot)

        human.rotation_euler = old_rot
        assert_vector_tuple_equality(human.rig_obj.rotation_euler, old_rot)

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


def test_is_batch(batch_human):
    rig_obj = batch_human.rig_obj
    assert Human._is_applied_batch_result(rig_obj)


def test_creation_phase(creation_phase_human):
    assert creation_phase_human.phase == "creation"

    assert creation_phase_human.creation_phase
    try:
        creation_phase_human.finalize_phase
        assert False, "Should have thrown exception"
    except HumGenException:
        assert True


def test_finalize_phase(finalize_phase_human):
    assert finalize_phase_human.phase == "finalize"

    assert finalize_phase_human.finalize_phase
    try:
        finalize_phase_human.creation_phase
        assert False, "Should have thrown exception"
    except HumGenException:
        assert True


def test_from_existing_fail():
    def assert_failure(obj):
        try:
            Human.from_existing(obj)
            assert False, "Should throw exception"
        except TypeError:
            assert True

    cube = ...
    assert_failure(cube)

    non_mesh = ...
    assert_failure(non_mesh)
