# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

import json
import os

import bpy
import pytest

from HumGen3D.common import find_multiple_in_list, find_original_rig, is_processed
from HumGen3D.human.human import Human
from HumGen3D.human.process.process import ProcessSettings
from HumGen3D.tests.test_fixtures import *
from HumGen3D.user_interface.ui_baseclasses import HGPanel

ENABLED_PROPS = (
    "baking_enabled",
    "lod_enabled",
    "modapply_enabled",
    "shapekeys_enabled",
    "haircards_enabled",
    "rig_renaming_enabled",
    "renaming_enabled",
    "scripting_enabled",
    "game_rig_enabled",
)


def _tris_count(obj):
    return sum(len(polygon.vertices) - 2 for polygon in obj.data.polygons)


@pytest.fixture
def process_settings(context):
    pr_sett = context.scene.HG3D.process
    for prop_name in ENABLED_PROPS:
        setattr(pr_sett, prop_name, False)
    for prop_group in (pr_sett.lod, pr_sett.shapekeys, pr_sett.game_rig):
        for prop in prop_group.bl_rna.properties:
            if prop.identifier not in ("rna_type", "name"):
                prop_group.property_unset(prop.identifier)
    pr_sett.output = "in_file"
    pr_sett.baking.export_folder = ""
    yield pr_sett


def _process(human, context):
    for obj in context.selected_objects:
        obj.select_set(False)
    human.objects.rig.select_set(True)
    context.view_layer.objects.active = human.objects.rig

    old_objects = set(bpy.data.objects)
    assert bpy.ops.hg3d.process() == {"FINISHED"}
    return [obj for obj in bpy.data.objects if obj not in old_objects]


def test_process_in_file(male_human, context, process_settings):
    human = male_human
    rig = human.objects.rig
    eyes_tris_count = _tris_count(human.objects.eyes)
    teeth_tris_count = _tris_count(human.objects.upper_teeth)
    process_settings.lod_enabled = True
    process_settings.game_rig_enabled = True
    process_settings.game_rig.preset = "generic_t"

    new_objects = _process(human, context)
    new_rigs = [obj for obj in new_objects if obj.type == "ARMATURE"]
    assert len(new_rigs) == 1
    processed_human = Human.from_existing(new_rigs[0])

    # The result is a frozen copy with all steps applied
    assert processed_human.process.is_processed
    assert processed_human.process.has_game_eyes
    assert processed_human.process.has_t_pose_rest
    assert _tris_count(processed_human.objects.eyes) < eyes_tris_count
    assert _tris_count(processed_human.objects.upper_teeth) < teeth_tris_count
    for obj in processed_human.objects:
        assert is_processed(obj)

    # The original human is not changed and stays editable
    assert not human.process.is_processed
    assert not human.process.has_game_eyes
    assert not human.process.has_t_pose_rest
    assert _tris_count(human.objects.eyes) == eyes_tris_count
    assert _tris_count(human.objects.upper_teeth) == teeth_tris_count
    assert not is_processed(rig)

    # The interface is hidden for the processed human, not for the original
    context.view_layer.objects.active = processed_human.objects.body
    assert not HGPanel.poll(context)
    context.view_layer.objects.active = rig
    assert HGPanel.poll(context)

    # Only the original can be processed again
    selected = [rig, processed_human.objects.rig]
    assert find_multiple_in_list(selected) == {rig}

    processed_human.delete()


def test_processed_human_finds_original(male_human, context, process_settings):
    human = male_human
    rig = human.objects.rig
    new_objects = _process(human, context)
    processed_rig = next(obj for obj in new_objects if obj.type == "ARMATURE")
    processed_body = Human.from_existing(processed_rig).objects.body

    assert find_original_rig(processed_body, context.view_layer.objects) == rig
    # Editable humans have no original
    assert find_original_rig(rig, context.view_layer.objects) is None

    # Renaming the original doesn't break the reference
    rig.name = "Renamed human"
    assert find_original_rig(processed_rig, context.view_layer.objects) == rig

    context.view_layer.objects.active = processed_body
    assert bpy.ops.hg3d.select_original_human() == {"FINISHED"}
    assert context.view_layer.objects.active == rig
    assert rig.select_get()

    # The original can be removed from the scene
    scene_objects = [obj for obj in context.view_layer.objects if obj != rig]
    assert find_original_rig(processed_rig, scene_objects) is None

    Human.from_existing(processed_rig).delete()


