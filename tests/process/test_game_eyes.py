# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

import os

import numpy as np
import pytest

from HumGen3D.common.exceptions import HumGenException
from HumGen3D.human.process import game_eyes
from HumGen3D.human.process.settings import TextureBakeSettings
from HumGen3D.human.process.textures import plan_texture_sets
from HumGen3D.tests.test_fixtures import *

ORIGINAL_TRIS_COUNT = 10_560
MAX_TRIS_COUNTS = {"high": 4000, "medium": 1000, "low": 250}


def _tris_count(obj):
    return sum(len(polygon.vertices) - 2 for polygon in obj.data.polygons)


def _evaluated_dimensions(obj, context):
    depsgraph = context.evaluated_depsgraph_get()
    depsgraph.update()
    obj_eval = obj.evaluated_get(depsgraph)
    coords = np.empty(len(obj_eval.data.vertices) * 3, dtype=np.float64)
    obj_eval.data.vertices.foreach_get("co", coords)
    coords = coords.reshape(-1, 3)
    return coords.max(axis=0) - coords.min(axis=0)


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_game_eyes_mesh(human, context):
    eyes = human.objects.eyes
    assert _tris_count(eyes) == ORIGINAL_TRIS_COUNT
    width, _, height = _evaluated_dimensions(eyes, context)

    human.process.convert_to_game_eyes()

    assert human.process.has_game_eyes
    assert _tris_count(eyes) <= MAX_TRIS_COUNTS["medium"]
    assert not eyes.data.shape_keys

    # The shape key that fits the eyes in the head has to be applied, not removed
    new_width, _, new_height = _evaluated_dimensions(eyes, context)
    assert new_width == pytest.approx(width, abs=1e-4)
    assert new_height == pytest.approx(height, abs=1e-4)

    # Every vertex still follows a single eye bone
    assert all(len(vert.groups) == 1 for vert in eyes.data.vertices)

    # No UV seams, as lowering the resolution would stretch the texture over them
    uvs_per_vert = [set() for _ in eyes.data.vertices]
    uv_data = eyes.data.uv_layers.active.data
    for loop in eyes.data.loops:
        uvs_per_vert[loop.vertex_index].add(uv_data[loop.index].uv.to_tuple(4))
    assert all(len(uvs) == 1 for uvs in uvs_per_vert)
    assert all(0 <= value <= 1 for uvs in uvs_per_vert for uv in uvs for value in uv)


@pytest.mark.parametrize("detail", ["high", "medium", "low"])
def test_game_eyes_detail(male_human, detail):
    male_human.process.convert_to_game_eyes(detail)

    tris_count = _tris_count(male_human.objects.eyes)
    assert 0 < tris_count <= MAX_TRIS_COUNTS[detail]


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_game_eyes_material(human):
    eyes = human.objects.eyes
    old_inner_material = human.materials.eye_inner
    iris_color = human.eyes.iris_color.value

    human.process.convert_to_game_eyes()

    assert list(eyes.data.materials) == [old_inner_material]
    assert all(polygon.material_index == 0 for polygon in eyes.data.polygons)
    assert human.materials.eye_inner == old_inner_material
    assert human.materials.eye_outer is None
    assert human.eyes.outer_material is None

    principled = next(
        node
        for node in old_inner_material.node_tree.nodes
        if node.bl_idname == "ShaderNodeBsdfPrincipled"
    )
    assert principled.inputs["Roughness"].default_value == pytest.approx(
        game_eyes.ROUGHNESS
    )
    assert not principled.inputs["Normal"].is_linked

    # The eye color can still be changed, as long as the eyes are not baked
    assert human.eyes.iris_color.value == iris_color
    human.eyes.randomize()

    eye_slots = [s.slot for s in plan_texture_sets(human, TextureBakeSettings()) if s.obj == eyes]
    assert eye_slots == [0]


def test_game_eyes_lookat_bones(male_human):
    bones = male_human.objects.rig.data.bones
    lookat_bones = [bone for bone in bones if bone.name.startswith("eyeball_lookat")]
    assert len(lookat_bones) == 3

    male_human.process.convert_to_game_eyes()

    assert not any(bone.use_deform for bone in lookat_bones)
    assert bones["eyeball.L"].use_deform
    assert bones["eyeball.R"].use_deform


def test_game_eyes_fails(male_human):
    with pytest.raises(ValueError):
        male_human.process.convert_to_game_eyes("ultra")

    male_human.process.convert_to_game_eyes()
    with pytest.raises(HumGenException):
        male_human.process.convert_to_game_eyes()


def test_game_eyes_baked(male_human, context, tmp_path):
    male_human.process.convert_to_game_eyes()
    textures = TextureBakeSettings(resolution={key: 128 for key in TextureBakeSettings().resolution})
    male_human.process.bake_textures(textures, str(tmp_path), only_sets=("eyes",), context=context)

    eyes = male_human.objects.eyes
    assert len(eyes.data.materials) == 1
    nodes = eyes.data.materials[0].node_tree.nodes
    assert nodes["Principled BSDF"].inputs["Roughness"].default_value == pytest.approx(
        game_eyes.ROUGHNESS
    )
    assert nodes["base_color"].image.size[0] == 128


@pytest.mark.parametrize("game_eyes_enabled", [False, True])
def test_export_keeps_eye_materials(male_human, context, tmp_path, game_eyes_enabled):
    if game_eyes_enabled:
        male_human.process.convert_to_game_eyes()
    mesh = male_human.objects.eyes.data
    materials = list(mesh.materials)
    material_indices = [polygon.material_index for polygon in mesh.polygons]
    male_human.location = (1, 2, 0)

    for _ in range(2):
        male_human.export.to_fbx(os.path.join(tmp_path, "test.fbx"), context=context)

    assert list(mesh.materials) == materials
    assert [polygon.material_index for polygon in mesh.polygons] == material_indices
    assert tuple(male_human.location) == (1, 2, 0)
