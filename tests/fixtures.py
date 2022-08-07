# Not named conftest.py because that is run outside of Blender Python, so it
# can't import from bpy

import random

import bpy
import pytest # type:ignore
from HumGen3D.human.human import Human
from pytest_lazyfixture import lazy_fixture # type:ignore

_standard_fixtures = ["creation_phase_human", "finalize_phase_human", "reverted_human"]
_all_female_fixtures = [name+"_female" for name in _standard_fixtures]
ALL_HUMAN_FIXTURES = [lazy_fixture(name) for name in _standard_fixtures+_all_female_fixtures]
ALL_FEMALE_FIXTURES = [lazy_fixture(name) for name in _all_female_fixtures]

ALL_FINALIZE_FIXTURES = [lazy_fixture(name) for name in ["finalize_phase_human", "finalize_phase_human_female"]]
ALL_CREATION_FIXTURES = []
for name in ["creation_phase_human", "reverted_human"]:
    ALL_CREATION_FIXTURES.append(lazy_fixture(name))
    ALL_CREATION_FIXTURES.append(lazy_fixture(name+"_female"))

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
def reverted_human() -> Human:
    human = _create_human("male")
    human.creation_phase.finish(bpy.context)
    human.finalize_phase.revert(bpy.context)
    yield human
    human.delete()

@pytest.fixture(scope="class")
def reverted_human_female() -> Human:
    human = _create_human("female")
    human.creation_phase.finish(bpy.context)
    human.finalize_phase.revert(bpy.context)
    yield human
    human.delete()

@pytest.fixture
def context():
    return bpy.context
