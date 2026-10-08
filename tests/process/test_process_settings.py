# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

"""The settings schema, the recipes and the pure helpers of the process system.

Nothing here needs a human, these tests are fast.
"""

import json
import os
from types import SimpleNamespace

import bpy
import pytest
from HumGen3D.common.progress import phase, run
from HumGen3D.human.process import migrate, naming, pipeline, quality
from HumGen3D.human.process import settings as settings_module
from HumGen3D.human.process.export import fbx_kwargs, gltf_kwargs
from HumGen3D.human.process.game_rig import INFLUENCE_LIMITS, PRESETS, REST_POSE_ITEMS, UNIT_ITEMS
from HumGen3D.human.process.lod import CLOTHING_DECIMATE_RATIOS
from HumGen3D.human.process.settings import (
    CLIP_LAYOUTS,
    CLIP_SOURCES,
    NAMING_SCHEMES,
    NORMAL_MAP_DIRECTIONS,
    OUTPUT_FORMATS,
    ROOT_MOTION_OPTIONS,
    SCHEMA_VERSION,
    SHIPPED_RECIPE_FOLDER,
    TEXTURE_FORMATS,
    TEXTURE_PASSES,
    TEXTURE_PLACEMENTS,
    TEXTURE_SETS,
    TEXTURE_WORKFLOWS,
    AnimationSettings,
    ExportSettings,
    OutputSettings,
    QualitySettings,
    ScriptSettings,
    ShapeKeySettings,
    TextureSettings,
    recipe_items,
)
from HumGen3D.human.process.shape_keys import GROUP_ACTIONS, KEY_GROUPS, actions_for_level
from HumGen3D.tests.test_fixtures import *

with open(os.path.join(SHIPPED_RECIPE_FOLDER, "order.json")) as _f:
    SHIPPED_RECIPES = json.load(_f)

HAIRCARD_QUALITIES = ("ultra", "high", "medium", "low", "haircap_only")
SKELETON_NAMES = ("humanoid", "unreal", "mixamo", "humgen", "custom")


def _ids(items):
    return {item[0] for item in items}


def exotic_settings() -> ExportSettings:
    """Settings with every field away from its default, see test_exotic_differs."""
    settings = ExportSettings(recipe="exotic")
    out = settings.output
    out.format, out.folder, out.name, out.naming = "glb", "/tmp/hg_exotic", "{name}_X", "custom"
    out.naming_templates = {"rig": "R_{name}", "mesh": "M_{name}_{part}", "material": "Mat_{part}", "texture": "Tex_{part}_{pass}"}
    out.textures, out.keep_copy = "embedded", True
    out.fbx.axis_forward, out.fbx.axis_up = "Y", "Z"
    out.fbx.primary_bone_axis, out.fbx.secondary_bone_axis = "X", "-Y"
    out.fbx.leaf_bones = out.fbx.custom_properties = out.fbx.triangulate = True
    out.fbx.smoothing = "EDGE"
    out.gltf.tangents, out.gltf.image_format, out.gltf.draco = True, "JPEG", True
    settings.lods = [
        QualitySettings(body=1, clothing="medium", eyes="medium", teeth=2, haircards="low", bones_per_vertex=8),
        QualitySettings(body=2, clothing="low", eyes="low", teeth=0, haircards="haircap_only", bones_per_vertex=2),
    ]
    settings.meshes.enabled = False
    settings.meshes.remove_hidden_skin = settings.meshes.remove_clothing_subdiv = False
    settings.meshes.remove_clothing_solidify = False
    settings.haircards.enabled = False
    sk = settings.skeleton
    sk.enabled, sk.names, sk.names_file, sk.rest_pose = False, "custom", "/tmp/names.json", "a_pose"
    sk.root_bone, sk.root_bone_name = False, "Origin"
    sk.keep_eyes = sk.keep_jaw = sk.keep_breasts = False
    sk.keep_metacarpals, sk.units = True, "centimeters"
    keys = settings.shape_keys
    keys.enabled, keys.face_rig, keys.expressions, keys.correctives = False, "remove", "remove", "remove"
    keys.body, keys.face, keys.age = "keep", "remove", "keep"
    keys.keep = {"body": ["Muscular"], "age": []}
    keys.lod0_only = False
    tex = settings.textures
    tex.enabled = False
    tex.resolution = {"body": 512, "clothing": 256, "eyes": 128, "teeth": 4096, "hair": 2048}
    tex.passes = {"body": ["base_color"], "clothing": ["normal"], "eyes": [], "teeth": ["metallic"], "hair": ["roughness", "alpha"]}
    tex.file_format, tex.workflow, tex.normal_map = "jpeg", "orm", "directx"
    tex.pack_hair_alpha, tex.samples = False, 64
    anim = settings.animations
    anim.enabled, anim.source, anim.clips, anim.layout = True, "library", ["a/b.json"], "per_clip"
    anim.sample_rate, anim.root_motion = 30, "root"
    settings.scripts.enabled = True
    settings.scripts.items = [ScriptSettings(path="/tmp/x.py", stage="start", args={"n": 2}, on_error="skip")]
    return settings


