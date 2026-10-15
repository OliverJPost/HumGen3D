# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Humans made with Human Generator 4.0 go through the process system.

`files/human_v4_0_33.blend` was saved after making two humans with the code of
the v4.0.33 tag and the content packs of 4.0: HG_Bobby with particle hair and
HG_Louella with her scalp hair turned into hair cards by 4.0. The base model of
4.0 had the face rig, eye target and heel.02 bones marked as deforming, which
the file doesn't have because it was made with newer content, so the tests set
that back.
"""

import json
import os

import bpy
import pytest
from HumGen3D import ExportSettings, Human
from HumGen3D.human.process import manifest
from HumGen3D.human.process.pipeline import OLD_PROCESS_KEYS

from HumGen3D.tests.process.process_helpers import cheap_settings

FILE = os.path.join(os.path.dirname(__file__), "files", "human_v4_0_33.blend")
OLD_DEFORM_BONES = ("facs", "eyeball_lookat", "heel.02")


@pytest.fixture(scope="module")
def v4_humans():
    """The humans of the file by name, appended to the scene and removed after."""
    with bpy.data.libraries.load(FILE) as (source, target):
        target.objects = list(source.objects)
    for obj in target.objects:
        bpy.context.scene.collection.objects.link(obj)
    humans = {}
    for obj in target.objects:
        if obj.type == "ARMATURE" and obj.HG.ishuman:
            for bone in obj.data.bones:
                if bone.name.startswith(OLD_DEFORM_BONES):
                    bone.use_deform = True
            human = Human.from_existing(obj)
            humans[obj.name.split(".")[0]] = human
    yield humans
    for human in humans.values():
        human.delete()


def test_the_file_has_both_humans(v4_humans):
    assert set(v4_humans) == {"HG_Bobby", "HG_Louella"}
    assert v4_humans["HG_Bobby"].hair.modifiers, "Bobby has particle hair"
    assert v4_humans["HG_Louella"].objects.haircards, "Louella has the hair cards of 4.0"


@pytest.mark.parametrize("recipe", ("unity", "unreal", "godot", "blender"))
def test_preflight_is_clean(v4_humans, recipe):
    for human in v4_humans.values():
        check = human.process.preflight(ExportSettings.from_recipe(recipe))
        assert check.ok, check.errors


def test_particle_hair_human_exports(v4_humans, tmp_path):
    settings = cheap_settings("unity", tmp_path)
    result = v4_humans["HG_Bobby"].process.run(settings, context=bpy.context)
    character = os.path.join(tmp_path, result.name + ".fbx")
    assert character in result.files
    assert os.path.getsize(character) > 0

    data = manifest.read(manifest.manifest_path(character))
    assert data is not None and data[manifest.FORMAT_KEY] == manifest.FORMAT
    types = {material["type"] for material in data["materials"].values()}
    assert {"skin", "eyes", "teeth", "hair_cards"} <= types
    for material in data["materials"].values():
        for texture in material["textures"].values():
            assert os.path.isfile(os.path.join(tmp_path, texture["file"]))
    # The manifest holds the settings, and loads like a recipe
    loaded = ExportSettings.from_recipe(manifest.manifest_path(character))
    assert not loaded.differs_from(result.settings)


def test_hair_card_human_processes_in_file(v4_humans):
    settings = ExportSettings.from_recipe("blender")
    settings.textures.enabled = False
    result = v4_humans["HG_Louella"].process.run(settings, context=bpy.context)
    try:
        assert len(result.humans) == 1
        assert result.humans[0].objects.haircards
        # The control bones the old rig file flagged as deforming are corrected
        rig = result.humans[0].objects.rig
        assert not any(
            bone.use_deform for bone in rig.data.bones if bone.name.startswith(OLD_DEFORM_BONES)
        )
    finally:
        for copy in result.humans:
            copy.delete()


@pytest.mark.parametrize("key", list(OLD_PROCESS_KEYS))
def test_humans_processed_in_place_are_refused(v4_humans, key):
    rig = v4_humans["HG_Bobby"].objects.rig
    rig[key] = True
    try:
        check = v4_humans["HG_Bobby"].process.preflight(ExportSettings.from_recipe("unity"))
        assert not check.ok
        assert OLD_PROCESS_KEYS[key] in check.errors[0]
    finally:
        del rig[key]


def test_broken_recipes_are_left_out(tmp_path, monkeypatch):
    from HumGen3D.human.process import settings as settings_module

    folder = tmp_path / settings_module.USER_RECIPE_FOLDER
    folder.mkdir()
    (folder / "Good.json").write_text(json.dumps(ExportSettings().to_dict()))
    # A section of a version 1 recipe that is not a dict breaks the migration
    (folder / "Old.json").write_text(json.dumps({"main": "fbx", "lod": [1, 2]}))
    (folder / "Not a recipe.json").write_text("[1, 2, 3]")
    monkeypatch.setattr(settings_module, "get_prefs", lambda: type("P", (), {"filepath": str(tmp_path)})())
    labels = [label for _, label, group in settings_module.recipe_items() if group == "Saved"]
    assert labels == ["Good"]
