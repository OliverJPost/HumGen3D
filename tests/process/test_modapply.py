# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811


import numpy as np
import pytest

from HumGen3D.backend import hg_log
from HumGen3D.human.human import Human
from HumGen3D.human.process.bake import BakeTexture
from HumGen3D.tests.test_fixtures import *


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_modapply(human, context):
    human.process.apply_modifiers(context=context)
