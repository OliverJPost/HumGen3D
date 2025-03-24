import pytest
from HumGen3D.tests.test_fixtures import *

@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_hair(human, context):
    hash_before = hash(human.hair)
    chosen_hair = human.hair.regular_hair.get_options(context)[3]

    human.hair.regular_hair.set(chosen_hair, context)

    assert (
        hash(human.hair) != hash_before
    ), f"Hash is the same after setting {chosen_hair=}"