def test_process_export(male_human, context, process_settings, tmp_path):
    human = male_human
    process_settings.lod_enabled = True
    process_settings.output = "export"
    process_settings.file_type = ".fbx"
    process_settings.baking.export_folder = str(tmp_path)
    eyes_tris_count = _tris_count(human.objects.eyes)

    new_objects = _process(human, context)

    # The processed copy is removed after exporting it
    assert not new_objects
    assert [file for file in os.listdir(tmp_path) if file.endswith(".fbx")]
    assert not human.process.is_processed
    assert _tris_count(human.objects.eyes) == eyes_tris_count


def test_process_game_rig(male_human, context, process_settings):
    human = male_human
    process_settings.game_rig_enabled = True
    process_settings.game_rig.preset = "humanoid"
    process_settings.game_rig.keep_breasts = False
    # Bone Renaming is skipped, the preset names the bones
    process_settings.rig_renaming_enabled = True
    process_settings.rig_renaming.head = "Noggin"
    # The humanoid preset sets the T-pose
    assert process_settings.game_rig.rest_pose == "t_pose"

    new_objects = _process(human, context)
    new_rigs = [obj for obj in new_objects if obj.type == "ARMATURE"]
    processed_human = Human.from_existing(new_rigs[0])
    bone_names = {bone.name for bone in processed_human.objects.rig.data.bones}

    assert processed_human.process.has_game_rig
    assert processed_human.process.has_t_pose_rest
    assert "Head" in bone_names
    assert "Noggin" not in bone_names
    assert "LeftBreast" not in bone_names
    assert not any(pose_bone.constraints for pose_bone in processed_human.pose_bones)

    assert not human.process.has_game_rig
    assert not human.process.has_t_pose_rest
    assert "head" in {bone.name for bone in human.objects.rig.data.bones}

    processed_human.delete()


def _key_names(obj):
    keys = obj.data.shape_keys
    return [key.name for key in keys.key_blocks] if keys else []


def test_process_shape_keys(male_human, context, process_settings):
    human = male_human
    human.clothing.outfit.set(
        human.clothing.outfit.get_options(context=context)[0], context
    )
    pr_sett = process_settings
    pr_sett.shapekeys_enabled = True
    pr_sett.shapekeys.face_rig = "keep"
    pr_sett.shapekeys.correctives = "remove"
    pr_sett.shapekeys.body = "keep"
    # The clothing is decimated with its kept keys
    pr_sett.lod_enabled = True
    pr_sett.lod.clothing = "high"
    cloth_tris_count = _tris_count(human.clothing.outfit.objects[0])

    new_objects = _process(human, context)
    processed_rig = next(obj for obj in new_objects if obj.type == "ARMATURE")
    processed_human = Human.from_existing(processed_rig)
    body_keys = _key_names(processed_human.objects.body)

    assert processed_human.expression.has_facial_rig
    assert "jawOpen" in body_keys
    assert not [name for name in body_keys if name.startswith(("cor_", "eyeLook"))]
    assert not [name for name in body_keys if name.startswith(("LIVE_KEY", "Male"))]
    # Body sliders are shape keys now, face sliders are baked
    assert len([name for name in body_keys if name.startswith("b_")]) > 20
    assert not [name for name in body_keys if name.startswith("f_")]

    cloth_obj = processed_human.clothing.outfit.objects[0]
    assert _tris_count(cloth_obj) < cloth_tris_count
    assert not [name for name in _key_names(cloth_obj) if name.startswith("cor_")]
    assert "Body Proportions" not in _key_names(cloth_obj)

    # The original human is not changed
    assert not human.expression.has_facial_rig
    assert "LIVE_KEY_PERMANENT" in _key_names(human.objects.body)
    assert "Body Proportions" in _key_names(human.clothing.outfit.objects[0])

    processed_human.delete()


