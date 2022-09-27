# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

# Not named conftest.py because that is run outside of Blender Python, so it
# can't import from bpy

import random

import bpy
import pytest  # type:ignore
from HumGen3D.human.human import Human
from pytest_lazyfixture import lazy_fixture  # type:ignore

_standard_fixtures = ["male_human", "legacy_male_human"]
_all_female_fixtures = ["female_human", "legacy_female_human"]
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
def legacy_male_human() -> Human:
    filepath = r"/Users/ole/Documents/Human Generator/legacy_test_male.blend"
    data_to = _import_old_testing_human(filepath)

    human = Human.from_existing(next(o for o in data_to.objects if o.HG.ishuman))
    yield human
    human.delete()


@pytest.fixture(scope="class")
def legacy_female_human() -> Human:
    filepath = r"/Users/ole/Documents/Human Generator/legacy_test_female.blend"
    data_to = _import_old_testing_human(filepath)

    human = Human.from_existing(next(o for o in data_to.objects if o.HG.ishuman))
    yield human
    human.delete()


def _import_old_testing_human(filepath):
    with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
        data_to.objects = data_from.objects

    for obj in data_to.objects:
        bpy.context.scene.collection.objects.link(obj)
    return data_to


@pytest.fixture(scope="class")
def female_human() -> Human:
    human = _create_human("female")
    yield human
    human.delete()


def _create_human(gender="male"):
    chosen_preset = random.choice(Human.get_preset_options(gender, bpy.context))
    human = Human.from_preset(chosen_preset, bpy.context)
    return human


@pytest.fixture
def context():
    return bpy.context
