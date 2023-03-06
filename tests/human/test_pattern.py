# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8: noqa F811
import random

import pytest
from HumGen3D.tests.test_fixtures import *
from HumGen3D.tests.human.test_clothing import human_with_outfit


def test_add_pattern_clothing(human_with_outfit, context):
    """Test adding a pattern to a human."""
    human = human_with_outfit
    pattern = random.choice(human.clothing.outfit.pattern.get_options(context=context))
    for obj in human.clothing.outfit.objects:
        human.clothing.outfit.pattern.set(pattern, obj)