def _leaves(data, prefix=""):
    if isinstance(data, dict):
        for key, value in data.items():
            yield from _leaves(value, f"{prefix}.{key}" if prefix else key)
    else:
        yield prefix, data


# Schema


def test_default_roundtrip():
    settings = ExportSettings()
    assert ExportSettings.from_dict(settings.to_dict()) == settings
    assert ExportSettings.from_json(settings.to_json()) == settings
    assert settings.version == SCHEMA_VERSION


def test_exotic_roundtrip():
    settings = exotic_settings()
    again = ExportSettings.from_json(settings.to_json())
    assert again == settings
    assert isinstance(again.lods[1], QualitySettings)
    assert isinstance(again.scripts.items[0], ScriptSettings)


def test_exotic_differs_from_defaults_everywhere():
    """Guards the property round trip tests: a field added to the schema has to
    get an exotic value here, and through that a test of its interface control."""
    default = dict(_leaves(ExportSettings().to_dict()))
    exotic = dict(_leaves(exotic_settings().to_dict()))
    # Lists of sections are compared whole
    same = [key for key in default if key not in ("version",) and default[key] == exotic.get(key)]
    assert not same, f"Fields with their default value in exotic_settings: {same}"


def test_copy_is_deep():
    settings = exotic_settings()
    copy = settings.copy()
    copy.lods[0].body = 0
    copy.textures.resolution["body"] = 1
    copy.scripts.items[0].args["n"] = 99
    assert settings.lods[0].body == 1
    assert settings.textures.resolution["body"] == 512
    assert settings.scripts.items[0].args["n"] == 2


def test_unknown_keys_are_ignored():
    data = ExportSettings().to_dict()
    data["from_the_future"] = 1
    data["output"]["hologram"] = True
    data["lods"][0]["nanite"] = True
    settings = ExportSettings.from_dict(data)
    assert settings == ExportSettings()


def test_missing_fields_get_defaults():
    settings = ExportSettings.from_dict({"output": {"format": "glb"}, "lods": [{"body": 2}]})
    assert settings.output.format == "glb"
    assert settings.output.naming == "plain"
    assert settings.lods[0].body == 2
    assert settings.lods[0].clothing == QualitySettings().clothing
    assert settings.textures == TextureSettings()


def test_optional_clip_list():
    """None means every clip, an empty list means none, both survive JSON."""
    for clips in (None, [], ["Walk"]):
        settings = ExportSettings(animations=AnimationSettings(clips=clips))
        assert ExportSettings.from_json(settings.to_json()).animations.clips == clips


def test_scripts_as_list_from_before_the_toggle():
    data = ExportSettings().to_dict()
    data["scripts"] = [{"path": "/a.py", "stage": "start"}]
    settings = ExportSettings.from_dict(data)
    assert settings.scripts.enabled
    assert settings.scripts.items[0].path == "/a.py"
    data["scripts"] = []
    assert not ExportSettings.from_dict(data).scripts.enabled


