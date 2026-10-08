# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

"""The single steps of the process system, called on their own from the API.

Every step is a public method of `ProcessSettings` that takes the section of
`ExportSettings` it is about, see the docstring of that class. These tests call
them on a duplicate of a human, in the order `run` does, and check that the
steps that change a human for good refuse to run twice.
"""

import json
import os

import bpy
import pytest
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.object_finding import HUMAN_ID_KEY, ORIGINAL_ID_KEY
from HumGen3D.human.human import Human
from HumGen3D.human.process.settings import (
    AnimationSettings,
    ExportSettings,
    MeshSettings,
    OutputSettings,
    QualitySettings,
    ShapeKeySettings,
    SkeletonSettings,
    TextureSettings,
)
from HumGen3D.human.process.shape_keys import facs_key_names
from HumGen3D.tests.process.process_helpers import *
from HumGen3D.tests.test_fixtures import *


@pytest.fixture(scope="module")
def source():
    human = make_source_human("male")
    yield human
    human.delete()


@pytest.fixture
def copy(source):
    """A duplicate of the source, as the steps are meant to be called on."""
    original = snapshot(source)
    human = source.duplicate(bpy.context)
    yield human
    try:
        from HumGen3D.human.process.animations import remove_clips

        remove_clips(human)
        human.delete()
    except ReferenceError:
        pass
    assert snapshot(source) == original, "A step reached the source human"


def _key_names(obj):
    return [key.name for key in obj.data.shape_keys.key_blocks] if obj.data.shape_keys else []


def _textures(settings: ExportSettings) -> TextureSettings:
    textures = settings.textures
    textures.resolution = {key: TEST_RESOLUTION for key in textures.resolution}
    return textures


# Shape keys


def test_shape_key_options(copy):
    options = copy.process.shape_key_options(bpy.context)
    assert set(options) == {"face_rig", "expressions", "correctives", "body", "face", "age"}
    assert len(options["face_rig"]) > 40
    assert len(options["expressions"]) > 5
    assert options["correctives"]


def test_shape_keys_removed(copy):
    copy.process.set_shape_keys(face_rig="remove", expressions="remove", correctives="remove", context=bpy.context)
    keys = _key_names(copy.objects.body)
    assert not set(keys) & set(facs_key_names())
    assert not any(key.startswith("cor_") for key in keys)
    for obj in copy.clothing.outfit.objects:
        assert not any(key.startswith("cor_") for key in _key_names(obj))


def test_shape_keys_by_settings(copy):
    options = copy.process.shape_key_options(bpy.context)
    chosen = options["expressions"][:2]
    settings = ShapeKeySettings(keep={"expressions": chosen, "face_rig": options["face_rig"][:5]})
    copy.process.set_shape_keys(settings, context=bpy.context)
    keys = _key_names(copy.objects.body)
    assert len(set(keys) & set(facs_key_names())) == 5
    assert any(key.startswith("cor_") for key in keys), "Correctives are kept"
    # Of the expressions only the chosen ones
    from HumGen3D.human.process.shape_keys import key_groups

    names = [item.name for item in key_groups(copy)["expressions"]]
    assert len(names) == 2


def test_shape_keys_lower_level(copy):
    copy.process.set_shape_keys(ShapeKeySettings(), level=1, context=bpy.context)
    keys = _key_names(copy.objects.body)
    assert not set(keys) & set(facs_key_names()), "lod0_only: lower levels keep no keys"
    assert not any(key.startswith("cor_") for key in keys)


def test_shape_keys_bake_refused_for_driven_groups(copy):
    with pytest.raises(ValueError):
        copy.process.set_shape_keys(face_rig="bake", context=bpy.context)


# The whole level, step by step, in the order of run


