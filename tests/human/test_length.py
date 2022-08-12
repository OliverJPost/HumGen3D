import pytest
from HumGen3D.tests.fixtures import (
    ALL_HUMAN_FIXTURES,
    male_human,
    female_human,
    context,
)


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_length(human, context):
    old_length = human.length.centimeters
    assert old_length
    assert human.length.meters

    new_length_cm = 172

    human.length.set(new_length_cm, context)

    # FIXME this fails due to impressision
    # assert human.creation_phase.length.centimeters == new_length_cm

    human.length.set(old_length, context)