def test_recipe_roundtrip(context, process_settings, tmp_path):
    pr_sett = process_settings
    pr_sett.lod_enabled = True
    pr_sett.lod.eyes = "low"
    pr_sett.lod.teeth = "2"
    pr_sett.lod.clothing = "high"
    pr_sett.haircards_enabled = True
    pr_sett.shapekeys_enabled = True
    pr_sett.shapekeys.face_rig = "remove"
    pr_sett.shapekeys.age = "keep"
    pr_sett.output = "export"
    pr_sett.game_rig_enabled = True
    pr_sett.game_rig.preset = "unreal"
    # Advanced settings that differ from the preset
    pr_sett.game_rig.rest_pose = "t_pose"
    pr_sett.game_rig.max_influences = "8"

    path = ProcessSettings.save_settings_to_template(
        str(tmp_path), "test_recipe", context=context
    )

    pr_sett.lod_enabled = False
    pr_sett.lod.eyes = "original"
    pr_sett.lod.teeth = "0"
    pr_sett.lod.clothing = "original"
    pr_sett.haircards_enabled = False
    pr_sett.shapekeys_enabled = False
    pr_sett.shapekeys.face_rig = "keep"
    pr_sett.shapekeys.age = "bake"
    pr_sett.baking_enabled = True
    pr_sett.output = "in_file"
    pr_sett.game_rig_enabled = False
    pr_sett.game_rig.preset = "generic_a"
    pr_sett.game_rig.max_influences = "4"

    ProcessSettings.set_settings_from_template(path, context=context)

    assert pr_sett.lod_enabled
    assert pr_sett.lod.eyes == "low"
    assert pr_sett.lod.teeth == "2"
    assert pr_sett.lod.clothing == "high"
    assert pr_sett.haircards_enabled
    assert pr_sett.shapekeys_enabled
    assert pr_sett.shapekeys.face_rig == "remove"
    assert pr_sett.shapekeys.age == "keep"
    assert pr_sett.shapekeys.body == "bake"
    assert not pr_sett.baking_enabled
    assert pr_sett.output == "export"
    assert pr_sett.game_rig_enabled
    assert pr_sett.game_rig.preset == "unreal"
    # Loading the preset does not overwrite the advanced settings of the recipe
    assert pr_sett.game_rig.rest_pose == "t_pose"
    assert pr_sett.game_rig.max_influences == "8"
    assert pr_sett.game_rig.units == "centimeters"


def test_recipe_from_older_version(context, process_settings, tmp_path):
    """Recipes saved before the eyes, teeth and frozen results were added."""
    pr_sett = process_settings
    data = {
        "main": {
            "bake_file_type": "png",
            "export_file_type": "obj",
            "output_type": "replace",
        },
        "lod": {
            "suffix": "_LOD0",
            "body_lod": "2",
            "decimate_ratio": 0.25,
            "remove_clothing_subdiv": True,
            "remove_clothing_solidify": False,
        },
        "rest_pose": {},
    }
    path = os.path.join(tmp_path, "old_recipe.json")
    with open(path, "w") as f:
        json.dump(data, f)

    ProcessSettings.set_settings_from_template(path, context=context)

    assert pr_sett.lod_enabled
    assert pr_sett.lod.body_lod == "2"
    # The decimate ratio is mapped to the nearest clothing option
    assert pr_sett.lod.clothing == "medium"
    assert not pr_sett.lod.remove_clothing_solidify
    # These didn't exist yet, so the recipe should not change them
    assert pr_sett.lod.eyes == "original"
    assert pr_sett.lod.teeth == "0"
    # The T-pose category became the generic T-pose game rig preset
    assert pr_sett.game_rig_enabled
    assert pr_sett.game_rig.preset == "generic_t"
    assert pr_sett.game_rig.rest_pose == "t_pose"
    assert pr_sett.output == "in_file"
    assert pr_sett.file_type == ".obj"
    assert not pr_sett.baking_enabled

    # A recipe without main settings
    with open(path, "w") as f:
        json.dump({"baking": {"res_body": "512"}}, f)
    ProcessSettings.set_settings_from_template(path, context=context)

    assert pr_sett.baking_enabled
    assert pr_sett.baking.res_body == "512"
    assert not pr_sett.lod_enabled
    assert not pr_sett.game_rig_enabled
