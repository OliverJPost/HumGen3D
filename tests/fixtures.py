import random

import bpy
import pytest
from bpy.types import Context
from HumGen3D import Human


@pytest.fixture(scope="class")
def creation_phase_human() -> Human:
    chosen_preset = random.choice(Human.get_preset_options("male", bpy.context))
    human = Human.from_preset(chosen_preset, bpy.context)
    yield human
    human.delete()


@pytest.fixture(scope="class")
def finalize_phase_human(creation_phase_human) -> Human:
    creation_phase_human.creation_phase.finish(bpy.context)
    yield creation_phase_human


@pytest.fixture(scope="class")
def reverted_human(finalize_phase_human) -> Human:
    finalize_phase_human.finalize_phase.revert(bpy.context)
    yield finalize_phase_human


@pytest.fixture
def context() -> Context:
    return bpy.context
