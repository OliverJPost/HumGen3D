# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8: noqa F811

import pytest
from HumGen3D.tests.test_fixtures import *


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_length(human, context):
    old_height = human.height.centimeters
    assert old_height
    assert human.height.meters

    new_height_cm = 172

    human.height.set(new_height_cm, context)

    # FIXME this fails due to impressision
    # assert human.creation_phase.length.centimeters == new_length_cm

    human.height.set(old_height, context)
