# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

import os
import random

import pytest
import pywavefront

from HumGen3D.backend import hg_log
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.human.expression.expression import FACE_RIG_BONE_NAMES
from HumGen3D.human.human import Human
from HumGen3D.tests.test_fixtures import *

MESH_COUNT = 4  # body, eyes, lower teeth, upper teeth
EYE_VERT_COUNT = 5_288
EYE_TRIS_COUNT = 10_560
LOWER_TEETH_VERT_COUNT = 3_254
LOWER_TEETH_TRIS_COUNT = 6_480
UPPER_TEETH_VERT_COUNT = 3_201
BODY_VERT_COUNT = 25_286


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_obj_export(human: Human, context, tmp_path):
    """Test that a gltf file can be exported from a human."""
    path = os.path.join(tmp_path, "test.obj")
    human.export.to_obj(path, context=context)

    scene = pywavefront.Wavefront(path)

    if len(scene.mesh_list) != MESH_COUNT:
        print("Meshes found:")
        for mesh in scene.mesh_list:
            hg_log(mesh.name, level="WARNING")
        raise AssertionError(
            f"Expected {MESH_COUNT} meshes, found {len(scene.mesh_list)}"
        )

    _assert_object(scene.mesh_list, "HG_Eyes")
    _assert_object(scene.mesh_list, "HG_TeethLower")
    _assert_object(scene.mesh_list, "HG_TeethUpper")
    _assert_object(scene.mesh_list, "HG_Body")


def _assert_object(object_iterator, starts_with):
    objects = [obj for obj in object_iterator if obj.name.startswith(starts_with)]
    assert len(objects) == 1