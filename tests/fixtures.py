# Not named conftest.py because that is run outside of Blender Python, so it
# can't import from bpy

import random

import bpy
import pytest # type:ignore
from HumGen3D.human.human import Human
from pytest_lazyfixture import lazy_fixture # type:ignore

@pytest.fixture(scope="class")
def creation_phase_human() -> Human:
    human = _create_human()
    yield human
    human.delete()

@pytest.fixture(scope="class")
def creation_phase_human_female() -> Human:
    human = _create_human("female")
    yield human
    human.delete()

@pytest.fixture(scope="class")
def finalize_phase_human() -> Human:
    # Repeated here because having creation_phase_human as argument does not
    # work outside of conftest.py somehow
    human = _create_human()
    human.creation_phase.finish(bpy.context)
    yield human
    human.delete()

@pytest.fixture(scope="class")
def finalize_phase_human_female() -> Human:
    # Repeated here because having creation_phase_human as argument does not
    # work outside of conftest.py somehow
    human = _create_human("female")
    human.creation_phase.finish(bpy.context)
    yield human
    human.delete()

def _create_human(gender="male"):
    chosen_preset = random.choice(Human.get_preset_options(gender, bpy.context))
    human = Human.from_preset(chosen_preset, bpy.context)
    return human


@pytest.fixture(scope="class")
def reverted_human(finalize_phase_human) -> Human:
    finalize_phase_human.finalize_phase.revert(bpy.context)
    yield finalize_phase_human

@pytest.fixture(scope="class")
def reverted_human_female(finalize_phase_human_female) -> Human:
    finalize_phase_human_female.finalize_phase.revert(bpy.context)
    yield finalize_phase_human_female

@pytest.fixture
def context():
    return bpy.context

_standard_fixtures = ["creation_phase_human", "finalize_phase_human", "reverted_human"]
_female_fixtures = [name+"_female" for name in _standard_fixtures]
all_human_fixtures = [lazy_fixture(name) for name in _standard_fixtures+_female_fixtures]
female_fixtures = [lazy_fixture(name) for name in _female_fixtures]

def parametrize_all_human_types(func, gender="all"):
    fixture_names = []
    default_fixture_names = [
        "creation_phase_human",
        "finalize_phase_human",
        "reverted_human"
    ]
    if gender == "male" or gender == "all":
        fixture_names.extend(default_fixture_names)
    if gender == "female" or gender == "all":
        fixture_names.extend([name+"_female" for name in default_fixture_names])

    return pytest.mark.parametrize(func, "human", [lazy_fixture(name) for name in fixture_names])
