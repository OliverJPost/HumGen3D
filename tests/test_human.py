import pytest
from bpy.props import FloatVectorProperty
from HumGen3D import Human
from HumGen3D.human.base.exceptions import HumGenException

from fixtures import context, creation_phase_human, finalize_phase_human


@pytest.mark.parametrize("gender", ["male", "female"])
def test_get_preset_options(gender, context):
    assert Human.get_preset_options(gender, context), "No preset options returned"

@pytest.mark.usefixtures("creation_phase_human", "finalize_phase_human")
#@pytest.mark.parametrize("creation_phase_human", [creation_phase_human, finalize_phase_human])
class TestHumanCommonMethods:
    @staticmethod
    def test_repr(creation_phase_human):
        assert creation_phase_human.__repr__
    @staticmethod
    def test_from_existing(creation_phase_human):
        for obj in creation_phase_human.objects:
            found_human = Human.from_existing(obj)
            assert found_human
    @staticmethod
    def test_from_existing_fail(creation_phase_human):
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
    @staticmethod
    def test_objects(creation_phase_human):
        assert creation_phase_human.objects, "No objects returned"
    @staticmethod
    def test_children(creation_phase_human):
        assert creation_phase_human.children, "No children returned"
    @staticmethod
    def test_body_obj(creation_phase_human):
        assert creation_phase_human.body_obj
    @staticmethod
    def test_eye_obj(creation_phase_human):
        assert creation_phase_human.eye_obj
    @staticmethod
    def test_gender(creation_phase_human):
        assert creation_phase_human.gender

        try:
            creation_phase_human.gender = "female"
            assert False, "Should throw exception"
        except AttributeError:
            assert True
    @staticmethod
    def test_name(creation_phase_human):
        assert creation_phase_human.name
        creation_phase_human.name = "Steve"
        creation_phase_human.name = "Julia"

        assert creation_phase_human.name == "Julia"
    @staticmethod
    def test_pose_bones(creation_phase_human):
        assert len(creation_phase_human.pose_bones)
    @staticmethod
    def test_edit_bones(creation_phase_human):
        assert len(creation_phase_human.edit_bones)
    @staticmethod
    def test_location(creation_phase_human):
        old_loc = creation_phase_human.location
        assert old_loc
        #assert isinstance(old_loc, FloatVectorProperty)

        new_loc = (1.2, 5.8, 3.1)
        creation_phase_human.location = new_loc
        assert creation_phase_human.location == new_loc
        assert creation_phase_human.rig_obj.location == new_loc

        creation_phase_human.location = old_loc
        assert creation_phase_human.rig_obj.location == old_loc
    @staticmethod
    def test_rotation_euler(creation_phase_human):
        old_rot = creation_phase_human.rotation_euler
        assert old_rot
        #assert isinstance(old_rot, FloatVectorProperty)

        new_rot = (35.1, 2.1, 84.9)
        creation_phase_human.rotation_euler = new_rot
        assert creation_phase_human.rotation_euler == new_rot
        assert creation_phase_human.rig_obj.rotation_euler == new_rot

        creation_phase_human.rotation_euler = old_rot
        assert creation_phase_human.rig_obj.rotation_eulet == old_rot
    @staticmethod
    def test_props(creation_phase_human):
        assert creation_phase_human.props
        assert creation_phase_human.props.ishuman
        assert creation_phase_human.props.body_obj
    @staticmethod
    def test_hide_set(creation_phase_human):
        def is_hidden():
            creation_phase_human.hide_set(True)
            for obj in creation_phase_human.objects:
                assert obj.hide_viewport
                assert not obj.visible_get()
        def is_visible():
            creation_phase_human.hide_set(False)
            for obj in creation_phase_human.objects:
                assert obj.hide_viewport
                assert not obj.visible_get()

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