def test_level_by_steps(copy, source, tmp_path):
    settings = ExportSettings.from_recipe("unity")
    textures = _textures(settings)
    p = copy.process

    p.set_shape_keys(settings.shape_keys, context=bpy.context)

    made = p.convert_to_haircards("low", bpy.context)
    assert made and p.has_haircards
    assert not copy.hair.modifiers, "The particle systems are removed"
    with pytest.raises(HumGenException):
        p.convert_to_haircards("low", bpy.context)

    p.convert_to_game_eyes("medium")
    assert p.has_game_eyes
    p.lod.set_teeth_lod(1, context=bpy.context)

    images = p.bake_textures(textures, str(tmp_path / "tex"), settings.output, context=bpy.context)
    assert images and p.was_baked
    files = files_in(str(tmp_path / "tex"))
    assert len(files) == len(images)
    assert all(image.size[0] == TEST_RESOLUTION for image in images)
    name = copy.name.split(".")[0]
    assert f"{name}_Skin_BaseColor.png" in files
    with pytest.raises(HumGenException):
        p.bake_textures(textures, context=bpy.context)

    body_verts = len(copy.objects.body.data.vertices)
    clothing_tris = sum(tris(obj) for obj in copy.clothing.outfit.objects)
    p.set_quality(QualitySettings.from_tier("medium"), settings.meshes, context=bpy.context)
    assert p.is_lod
    assert len(copy.objects.body.data.vertices) < body_verts
    assert sum(tris(obj) for obj in copy.clothing.outfit.objects) < clothing_tris / 2
    assert not [mod for mod in copy.objects.body.modifiers if mod.type == "MASK"], "Hidden skin removed"

    p.convert_to_game_rig(settings=settings.skeleton, max_influences=4, context=bpy.context)
    assert p.has_t_pose_rest and p.has_game_rig
    rig = copy.objects.rig
    assert "Hips" in rig.data.bones and "Root" in rig.data.bones
    assert arm_angle(rig, "LeftUpperArm", "LeftLowerArm") < 10
    for obj in copy.objects:
        if obj.type == "MESH":
            assert bone_influences(obj, rig) <= 4, obj.name
    with pytest.raises(HumGenException):
        p.set_t_pose_as_rest(bpy.context)
    with pytest.raises(HumGenException):
        p.convert_to_game_rig(settings=settings.skeleton, context=bpy.context)

    p.apply_names(settings.output)
    assert rig.name == name
    assert copy.objects.body.name == f"{name}_Body"
    assert copy.objects.body.material_slots[0].material.name == f"{name}_Skin"

    clips = p.prepare_clips(AnimationSettings(enabled=True), source=source, context=bpy.context)
    assert len(clips) == len(source.animation.actions)
    strips = [strip.action for track in rig.animation_data.nla_tracks for strip in track.strips]
    assert set(strips) == set(clips)
    for clip in clips:
        assert 'pose.bones["Hips"].rotation_quaternion' in action_paths(clip), "Retargeted"
        assert clip not in source.animation.actions

    path = copy.export.write(str(tmp_path / "out" / "Character"), settings.output, "meters", "strips", context=bpy.context)
    assert path.endswith("Character.fbx") and os.path.isfile(path)
    with imported(path) as data:
        assert len(data.armatures) == 1
        assert len(data.actions) >= len(clips)
        assert {obj.name for obj in data.meshes} >= {f"{name}_Body", f"{name}_Eyes"}


def test_lod_levels_share_textures(source, tmp_path):
    settings = ExportSettings.from_recipe("unreal")
    textures = _textures(settings)
    first, second = source.duplicate(bpy.context), source.duplicate(bpy.context)
    try:
        for level, (human, quality) in enumerate(((first, "high"), (second, "low"))):
            p = human.process
            p.set_shape_keys(settings.shape_keys, level=level, context=bpy.context)
            p.convert_to_haircards(QualitySettings.from_tier(quality).haircards, bpy.context)
            p.convert_to_game_eyes(QualitySettings.from_tier(quality).eyes)
            if level:
                p.share_textures(first)
            p.bake_textures(
                textures,
                str(tmp_path),
                settings.output,
                level=level,
                levels=2,
                only_sets=("eyes", "hair") if level else None,
                context=bpy.context,
            )
            p.set_quality(QualitySettings.from_tier(quality), settings.meshes, context=bpy.context)
            p.convert_to_game_rig(settings=settings.skeleton, context=bpy.context)
            p.apply_names(settings.output, level=level, levels=2)

        name = first.objects.rig.name[len("SK_"):]
        assert second.objects.body.material_slots[0].material == first.objects.body.material_slots[0].material
        assert first.objects.body.material_slots[0].material.name == f"M_{name}_Skin"
        assert second.objects.eyes.material_slots[0].material.name == f"M_{name}_Eyes_LOD1"
        assert second.objects.body.name == f"SK_{name}_Body_LOD1"
        files = files_in(str(tmp_path))
        assert f"T_{name}_Eyes_BC_LOD1.png" in files
        assert not [file for file in files if "Skin" in file and "LOD1" in file]

        first.process.merge_levels([second])
        rigs = [obj for obj in bpy.data.objects if obj.type == "ARMATURE" and obj.name.startswith("SK_")]
        assert rigs == [first.objects.rig], "The rig of the second level is removed"
        children = {obj.name for obj in first.objects.rig.children}
        assert f"SK_{name}_Body_LOD0" in children and f"SK_{name}_Body_LOD1" in children
        for obj in first.objects.rig.children:
            for mod in obj.modifiers:
                if mod.type == "ARMATURE":
                    assert mod.object == first.objects.rig
    finally:
        for human in (first, second):
            try:
                rig = human.objects.rig
            except ReferenceError:
                continue
            if rig and rig.name in bpy.data.objects:
                human.delete()
        for obj in [obj for obj in bpy.data.objects if obj.name.startswith("SK_")]:
            bpy.data.objects.remove(obj)


