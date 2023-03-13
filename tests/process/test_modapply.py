# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

import bpy
import pytest

from HumGen3D.human.process.apply_modifiers import apply_modifiers, refresh_modapply
from HumGen3D.tests.test_fixtures import *


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_armature_apply(human, context):
    # human as context.object
    context.view_layer.objects.active = human.objects.rig
    refresh_modapply(None, context)
    col = context.scene.modapply_col

    for item in col:
        if item.mod_type == "ARMATURE":
            item.enabled = True
            break
    apply_modifiers(human, context=context)