def test_scripts_active():
    settings = exotic_settings()
    assert settings.scripts.active() == settings.scripts.items
    settings.scripts.enabled = False
    assert settings.scripts.active() == []


def test_differs_from_ignores_recipe_name():
    a, b = ExportSettings(recipe="unity"), ExportSettings(recipe="other")
    assert not a.differs_from(b)
    b.lods[0].body = 2
    assert a.differs_from(b)


@pytest.mark.parametrize(
    "template, expected",
    [("{name}", "Jake"), ("{name}_Game", "Jake_Game"), ("Hero", "Hero"), ("", "Jake"), ("   ", "Jake")],
)
def test_resolved_name(template, expected):
    assert OutputSettings(name=template).resolved_name("Jake") == expected
    assert ExportSettings(output=OutputSettings(name=template)).resolved_name("Jake") == expected


@pytest.mark.parametrize("output_format", [ident for ident, *_ in OUTPUT_FORMATS])
def test_output_format_flags(output_format):
    output = OutputSettings(format=output_format)
    assert output.is_file == (output_format != "in_file")
    assert output.has_rig == (output_format in ("in_file", "fbx", "glb", "gltf"))


def test_texture_resolution_tier():
    textures = TextureSettings()
    textures.set_resolution_tier("512")
    assert textures.resolution == quality.resolution_of_tier("512")
    with pytest.raises(ValueError):
        textures.set_resolution_tier("8k")


# Recipes


def test_order_lists_every_shipped_recipe():
    files = {
        os.path.splitext(f)[0]
        for f in os.listdir(SHIPPED_RECIPE_FOLDER)
        if f.endswith(".json") and f != "order.json"
    }
    assert set(SHIPPED_RECIPES) == files
    assert len(SHIPPED_RECIPES) == len(set(SHIPPED_RECIPES))


@pytest.mark.parametrize("recipe", SHIPPED_RECIPES)
def test_shipped_recipe_is_valid(recipe):
    settings = ExportSettings.from_recipe(recipe)
    assert settings.recipe == recipe
    assert settings.version == SCHEMA_VERSION
    with open(os.path.join(SHIPPED_RECIPE_FOLDER, recipe + ".json")) as f:
        data = json.load(f)
    assert data.get("label"), "A recipe needs a label for the dropdown"
    assert data["version"] == SCHEMA_VERSION
    # Every key of the file is a field, no typos that would be ignored silently
    known = settings.to_dict()
    for key, value in data.items():
        if key == "label":
            continue
        assert key in known, f"{recipe}: unknown section {key}"
        if isinstance(value, dict):
            for sub in value:
                assert sub in known[key], f"{recipe}: unknown field {key}.{sub}"

    output = settings.output
    assert output.format in _ids(OUTPUT_FORMATS)
    assert output.naming in _ids(NAMING_SCHEMES)
    assert output.textures in _ids(TEXTURE_PLACEMENTS)
    assert not output.folder, "A shipped recipe must not point at a folder"
    assert settings.lods
    for level in settings.lods:
        assert level.body in (0, 1, 2)
        assert level.clothing in CLOTHING_DECIMATE_RATIOS
        assert level.eyes in ("original", "high", "medium", "low")
        assert level.teeth in (0, 1, 2)
        assert level.haircards in HAIRCARD_QUALITIES
        assert str(level.bones_per_vertex) in _ids(INFLUENCE_LIMITS)
    skeleton = settings.skeleton
    assert skeleton.names in SKELETON_NAMES
    assert skeleton.rest_pose in _ids(REST_POSE_ITEMS)
    assert skeleton.units in _ids(UNIT_ITEMS)
    for group, *_ in KEY_GROUPS:
        action = getattr(settings.shape_keys, group)
        assert action in GROUP_ACTIONS.get(group, ("keep", "bake", "remove"))
    textures = settings.textures
    assert set(textures.resolution) == set(TEXTURE_SETS)
    assert set(textures.passes) == set(TEXTURE_SETS)
    for passes in textures.passes.values():
        assert set(passes) <= _ids(TEXTURE_PASSES)
    assert textures.workflow in _ids(TEXTURE_WORKFLOWS)
    assert textures.normal_map in _ids(NORMAL_MAP_DIRECTIONS)
    assert textures.file_format in _ids(TEXTURE_FORMATS)
    animations = settings.animations
    assert animations.source in _ids(CLIP_SOURCES)
    assert animations.layout in _ids(CLIP_LAYOUTS)
    assert animations.root_motion in _ids(ROOT_MOTION_OPTIONS)
    assert not settings.scripts.active()


