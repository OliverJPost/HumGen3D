# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

import pytest

from HumGen3D.tests.test_fixtures import *
from pytest_lazyfixture import lazy_fixture

NON_RIGIFY_FIXTURES = [lazy_fixture("male_human"), lazy_fixture("female_human")]


def _weighted_group_names(human):
    names = set()
    for obj in human.objects:
        if obj.type != "MESH":
            continue
        for vertex in obj.data.vertices:
            for group in vertex.groups:
                if group.weight > 0:
                    names.add(obj.vertex_groups[group.group].name)
    return names


@pytest.mark.parametrize("human", NON_RIGIFY_FIXTURES)
def test_deform_flags_match_weights(human):
    """Only the bones that deform a mesh are flagged as deforming, see
    CONTENT_CHANGELOG.md for the change to HG_HUMAN.blend."""
    weighted = _weighted_group_names(human)
    for bone in human.objects.rig.data.bones:
        assert bone.use_deform == (bone.name in weighted), bone.name
