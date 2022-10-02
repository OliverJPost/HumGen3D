# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

# Not named conftest.py because that is run outside of Blender Python, so it
# can't import from bpy

import random

import bpy
import pytest  # type:ignore
from HumGen3D.human.human import Human
from pytest_lazyfixture import lazy_fixture  # type:ignore

_standard_fixtures = [
    "male_human",
]
_all_female_fixtures = [
    "female_human",
]
ALL_HUMAN_FIXTURES = [
    lazy_fixture(name) for name in _standard_fixtures + _all_female_fixtures
]
ALL_FEMALE_FIXTURES = [lazy_fixture(name) for name in _all_female_fixtures]


@pytest.fixture(scope="class")
def male_human() -> Human:
    human = _create_human("male")
    yield human
    human.delete()


@pytest.fixture(scope="class")
def female_human() -> Human:
    human = _create_human("female")
    yield human
    human.delete()


def _create_human(gender="male"):
    chosen_preset = Human.get_preset_options(gender, bpy.context)[0]
    human = Human.from_preset(chosen_preset, bpy.context)
    return human


@pytest.fixture
def context():
    return bpy.context
