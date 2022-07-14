import pytest
from HumGen3D import Human

@pytest.fixture(scope="class")
def creation_phase_human():
    human = Human.from_preset(chosen_preset)
    yield human
    human.delete()
    
    
@pytest.fixture(scope="class")
def finalize_phase_human(creation_phase_human):
    creation_phase_human.creation_phase.finish()
    yield creation_phase_human
    