@pytest.mark.parametrize(
    "recipe, expected",
    [
        ("unity", {"output.format": "fbx", "skeleton.names": "humanoid", "skeleton.rest_pose": "t_pose", "textures.workflow": "metallic_smoothness", "textures.normal_map": "directx", "animations.layout": "per_clip"}),
        ("unreal", {"output.naming": "unreal", "skeleton.names": "unreal", "skeleton.rest_pose": "a_pose", "skeleton.units": "centimeters", "textures.workflow": "orm", "textures.normal_map": "directx"}),
        ("godot", {"output.format": "glb", "output.textures": "embedded", "skeleton.names": "humanoid", "textures.workflow": "metallic_roughness", "textures.normal_map": "opengl", "animations.layout": "with_mesh"}),
        ("mixamo", {"skeleton.names": "mixamo", "skeleton.root_bone": False, "skeleton.rest_pose": "t_pose"}),
        ("blender", {"output.format": "in_file", "textures.enabled": False, "skeleton.enabled": False, "haircards.enabled": False}),
    ],
)
def test_recipe_engine_knowledge(recipe, expected):
    """The engine conventions live in the recipes, see CLAUDE.md."""
    flat = dict(_leaves(ExportSettings.from_recipe(recipe).to_dict()))
    for key, value in expected.items():
        assert flat[key] == value, key


def test_recipe_bone_names_match_preset():
    """The humanoid, unreal and mixamo names of the recipes are game rig presets."""
    for recipe in SHIPPED_RECIPES:
        names = ExportSettings.from_recipe(recipe).skeleton.names
        assert names == "humgen" or names in PRESETS


def test_recipe_items():
    items = recipe_items()
    shipped = [item for item in items if item[2] == "Built-in"]
    assert [ident for ident, *_ in shipped] == SHIPPED_RECIPES
    assert items[: len(shipped)] == shipped, "Shipped recipes come first"
    for ident, label, group in items:
        assert label
        # Every listed recipe loads, also the user's, migrated when old
        settings = ExportSettings.from_recipe(ident)
        assert settings.version == SCHEMA_VERSION


def test_unknown_recipe():
    with pytest.raises(FileNotFoundError):
        ExportSettings.from_recipe("no_such_engine")


@pytest.fixture
def content_folder(tmp_path, monkeypatch):
    """A content folder of its own, so saving a recipe leaves the user's alone."""
    prefs = SimpleNamespace(filepath=str(tmp_path), is_trial=False)
    for module in (settings_module, migrate, pipeline):
        monkeypatch.setattr(module, "get_prefs", lambda: prefs)
    return tmp_path


def test_save_recipe(content_folder):
    settings = exotic_settings()
    path = settings.save_recipe("Team", "Hero")
    assert path == os.path.join(str(content_folder), "process_templates", "Team", "Hero.json")
    with open(path) as f:
        assert json.load(f)["recipe"] == ""

    assert ("Team/Hero.json", "Hero", "Team") in [
        (ident.replace(os.sep, "/"), label, group) for ident, label, group in recipe_items()
    ]
    loaded = ExportSettings.from_recipe(os.path.join("Team", "Hero.json"))
    assert not loaded.differs_from(settings)
    assert ExportSettings.from_recipe(path).to_dict() == loaded.to_dict() | {"recipe": path}


def test_saved_recipe_in_root_folder_is_saved_group(content_folder):
    ExportSettings().save_recipe("", "Loose")
    assert ("Loose.json", "Loose", "Saved") in recipe_items()