# Single steps with plain arguments


def test_game_rig_presets(copy):
    with pytest.raises(ValueError):
        copy.process.convert_to_game_rig(preset="no_such_engine", context=bpy.context)
    assert not copy.process.has_game_rig
    copy.process.convert_to_game_rig(preset="humgen", context=bpy.context)
    assert copy.process.game_rig_preset == "generic_a"
    assert "spine" in copy.objects.rig.data.bones
    assert not copy.process.has_t_pose_rest


def test_game_rig_custom_names(copy, tmp_path):
    path = tmp_path / "names.json"
    path.write_text(json.dumps({"names": {"spine": "Pelvis", "upper_arm": "Arm_{side}"}}))
    skeleton = SkeletonSettings(names="custom", names_file=str(path), rest_pose="a_pose", root_bone_name="Origin")
    copy.process.convert_to_game_rig(settings=skeleton, context=bpy.context)
    bones = copy.objects.rig.data.bones
    assert "Pelvis" in bones and "Arm_l" in bones and "Origin" in bones
    assert bones["Pelvis"].parent.name == "Origin"


def test_game_rig_keep_options(copy):
    skeleton = SkeletonSettings(names="unreal", rest_pose="a_pose", keep_eyes=False, keep_jaw=False, keep_breasts=False, keep_metacarpals=True, root_bone=False)
    copy.process.convert_to_game_rig(settings=skeleton, context=bpy.context)
    bones = copy.objects.rig.data.bones
    assert "eye_l" not in bones and "jaw" not in bones and "breast_l" not in bones
    assert "index_metacarpal_l" in bones
    assert "root" not in bones and bones["pelvis"].parent is None


def test_clothing_quality(copy):
    with pytest.raises(ValueError):
        copy.process.lod.set_clothing_lod("tiny", context=bpy.context)
    before = {obj.name: tris(obj) for obj in copy.clothing.outfit.objects}
    copy.process.lod.set_clothing_lod("low", context=bpy.context)
    for obj in copy.clothing.outfit.objects:
        assert tris(obj) < before[obj.name] / 4


def test_remove_hidden_skin(copy):
    verts = len(copy.objects.body.data.vertices)
    keys = len(copy.objects.body.data.shape_keys.key_blocks)
    removed = copy.process.remove_hidden_skin(bpy.context)
    assert removed > 0
    assert len(copy.objects.body.data.vertices) == verts - removed
    assert len(copy.objects.body.data.shape_keys.key_blocks) == keys, "The keys are carried along"


def test_apply_modifiers_keeps_shape_keys(copy):
    obj = copy.clothing.outfit.objects[0]
    mod = obj.modifiers.new("Test subdivision", "SUBSURF")
    mod.levels = 1
    keys = len(obj.data.shape_keys.key_blocks)
    verts = len(obj.data.vertices)
    copy.process.apply_modifiers(["SUBSURF"], objects=[obj], context=bpy.context)
    assert "Test subdivision" not in obj.modifiers
    assert len(obj.data.vertices) > verts
    assert len(obj.data.shape_keys.key_blocks) == keys


def test_apply_names_schemes(copy):
    copy.process.apply_names(OutputSettings(naming="unreal", name="{name}_Hero"))
    name = copy.objects.rig.name
    assert name.startswith("SK_") and name.endswith("_Hero")
    base = name[len("SK_"):]
    assert copy.objects.body.name == f"SK_{base}_Body"
    assert copy.objects.body.data.name == f"SK_{base}_Body"
    teeth = {copy.objects.upper_teeth.material_slots[0].material, copy.objects.lower_teeth.material_slots[0].material}
    assert {material.name for material in teeth} == {f"M_{base}_Teeth"}
    eyes = [slot.material.name for slot in copy.objects.eyes.material_slots]
    assert eyes == [f"M_{base}_EyesOuter", f"M_{base}_EyesInner"]
    # Twice is fine, the names stay
    copy.process.apply_names(OutputSettings(naming="unreal", name="{name}_Hero"))
    assert copy.objects.rig.name == name


def test_export_write_refuses_in_file(copy, tmp_path):
    with pytest.raises(ValueError):
        copy.export.write(str(tmp_path / "x"), OutputSettings(format="in_file"), context=bpy.context)


def test_mark_as_processed(copy, source):
    copy.process.mark_as_processed(source)
    rig = copy.objects.rig
    assert copy.process.is_processed
    assert rig[ORIGINAL_ID_KEY] == source.objects.rig[HUMAN_ID_KEY]
    assert HUMAN_ID_KEY not in rig
    assert not copy.process.settings, "No settings stored by marking alone"


def test_baking_compatibility_layer(copy):
    """The baking API of earlier versions still exists."""
    assert copy.process.baking is not None
