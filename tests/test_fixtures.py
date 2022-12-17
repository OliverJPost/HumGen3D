# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

# Not named conftest.py because that is run outside of Blender Python, so it
# can't import from bpy


import bpy
import pytest  # type:ignore
from HumGen3D.human.human import Human
from pytest_lazyfixture import lazy_fixture  # type:ignore

__all__ = [
    "ALL_FEMALE_FIXTURES",
    "ALL_HUMAN_FIXTURES",
    "TESTFILES_PATH",
    "CLIPPING_THRESHOLD",
    "male_human",
    "context",
    "female_human",
    "male_rigify_human",
]

CLIPPING_THRESHOLD = 0.05
TESTFILES_PATH = "/Users/ole/Documents/HG_EXTRAS/Testfiles"
_standard_fixtures = ["male_human", "male_rigify_human"]
_all_female_fixtures = [
    "female_human",
]
ALL_HUMAN_FIXTURES = [
    lazy_fixture(name) for name in _standard_fixtures + _all_female_fixtures
]
ALL_FEMALE_FIXTURES = [lazy_fixture(name) for name in _all_female_fixtures]


# enable addon in Bpy python module
if not bpy.context.preferences.addons.get("HumGen3D"):
    bpy.ops.preferences.addon_enable(module="HumGen3D")
    bpy.ops.preferences.addon_enable(module="rigify")

@pytest.fixture(scope="class")
def male_human() -> "Human":
    human = _create_human("male")
    yield human
    human.delete()


@pytest.fixture(scope="class")
def female_human() -> "Human":
    human = _create_human("female")
    yield human
    human.delete()


@pytest.fixture(scope="class")
def male_rigify_human() -> "Human":
    human = _create_human("male")
    human.pose.rigify.generate(bpy.context)
    yield human
    human.delete()


def _create_human(gender="male"):
    chosen_preset = next(
        p
        for p in Human.get_preset_options(gender, context=bpy.context)
        if "base" in p.lower()
    )
    human = Human.from_preset(chosen_preset, bpy.context)
    human._rig_obj["pytest_human"] = True
    return human


@pytest.fixture()
def context():
    return bpy.context


FIXTURE_FUNCTIONS = [female_human, male_human, male_rigify_human, context]