def test_default_output_folder(content_folder):
    assert pipeline.output_folder(ExportSettings()) == os.path.join(
        str(content_folder), pipeline.DEFAULT_EXPORT_FOLDER
    )
    assert pipeline.output_folder(ExportSettings(output=OutputSettings(folder="/a/b/"))) == "/a/b"


# Migration of version 1 recipes

V1_RECIPE = {
    "main": {"bake_file_type": "jpeg", "export_file_type": "gltf separate", "output_type": "export"},
    "baking": {"res_body": "512", "res_eyes": "128", "res_teeth": "128", "res_clothes": "256", "export_folder": "/tmp/old", "samples": "16"},
    "haircards": {"quality": "medium", "face_hair": False},
    "lod": {"body_lod": "2", "decimate_ratio": 0.3, "eyes": "low", "teeth": "1"},
    "game_rig": {"preset": "unreal", "max_influences": "2", "units": "centimeters", "add_root_bone": False},
    "shapekeys": {"face_rig": "remove", "expressions": "keep"},
    "modapply": {"enabled_items": ["SUBSURF"]},
    "scripting": {"does_not_exist.py": {}},
    "rig_renaming": {"head": "Head"},
}


def test_migrate_v1():
    data = migrate.migrate_v1(json.loads(json.dumps(V1_RECIPE)))
    settings = ExportSettings.from_dict(data)
    assert settings.version == SCHEMA_VERSION
    assert settings.output.format == "gltf"
    assert settings.output.folder == "/tmp/old"
    level = settings.lods[0]
    assert (level.body, level.clothing, level.eyes, level.teeth) == (2, "medium", "low", 1)
    assert level.haircards == "medium"
    assert level.bones_per_vertex == 2
    assert settings.haircards.enabled
    assert settings.skeleton.enabled
    assert settings.skeleton.names == "unreal"
    assert settings.skeleton.units == "centimeters"
    assert settings.skeleton.root_bone is False
    assert settings.shape_keys.face_rig == "remove"
    assert settings.shape_keys.expressions == "keep"
    assert settings.textures.enabled
    assert settings.textures.resolution == {"body": 512, "clothing": 256, "eyes": 128, "teeth": 128, "hair": 512}
    assert settings.textures.samples == 16
    assert settings.textures.file_format == "jpeg"
    assert settings.meshes.remove_hidden_skin is False
    assert not settings.scripts.enabled, "A missing script is dropped"


def test_migrate_v1_minimal():
    """A recipe of only a baking section, like 'Quick 512px bake'."""
    data = migrate.migrate_v1({"baking": {"res_body": "512", "res_eyes": "128"}})
    settings = ExportSettings.from_dict(data)
    assert settings.output.format == "in_file"
    assert settings.textures.enabled
    level = settings.lods[0]
    assert (level.body, level.clothing, level.eyes, level.teeth) == (0, "original", "original", 0)
    assert not settings.haircards.enabled
    assert not settings.skeleton.enabled


