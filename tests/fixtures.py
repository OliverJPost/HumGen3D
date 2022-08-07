# Not named conftest.py because that is run outside of Blender Python, so it
# can't import from bpy

import random

import bpy
import pytest # type:ignore
from HumGen3D.human.human import Human


@pytest.fixture(scope="class")
def creation_phase_human() -> Human:
    human = _create_human()
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


def _create_human():
    chosen_preset = random.choice(Human.get_preset_options("male", bpy.context))
    human = Human.from_preset(chosen_preset, bpy.context)
    return human


@pytest.fixture(scope="class")
def reverted_human(finalize_phase_human) -> Human:
    finalize_phase_human.finalize_phase.revert(bpy.context)
    yield finalize_phase_human


@pytest.fixture
def context():
    return bpy.context
