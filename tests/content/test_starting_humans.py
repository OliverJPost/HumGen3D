import pytest

from HumGen3D import Human
import bpy

@pytest.mark.parametrize("preset", Human.get_preset_options("male")+Human.get_preset_options("female"))
def test_starting_humans(preset):
    human = Human.from_preset(preset, context=bpy.context)
    human.objects.rig["pytest_human"] = True
    human._verify_integrity()
    human.delete()