def test_from_recipe_migrates_v1_files(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(json.dumps(V1_RECIPE))
    settings = ExportSettings.from_recipe(str(path))
    assert settings.version == SCHEMA_VERSION
    assert settings.output.format == "gltf"


# Quality tiers


@pytest.mark.parametrize("tier", [ident for ident, *_ in quality.QUALITY_TIERS])
def test_quality_tier_roundtrip(tier):
    settings = QualitySettings.from_tier(tier)
    assert quality.tier_of(settings) == tier
    assert quality.tier_label(tier)
    # A copy, changing it doesn't change the tier
    settings.body = 9
    assert quality.quality_of_tier(tier).body != 9


def test_quality_tiers_get_lower():
    tiers = [quality.quality_of_tier(ident) for ident, *_ in quality.QUALITY_TIERS[1:]]
    for higher, lower in zip(tiers, tiers[1:]):
        assert lower.body >= higher.body
        assert CLOTHING_DECIMATE_RATIOS[lower.clothing] <= CLOTHING_DECIMATE_RATIOS[higher.clothing]


def test_custom_and_unknown_tiers():
    assert quality.tier_of(QualitySettings(body=2, clothing="original")) == "custom"
    with pytest.raises(ValueError):
        quality.quality_of_tier("potato")
    assert quality.texture_tier_of({"body": 1}) == "custom"
    for ident, _, resolution in quality.TEXTURE_TIERS:
        assert quality.texture_tier_of(quality.resolution_of_tier(ident)) == ident
        assert set(resolution) == set(TEXTURE_SETS)
        assert set(resolution.values()) <= set(quality.RESOLUTIONS)


# Naming


@pytest.mark.parametrize(
    "text, expected",
    [("HG_Body.001", "HG_Body"), ("Jake Smith", "Jake_Smith"), ("a..b", "a_b"), ("__x__", "x"), ("Jake.12", "Jake_12")],
)
def test_clean(text, expected):
    assert naming.clean(text) == expected


def test_namer_plain():
    namer = naming.Namer(OutputSettings(), "Jake.001")
    assert namer.rig() == "Jake"
    assert namer.mesh("Body") == "Jake_Body"
    assert namer.material("Skin") == "Jake_Skin"
    assert namer.texture("Body", "base_color") == "Jake_Body_BaseColor"
    assert namer.texture("Body", "metallic_smoothness") == "Jake_Body_MetallicSmoothness"


def test_namer_unreal():
    namer = naming.Namer(OutputSettings(naming="unreal"), "Jake")
    assert namer.rig() == "SK_Jake"
    assert namer.mesh("Body") == "SK_Jake_Body"
    assert namer.material("Skin") == "M_Jake_Skin"
    assert namer.texture("Body", "base_color") == "T_Jake_Body_BC"
    assert namer.texture("Body", "orm") == "T_Jake_Body_ORM"


def test_namer_custom_templates():
    output = OutputSettings(naming="custom", naming_templates={"mesh": "{part}-{name}", "texture": "tx {pass} {part}"})
    namer = naming.Namer(output, "Jake")
    assert namer.mesh("Body") == "Body-Jake"
    assert namer.texture("Body", "normal") == "tx_Normal_Body"
    # Templates that are not given fall back on the plain scheme
    assert namer.rig() == "Jake"
    assert namer.material("Skin") == "Jake_Skin"


def test_namer_lod_levels():
    single = naming.Namer(OutputSettings(), "Jake", 0, 1)
    assert single.mesh("Body") == "Jake_Body"
    first = naming.Namer(OutputSettings(), "Jake", 0, 3)
    second = naming.Namer(OutputSettings(), "Jake", 2, 3)
    assert first.mesh("Body") == "Jake_Body_LOD0"
    assert second.mesh("Body") == "Jake_Body_LOD2"
    # Shared materials keep the name of the first level, own ones get the level
    assert second.material("Skin") == "Jake_Skin"
    assert first.material("Eyes", per_level=True) == "Jake_Eyes"
    assert second.material("Eyes", per_level=True) == "Jake_Eyes_LOD2"
    assert second.texture("Hair", "alpha", per_level=True) == "Jake_Hair_Alpha_LOD2"


def test_exact_names_swaps_and_restores():
    original = bpy.data.materials.new("HGTestName")
    copy = bpy.data.materials.new("HGTestName")
    try:
        assert copy.name == "HGTestName.001"
        with naming.exact_names([copy]):
            assert copy.name == "HGTestName"
            assert original.name.startswith("HGTestName" + naming.TEMP_SUFFIX)
        assert copy.name == "HGTestName.001"
        assert original.name == "HGTestName"
    finally:
        bpy.data.materials.remove(original)
        bpy.data.materials.remove(copy)


# Shape key actions per level


def test_actions_for_level():
    settings = ShapeKeySettings(body="keep", face="bake", age="remove")
    assert actions_for_level(settings, 0) is settings
    lower = actions_for_level(settings, 1)
    assert (lower.face_rig, lower.expressions, lower.correctives) == ("remove",) * 3
    assert (lower.body, lower.face, lower.age) == ("bake", "bake", "remove")
    assert settings.body == "keep", "The settings of the first level are not changed"
    settings.lod0_only = False
    assert actions_for_level(settings, 2) is settings


# What the pipeline makes of the settings


def test_effective_settings_file_needs_textures():
    settings = ExportSettings.from_recipe("unity")
    settings.textures.enabled = False
    assert pipeline._effective_settings(settings).textures.enabled
    assert not settings.textures.enabled, "The settings passed in are not changed"


def test_effective_settings_no_rig_no_animations():
    settings = ExportSettings(output=OutputSettings(format="obj"), animations=AnimationSettings(enabled=True))
    assert not pipeline._effective_settings(settings).animations.enabled


def test_effective_settings_meshes_off():
    settings = ExportSettings.from_recipe("unity")
    settings.meshes.enabled = False
    settings.lods.append(QualitySettings.from_tier("low"))
    effective = pipeline._effective_settings(settings)
    for level in effective.lods:
        assert (level.body, level.clothing, level.eyes, level.teeth) == (0, "original", "original", 0)
    assert effective.lods[1].haircards == "low", "The levels still differ in hair cards"
    assert not effective.meshes.remove_hidden_skin


def test_effective_settings_shape_keys_off():
    settings = ExportSettings(shape_keys=ShapeKeySettings(enabled=False, body="keep", age="remove"))
    keys = pipeline._effective_settings(settings).shape_keys
    assert (keys.face_rig, keys.expressions, keys.correctives) == ("remove",) * 3
    assert (keys.body, keys.age) == ("bake", "remove")


def test_texture_folder_placement(tmp_path):
    settings = ExportSettings.from_recipe("unity")
    folder = str(tmp_path)
    assert pipeline._texture_folder(settings, folder) == (os.path.join(folder, "Textures"), None)
    settings.output.textures = "next_to_file"
    assert pipeline._texture_folder(settings, folder) == (folder, None)
    settings.output.textures = "embedded"
    scratch, remove = pipeline._texture_folder(settings, folder)
    assert scratch == remove and os.path.isdir(scratch)
    os.rmdir(scratch)
    settings.output.format = "glb"
    assert pipeline._texture_folder(settings, folder) == (None, None), "glTF packs the images"
    settings.output.format = "in_file"
    assert pipeline._texture_folder(settings, None) == (None, None), "Packed in the blend file"


def test_exporter_arguments():
    output = ExportSettings.from_recipe("unreal").output
    kwargs = fbx_kwargs(output, "centimeters")
    assert kwargs["apply_scale_options"] == "FBX_SCALE_ALL"
    assert kwargs["use_leaf_bones"] is False
    assert kwargs["path_mode"] == "RELATIVE" and not kwargs["embed_textures"]
    output.textures = "embedded"
    kwargs = fbx_kwargs(output, "meters")
    assert kwargs["apply_scale_options"] == "FBX_SCALE_NONE"
    assert kwargs["path_mode"] == "COPY" and kwargs["embed_textures"]
    assert gltf_kwargs(exotic_settings().output) == {"image_format": "JPEG", "tangents": True, "draco": True}


# Progress


def test_progress_run_and_phase():
    def steps():
        yield 0.2
        yield 0.1  # Going back is not reported
        yield 0.6
        return "done"

    seen = []
    assert run(steps(), seen.append) == "done"
    assert seen == [0.2, 0.6, 1.0]

    def outer():
        first = yield from phase(steps(), 0.0, 0.5)
        second = yield from phase(steps(), 0.5, 1.0)
        return first + second

    seen = []
    assert run(outer(), seen.append) == "donedone"
    assert seen == pytest.approx([0.1, 0.3, 0.6, 0.8, 1.0])


def test_tracker_weights():
    tracker = pipeline._Tracker(10)
    assert tracker.tick(5) == 0.5

    def steps():
        yield 0.5
        return 1

    fractions = []
    gen = tracker.phase(steps(), 5)
    try:
        while True:
            fractions.append(next(gen))
    except StopIteration as finished:
        assert finished.value == 1
    assert fractions == [0.75]
    assert tracker.done == 10
