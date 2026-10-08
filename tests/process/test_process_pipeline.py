# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811

"""`human.process.run` from the API, per recipe and output format.

Every run is made once per module and checked by several tests. The written
files are read back: FBX, glTF, OBJ and Alembic are imported again and glb and
glTF also read with pygltflib, so the checks see what an engine gets. The
source human is compared before and after every run and the datablocks are
counted to find leftovers.

The textures are baked at 128 px, which keeps a run at half a minute.
"""

import glob
import json
import os
import tempfile
from types import SimpleNamespace

import bpy
import numpy as np
import pytest
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.object_finding import find_original_rig
from HumGen3D.human.human import Human
from HumGen3D.human.process.operators import process_with_settings
from HumGen3D.human.process.pipeline import (
    LEVEL_KEY,
    RESULT_SPACING,
    RESULTS_COLLECTION,
    TEXTURES_FOLDER,
)
from HumGen3D.human.process.settings import QualitySettings, ScriptSettings, ScriptsSettings
from HumGen3D.human.process.shape_keys import facs_key_names
from HumGen3D.tests.process.process_helpers import *
from HumGen3D.tests.test_fixtures import *

SHIPPED_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "scripts",
    "preset_scripts",
    "write_export_info.py",
)
# Parts every processed character has, besides its clothing
PARTS = ("Body", "Eyes", "TeethUpper", "TeethLower", "Eyebrows", "Eyelashes", "Hair", "FaceHair")


@pytest.fixture(scope="module")
def source():
    human = make_source_human("male")
    yield human
    human.delete()


def _run(source, settings, **kwargs):
    """Runs the settings on the source, with everything the tests compare."""
    before = snapshot(source)
    counts = datablock_counts()
    progress = []
    result = source.process.run(settings, bpy.context, progress=progress.append, **kwargs)
    return SimpleNamespace(
        settings=settings,
        result=result,
        name=result.name,
        folder=settings.output.folder,
        before=before,
        after=snapshot(source),
        counts_before=counts,
        counts_after=datablock_counts(),
        progress=progress,
    )


def _cleanup(run):
    for human in run.result.humans:
        human.delete()


@pytest.fixture(scope="module")
def unity_run(source, tmp_path_factory):
    folder = tmp_path_factory.mktemp("unity")
    settings = cheap_settings("unity", folder, **{"animations.enabled": True})
    settings.scripts = ScriptsSettings(
        enabled=True,
        items=[ScriptSettings(path=SHIPPED_SCRIPT, stage="after_export", args={"file_name": "info"})],
    )
    run = _run(source, settings)
    yield run
    _cleanup(run)


@pytest.fixture(scope="module")
def unreal_run(source, tmp_path_factory):
    folder = tmp_path_factory.mktemp("unreal")
    settings = cheap_settings(
        "unreal",
        folder,
        **{
            "animations.enabled": True,
            "lods": [QualitySettings.from_tier("high"), QualitySettings.from_tier("low")],
        },
    )
    run = _run(source, settings)
    yield run
    _cleanup(run)


@pytest.fixture(scope="module")
def godot_run(source, tmp_path_factory):
    folder = tmp_path_factory.mktemp("godot")
    run = _run(source, cheap_settings("godot", folder, **{"animations.enabled": True}))
    yield run
    _cleanup(run)


@pytest.fixture(scope="module")
def gltf_run(source, tmp_path_factory):
    folder = tmp_path_factory.mktemp("gltf")
    settings = cheap_settings(
        "generic",
        folder,
        **{
            "output.format": "gltf",
            "output.name": "{name}_Web",
            "output.naming": "custom",
            "output.naming_templates": {"rig": "Rig_{name}", "mesh": "{part}_{name}", "material": "Mat_{name}_{part}", "texture": "{part}-{pass}"},
            "textures.file_format": "jpeg",
        },
    )
    run = _run(source, settings)
    yield run
    _cleanup(run)


@pytest.fixture(scope="module")
def obj_run(source, tmp_path_factory):
    folder = tmp_path_factory.mktemp("obj")
    run = _run(source, cheap_settings("generic", folder, **{"output.format": "obj", "output.keep_copy": True}))
    yield run
    _cleanup(run)


@pytest.fixture(scope="module")
def abc_run(source, tmp_path_factory):
    folder = tmp_path_factory.mktemp("abc")
    run = _run(source, cheap_settings("generic", folder, **{"output.format": "abc"}))
    yield run
    _cleanup(run)


@pytest.fixture(scope="module")
def mixamo_embedded_run(source, tmp_path_factory):
    folder = tmp_path_factory.mktemp("mixamo")
    scratch_before = set(glob.glob(os.path.join(tempfile.gettempdir(), "hg_textures_*")))
    run = _run(source, cheap_settings("mixamo", folder, **{"output.textures": "embedded"}))
    run.scratch_left = set(glob.glob(os.path.join(tempfile.gettempdir(), "hg_textures_*"))) - scratch_before
    yield run
    _cleanup(run)


@pytest.fixture(scope="module")
def infile_unity_run(source):
    run = _run(source, cheap_settings("unity", None, **{"output.format": "in_file"}))
    yield run
    _cleanup(run)


@pytest.fixture(scope="module")
def infile_blender_run(source):
    run = _run(source, cheap_settings("blender"))
    yield run
    _cleanup(run)


FILE_RUNS = ["unity_run", "unreal_run", "godot_run", "gltf_run", "obj_run", "abc_run", "mixamo_embedded_run"]
IN_FILE_RUNS = ["infile_unity_run", "infile_blender_run"]
ALL_RUNS = FILE_RUNS + IN_FILE_RUNS


# What every run has to do


@pytest.mark.parametrize("run_name", ALL_RUNS)
def test_source_is_not_changed(request, run_name):
    run = request.getfixturevalue(run_name)
    assert run.after == run.before


@pytest.mark.parametrize("run_name", ALL_RUNS)
def test_progress(request, run_name):
    progress = request.getfixturevalue(run_name).progress
    assert len(progress) > 5
    assert progress == sorted(progress), "The progress never goes back"
    assert 0 < progress[0] < 0.2
    assert progress[-1] == 1.0


@pytest.mark.parametrize("run_name", ALL_RUNS)
def test_result(request, run_name):
    run = request.getfixturevalue(run_name)
    result = run.result
    assert result.seconds > 0
    assert len(result.triangles) == len(run.settings.lods)
    assert all(tris > 1000 for tris in result.triangles)
    assert not any("failed" in warning for warning in result.warnings)
    assert result.summary()
    if run.settings.output.is_file:
        assert result.files
        for path in result.files:
            assert os.path.isfile(path)
            assert os.path.dirname(path) == str(run.folder)
            assert os.path.getsize(path) > 10_000


@pytest.mark.parametrize("run_name", [name for name in FILE_RUNS if name != "obj_run"])
def test_file_export_leaves_nothing_behind(request, run_name):
    """The copies, their materials, images, clips and rigs are removed."""
    run = request.getfixturevalue(run_name)
    leftovers = {
        name: run.counts_after[name] - run.counts_before[name]
        for name in run.counts_before
        if run.counts_after[name] != run.counts_before[name]
    }
    assert not leftovers


@pytest.mark.parametrize("run_name", ["unity_run", "unreal_run", "mixamo_embedded_run", "godot_run", "gltf_run"])
def test_written_names_have_no_blender_suffix(request, run_name):
    """The file has the names of the scheme, without Blender's .001.

    The source human and the in-file results hold the same names while the
    files are written. glTF is read as it is, its importer adds suffixes of
    its own; FBX is imported, with the names of the scene moved aside.
    """
    run = request.getfixturevalue(run_name)
    path = run.result.files[0]
    humgen_bones = run.settings.skeleton.names == "humgen"
    if path.endswith((".glb", ".gltf")):
        gltf = gltf_document(path)
        names = [node.name for node in gltf.nodes if node.mesh is not None or node.skin is not None]
        names += [mesh.name for mesh in gltf.meshes] + [material.name for material in gltf.materials]
        names += [image.name or "" for image in gltf.images]
        names += [animation.name for animation in gltf.animations]
        if not humgen_bones:
            names += [gltf.nodes[index].name for skin in gltf.skins for index in skin.joints]
    else:
        with imported(path) as data:
            names = [block.name for block in data.objects + data.materials]
            names += [obj.data.name for obj in data.objects if obj.data]
            # The importer makes an image per texture slot, the files count
            names += [os.path.splitext(os.path.basename(image.filepath))[0] for image in data.images if image.filepath]
            if not humgen_bones:
                names += [bone.name for arm in data.armatures for bone in arm.data.bones]
    assert names
    assert not [name for name in names if SUFFIX.search(name)]


# Unity: FBX, humanoid T-pose skeleton, metallic-smoothness, clip per file


def _check_skeleton(armature, root, hips, upper_arm, forearm, t_pose):
    bones = armature.data.bones
    assert hips in bones
    if root:
        assert root in bones
        assert bones[hips].parent.name == root
        assert bones[root].parent is None
        head = armature.matrix_world @ bones[root].head_local
        assert head.length < 0.01, "The root bone is at the origin"
    else:
        assert bones[hips].parent is None
    angle = arm_angle(armature, upper_arm, forearm)
    if t_pose:
        assert angle < 10, f"The arms of a T-pose are horizontal, not {angle:.0f} degrees"
    else:
        assert angle > 20, f"The arms of the A-pose hang down, not {angle:.0f} degrees"
    # The face rig controls and helper bones are gone
    names = " ".join(bone.name.lower() for bone in bones)
    for control in ("facs", "lookat", "mch", "ik"):
        assert control not in names
    assert len(bones) < 80


def _check_meshes(data, name, armature, max_influences, suffix=""):
    meshes = {obj.name: obj for obj in data.meshes}
    for part in PARTS:
        assert f"{name}_{part}{suffix}" in meshes, f"No {part} in {sorted(meshes)}"
    for obj in meshes.values():
        assert obj.parent == armature
        modifiers = [mod for mod in obj.modifiers if mod.type == "ARMATURE"]
        assert modifiers and modifiers[0].object == armature
        if max_influences:
            assert bone_influences(obj, armature) <= max_influences, obj.name
    assert 1.5 < world_height([meshes[f"{name}_Body{suffix}"]]) < 2.1


def test_unity_files(unity_run, source):
    run, name = unity_run, unity_run.name
    folder = str(run.folder)
    clips = [action.name[len(source.name) + 1 :] for action in source.animation.actions]
    expected = {f"{name}.fbx", "info.json"} | {f"{name}@{clip}.fbx" for clip in clips}
    top = {path for path in files_in(folder) if os.sep not in path}
    assert top == expected
    assert sorted(run.result.files) == sorted(os.path.join(folder, f) for f in expected if f.endswith(".fbx"))
    assert fbx_unit_scale(os.path.join(folder, f"{name}.fbx")) == pytest.approx(1.0)


def test_unity_character(unity_run):
    run, name = unity_run, unity_run.name
    with imported(run.result.files[0]) as data:
        assert len(data.armatures) == 1
        armature = data.armatures[0]
        assert armature.name == name
        _check_skeleton(armature, "Root", "Hips", "LeftUpperArm", "LeftLowerArm", t_pose=True)
        for bone in ("LeftEye", "RightEye", "Jaw", "LeftBreast", "LeftHand", "RightToes"):
            assert bone in armature.data.bones
        assert not [bone for bone in armature.data.bones if "Metacarpal" in bone.name and "Thumb" not in bone.name]
        _check_meshes(data, name, armature, 4)

        body = bpy.data.objects[f"{name}_Body"]
        keys = [key.name for key in body.data.shape_keys.key_blocks]
        assert len(set(keys) & set(facs_key_names())) > 40, "The face rig is kept"
        assert any(key.startswith("cor_") for key in keys), "The correctives are kept"
        assert not any(key.startswith(("height_", "LIVE")) for key in keys)

        materials = {slot.material.name for obj in data.meshes for slot in obj.material_slots}
        for material in ("Skin", "Eyes", "Teeth", "Haircap", "HairCards", "FaceHair", "FaceHairCards"):
            assert f"{name}_{material}" in materials
        eyes = bpy.data.objects[f"{name}_Eyes"]
        assert len(eyes.material_slots) == 1, "Game eyes have one opaque material"
        upper, lower = (bpy.data.objects[f"{name}_Teeth{part}"] for part in ("Upper", "Lower"))
        assert upper.material_slots[0].material == lower.material_slots[0].material


def test_unity_textures(unity_run):
    run, name = unity_run, unity_run.name
    textures = os.path.join(str(run.folder), TEXTURES_FOLDER)
    files = files_in(textures)
    for file in (f"{name}_Skin_BaseColor.png", f"{name}_Skin_Normal.png", f"{name}_Haircap_BaseColor.png", f"{name}_FaceHair_BaseColor.png"):
        assert file in files
    assert all(file.startswith(name + "_") and file.endswith(".png") for file in files)
    assert not [file for file in files if file.endswith(("_Roughness.png", "_Metallic.png"))], "Packed"
    packed = [file for file in files if file.endswith("_MetallicSmoothness.png")]
    assert packed, "Some material has a roughness map"
    for file in packed:
        pixels = image_pixels(os.path.join(textures, file))
        assert np.allclose(pixels[:, 0], pixels[:, 1], atol=1 / 255)
        assert np.allclose(pixels[:, 0], pixels[:, 2], atol=1 / 255)
        assert pixels[:, 3].std() > 0 or pixels[:, 3].mean() < 1, "Smoothness in alpha"

    cards = image_pixels(os.path.join(textures, f"{name}_HairCards_BaseColor.png"))
    assert len(cards) == TEST_RESOLUTION**2
    assert (cards[:, 3] < 0.5).mean() > 0.2, "The transparency of the cards is in the alpha"

    # Every image of the file is one of these files
    with imported(run.result.files[0]) as data:
        assert data.images
        for image in data.images:
            path = bpy.path.abspath(image.filepath)
            assert os.path.isfile(path), path
            assert os.path.dirname(os.path.normpath(path)) == textures


def test_unity_clips(unity_run):
    run, name = unity_run, unity_run.name
    clip_files = [path for path in run.result.files if "@" in path]
    assert len(clip_files) == 2
    for path in clip_files:
        with imported(path) as data:
            assert not data.meshes
            assert len(data.armatures) == 1
            assert "Hips" in data.armatures[0].data.bones
            assert data.actions
            paths = set().union(*(action_paths(action) for action in data.actions))
            assert 'pose.bones["Hips"].rotation_quaternion' in paths
            assert 'pose.bones["LeftUpperArm"].rotation_quaternion' in paths


def test_unity_script(unity_run):
    run, name = unity_run, unity_run.name
    with open(os.path.join(str(run.folder), "info.json")) as f:
        info = json.load(f)
    assert info["name"] == name
    assert sorted(info["files"]) == sorted(os.path.basename(path) for path in run.result.files)
    assert "Hips" in info["bones"]
    assert info["triangles"] == run.result.triangles[0]


def test_unity_warnings(unity_run):
    warnings = " ".join(unity_run.result.warnings)
    assert "driven by bones" in warnings, "Face rig and correctives are kept"


# Unreal: two LOD levels, Unreal names, ORM, centimeters, clips in one file


def test_unreal_files(unreal_run):
    run, name = unreal_run, unreal_run.name
    folder = str(run.folder)
    assert [os.path.basename(path) for path in run.result.files] == [f"{name}.fbx", f"{name}_Animations.fbx"]
    assert fbx_unit_scale(run.result.files[0]) == pytest.approx(100.0)
    assert fbx_unit_scale(run.result.files[1]) == pytest.approx(100.0)
    files = files_in(os.path.join(folder, TEXTURES_FOLDER))
    for file in (f"T_{name}_Skin_BC.png", f"T_{name}_Skin_N.png", f"T_{name}_Eyes_BC.png", f"T_{name}_Eyes_BC_LOD1.png"):
        assert file in files
    assert all(file.startswith(f"T_{name}_") for file in files)
    assert not [file for file in files if "Skin" in file and "LOD1" in file], "LOD1 shares the skin textures"
    for file in files:
        if "_ORM" in file:
            pixels = image_pixels(os.path.join(folder, TEXTURES_FOLDER, file))
            assert np.allclose(pixels[:, 0], 1.0), "No occlusion is baked, R is white"


def test_unreal_character(unreal_run):
    run, name = unreal_run, unreal_run.name
    with imported(run.result.files[0]) as data:
        assert len(data.armatures) == 1, "Both levels share one skeleton"
        armature = data.armatures[0]
        assert armature.name == f"SK_{name}"
        _check_skeleton(armature, "root", "pelvis", "upperarm_l", "lowerarm_l", t_pose=False)
        for level in (0, 1):
            _check_meshes(data, f"SK_{name}", armature, 4, f"_LOD{level}")
        assert all(obj.name.endswith(("_LOD0", "_LOD1")) for obj in data.meshes)
        lod0 = {obj.name[: -len("_LOD0")] for obj in data.meshes if obj.name.endswith("_LOD0")}
        lod1 = {obj.name[: -len("_LOD1")] for obj in data.meshes if obj.name.endswith("_LOD1")}
        assert lod0 == lod1

        body0, body1 = (bpy.data.objects[f"SK_{name}_Body_LOD{level}"] for level in (0, 1))
        assert tris(body1) < tris(body0) / 2
        keys = [key.name for key in body0.data.shape_keys.key_blocks]
        assert len(set(keys) & set(facs_key_names())) > 40
        assert not any(key.startswith("cor_") for key in keys), "The recipe removes the correctives"
        for obj in data.meshes:
            if obj.name.endswith("_LOD1"):
                assert not obj.data.shape_keys or len(obj.data.shape_keys.key_blocks) <= 1, obj.name

        assert body0.material_slots[0].material == body1.material_slots[0].material
        assert body0.material_slots[0].material.name == f"M_{name}_Skin"
        eyes0, eyes1 = (bpy.data.objects[f"SK_{name}_Eyes_LOD{level}"] for level in (0, 1))
        assert eyes0.material_slots[0].material.name == f"M_{name}_Eyes"
        assert eyes1.material_slots[0].material.name == f"M_{name}_Eyes_LOD1"


def test_unreal_triangles(unreal_run):
    high, low = unreal_run.result.triangles
    assert low < high / 2
    summary = unreal_run.result.summary()
    assert "LOD0" in summary and "LOD1" in summary


def test_unreal_clips(unreal_run, source):
    with imported(unreal_run.result.files[1]) as data:
        assert not data.meshes
        assert len(data.armatures) == 1
        assert "pelvis" in data.armatures[0].data.bones
        assert len(data.actions) >= len(source.animation.actions)


# Godot: glb with embedded textures, metallic-roughness, clips in the file


def test_godot_file(godot_run, source):
    run, name = godot_run, godot_run.name
    assert [os.path.basename(path) for path in run.result.files] == [f"{name}.glb"]
    assert files_in(str(run.folder)) == [f"{name}.glb"], "The textures are inside"
    gltf = gltf_document(run.result.files[0])
    assert "Human Generator" in gltf.asset.copyright
    assert gltf.images and all(image.bufferView is not None and not image.uri for image in gltf.images)
    assert len(gltf.skins) == 1
    joints = {gltf.nodes[index].name for index in gltf.skins[0].joints}
    assert {"Hips", "LeftUpperArm", "LeftEye", "Jaw"} <= joints
    nodes = {node.name for node in gltf.nodes}
    assert {"Root", name} <= nodes
    for part in PARTS:
        assert f"{name}_{part}" in nodes

    materials = {material.name: material for material in gltf.materials}
    skin = materials[f"{name}_Skin"]
    assert skin.pbrMetallicRoughness.baseColorTexture is not None
    assert skin.normalTexture is not None
    cards = materials[f"{name}_HairCards"]
    assert cards.alphaMode in ("BLEND", "MASK")
    assert any(
        material.pbrMetallicRoughness.metallicRoughnessTexture is not None for material in gltf.materials
    ), "Roughness and metallic packed in one texture"

    body = next(mesh for mesh in gltf.meshes if mesh.name == f"{name}_Body")
    target_names = body.extras["targetNames"]
    assert len(set(target_names) & set(facs_key_names())) > 40
    clips = sorted(animation.name for animation in gltf.animations)
    assert clips == sorted(action.name for action in source.animation.actions), "The clips are in the file"


def test_godot_reimport(godot_run):
    run, name = godot_run, godot_run.name
    with imported(run.result.files[0]) as data:
        assert len(data.armatures) == 1
        armature = data.armatures[0]
        _check_skeleton(armature, "Root", "Hips", "LeftUpperArm", "LeftLowerArm", t_pose=True)
        body = next(obj for obj in data.meshes if obj.name.startswith(f"{name}_Body"))
        assert 1.5 < world_height([body]) < 2.1


# glTF with separate files, JPEG and custom names


def test_gltf_files(gltf_run):
    run, name = gltf_run, gltf_run.name
    assert name.endswith("_Web")
    folder = str(run.folder)
    path = run.result.files[0]
    assert os.path.basename(path) == f"{name}.gltf"
    gltf = gltf_document(path)
    assert gltf.images
    for image in gltf.images:
        assert image.uri, "Separate files"
        assert os.path.isfile(os.path.join(folder, image.uri))
    textures = files_in(os.path.join(folder, TEXTURES_FOLDER))
    assert textures and all(file.endswith(".jpg") for file in textures)
    assert "Skin-BaseColor.jpg" in textures, "The texture template"
    for buffer in gltf.buffers:
        assert os.path.isfile(os.path.join(folder, buffer.uri))
    nodes = {node.name for node in gltf.nodes}
    assert f"Body_{name}" in nodes, "The mesh template"
    assert f"Rig_{name}" in nodes, "The rig template"
    assert f"Mat_{name}_Skin" in {material.name for material in gltf.materials}
    assert any("JPEG" in warning for warning in run.result.warnings)


def test_gltf_generic_skeleton(gltf_run):
    """The generic recipe keeps the Human Generator names in the A-pose."""
    with imported(gltf_run.result.files[0]) as data:
        armature = data.armatures[0]
        _check_skeleton(armature, "root", "spine", "upper_arm.L", "forearm.L", t_pose=False)


# OBJ and Alembic, meshes only


def test_obj(obj_run):
    run, name = obj_run, obj_run.name
    folder = str(run.folder)
    path = run.result.files[0]
    assert os.path.isfile(os.path.splitext(path)[0] + ".mtl")
    with open(path) as f:
        objects = [line.split(" ", 1)[1].strip() for line in f if line.startswith("o ")]
    assert objects
    assert all(obj.startswith(name + "_") for obj in objects), objects
    for part in PARTS:
        assert f"{name}_{part}" in objects
    assert any("OBJ carries no skeleton" in warning for warning in run.result.warnings)
    with open(os.path.splitext(path)[0] + ".mtl") as f:
        # Options like "-bm 1.0" come before the path
        maps = [line.split()[-1] for line in f if line.startswith("map_")]
    assert maps
    for texture in maps:
        assert os.path.isfile(os.path.join(folder, texture)), texture


def test_obj_keep_copy(obj_run):
    """With keep_copy the processed human stays in the file next to the file."""
    run = obj_run
    assert len(run.result.humans) == 1
    copy = run.result.humans[0]
    assert copy.process.is_processed
    assert copy.name == run.name


def test_abc(abc_run):
    run, name = abc_run, abc_run.name
    assert os.path.basename(run.result.files[0]) == f"{name}.abc"
    with imported(run.result.files[0]) as data:
        assert len(data.meshes) >= len(PARTS)
        assert any(obj.name.startswith(f"{name}_Body") for obj in data.objects)


# Mixamo with the textures inside the FBX


def test_mixamo_embedded(mixamo_embedded_run):
    run, name = mixamo_embedded_run, mixamo_embedded_run.name
    folder = str(run.folder)
    assert files_in(folder) == [f"{name}.fbx"], "No texture files next to it"
    assert not run.scratch_left, "The scratch folder of the textures is removed"
    with open(run.result.files[0], "rb") as f:
        assert f.read().count(b"\x89PNG") >= 8, "The images are in the file"
    with imported(run.result.files[0]) as data:
        armature = data.armatures[0]
        _check_skeleton(armature, None, "mixamorig:Hips", "mixamorig:LeftArm", "mixamorig:LeftForeArm", t_pose=True)
        assert all(image.packed_file or os.path.isfile(bpy.path.abspath(image.filepath)) for image in data.images)


# In the file


def test_infile_unity(infile_unity_run, source):
    run = infile_unity_run
    assert not run.result.files
    assert len(run.result.humans) == 1
    copy = run.result.humans[0]
    rig = copy.objects.rig
    assert copy.process.is_processed
    assert find_original_rig(rig, bpy.context.view_layer.objects) == source.objects.rig
    assert rig[LEVEL_KEY] == 0
    assert copy.process.settings.to_dict() == run.result.settings.to_dict()
    assert copy.location[1] == pytest.approx(source.location[1] + RESULT_SPACING)
    assert all(obj.name in bpy.data.collections[RESULTS_COLLECTION].objects for obj in copy.objects)

    assert copy.process.has_game_rig and copy.process.has_t_pose_rest
    assert copy.process.has_haircards and copy.process.was_baked and copy.process.has_game_eyes
    assert not copy.hair.modifiers, "No particle hair left"
    assert "Hips" in rig.data.bones
    # The baked images live in the blend file, nothing is written
    images = {node.image for obj in copy.objects if obj.type == "MESH" for slot in obj.material_slots if slot.material for node in slot.material.node_tree.nodes if getattr(node, "image", None)}
    assert images and all(image.packed_file for image in images)
    assert all(image.size[0] == TEST_RESOLUTION for image in images)
    # Nothing is shared with the source
    source_materials = {slot.material for obj in source.objects if obj.type == "MESH" for slot in obj.material_slots}
    copy_materials = {slot.material for obj in copy.objects if obj.type == "MESH" for slot in obj.material_slots}
    assert not source_materials & copy_materials
    # A processed human can't be processed again
    with pytest.raises(HumGenException, match="processed human"):
        copy.process.run(run.settings, bpy.context)


def test_infile_unity_directx_normals(infile_unity_run):
    """Unity wants DirectX normal maps, the material flips them back for Blender."""
    copy = infile_unity_run.result.humans[0]
    skin = copy.objects.body.material_slots[0].material
    nodes = skin.node_tree.nodes
    assert any(node.bl_idname == "ShaderNodeSeparateColor" for node in nodes)
    normal_map = next(node for node in nodes if node.bl_idname == "ShaderNodeNormalMap")
    assert normal_map.inputs["Color"].links[0].from_node.bl_idname == "ShaderNodeCombineColor"


def test_infile_blender(infile_blender_run, source):
    """The render copy keeps everything as it is, except the editability."""
    copy = infile_blender_run.result.humans[0]
    assert copy.process.is_processed
    assert not copy.process.has_game_rig and not copy.process.was_baked
    assert not copy.process.has_haircards
    assert len(copy.hair.modifiers) == len(source.hair.modifiers)
    assert len(copy.objects.rig.data.bones) == len(source.objects.rig.data.bones)
    assert len(copy.objects.eyes.material_slots) == 2, "The layered eyes"
    body = copy.objects.body
    assert len(body.data.vertices) == len(source.objects.body.data.vertices)
    keys = [key.name for key in body.data.shape_keys.key_blocks]
    assert any(key.startswith("cor_") for key in keys)
    assert copy.objects.body.material_slots[0].material != source.objects.body.material_slots[0].material


# Further settings, run on their own


def test_two_humans_next_to_file(source, tmp_path):
    """process_with_settings, a female human and the textures next to the files."""
    female = make_source_human("female", outfit=False, clips=0)
    try:
        settings = cheap_settings("generic", tmp_path, **{"output.textures": "next_to_file"})
        results = process_with_settings([source, female], settings, bpy.context)
        male_name, female_name = source.name, female.name
        assert [result.name for result in results] == [male_name, female_name]
        files = files_in(str(tmp_path))
        assert f"{male_name}.fbx" in files and f"{female_name}.fbx" in files
        assert f"{female_name}_Skin_BaseColor.png" in files
        assert not os.path.isdir(os.path.join(str(tmp_path), TEXTURES_FOLDER))
        with imported(results[1].files[0]) as data:
            names = {obj.name for obj in data.meshes}
            assert f"{female_name}_Body" in names
            assert not [name for name in names if "FaceHair" in name]
    finally:
        female.delete()


def test_options_turned_off(source):
    settings = cheap_settings(
        "unity",
        None,
        **{
            "output.format": "in_file",
            "textures.enabled": False,
            "haircards.enabled": False,
            "skeleton.enabled": False,
            "shape_keys.enabled": False,
            "meshes.enabled": False,
        },
    )
    copy = source.process.run(settings, bpy.context).humans[0]
    try:
        keys = copy.objects.body.data.shape_keys
        assert not keys or [key.name for key in keys.key_blocks] == ["Basis"], "No shape keys kept"
        assert len(copy.objects.eyes.material_slots) == 2, "Meshes as they are"
        assert len(copy.objects.rig.data.bones) == len(source.objects.rig.data.bones)
        assert len(copy.hair.modifiers) == len(source.hair.modifiers)
        assert not copy.process.was_baked
        assert len(copy.objects.body.data.vertices) == len(source.objects.body.data.vertices), "No skin removed"
        assert sorted(len(obj.data.vertices) for obj in copy.clothing.outfit.objects) == sorted(
            len(obj.data.vertices) for obj in source.clothing.outfit.objects
        )
        assert sorted(mod.type for obj in copy.clothing.outfit.objects for mod in obj.modifiers) == sorted(
            mod.type for obj in source.clothing.outfit.objects for mod in obj.modifiers
        ), "The clothing keeps its modifiers"
    finally:
        copy.delete()


def test_haircap_only_and_bones_per_vertex(source):
    settings = cheap_settings("unity", None, **{"output.format": "in_file", "textures.enabled": False, "lods": [QualitySettings.from_tier("mobile")]})
    copy = source.process.run(settings, bpy.context).humans[0]
    try:
        rig = copy.objects.rig
        for obj in copy.objects:
            if obj.type == "MESH":
                assert bone_influences(obj, rig) <= 2, obj.name
        hair = [obj for obj in copy.objects.haircards]
        assert hair and all(len(obj.material_slots) == 1 for obj in hair), "Only the cap, no cards"
    finally:
        copy.delete()


# Scripts at every stage

STAGE_SCRIPT = '''"""Writes where it ran to a log."""
import json

def main(context, human, log: str = "", stage: str = "", files: list = None):
    rig = human.objects.rig
    entry = {
        "stage": stage,
        "level": rig.get("hg_export_level"),
        "processed": "hg_processed" in rig,
        "game_rig": "game_rig" in rig,
        "baked": "hg_baked" in rig,
        "keys": len(human.objects.body.data.shape_keys.key_blocks) if human.objects.body.data.shape_keys else 0,
        "rig": rig.name,
        "files": files,
    }
    with open(log, "a") as f:
        f.write(json.dumps(entry) + "\\n")
'''


def test_scripts_at_every_stage(source, tmp_path):
    from HumGen3D.human.process.settings import SCRIPT_STAGES

    script = write_script(tmp_path, "stage_logger", STAGE_SCRIPT)
    log = str(tmp_path / "log.jsonl")
    settings = cheap_settings(
        "unity",
        tmp_path / "out",
        **{
            "haircards.enabled": False,
            "textures.passes": {key: ["base_color"] for key in ("body", "clothing", "eyes", "teeth", "hair")},
            "lods": [QualitySettings.from_tier("high"), QualitySettings.from_tier("low")],
        },
    )
    settings.scripts = ScriptsSettings(
        enabled=True,
        items=[ScriptSettings(path=script, stage=stage, args={"log": log, "stage": stage}) for stage, *_ in reversed(SCRIPT_STAGES)],
    )
    result = source.process.run(settings, bpy.context)
    with open(log) as f:
        entries = [json.loads(line) for line in f]
    stages = [entry["stage"] for entry in entries]
    per_level = [stage for stage, *_ in SCRIPT_STAGES[:6]]
    assert stages == per_level + per_level + ["before_export", "after_export"]
    assert [entry["level"] for entry in entries[:12]] == [0] * 6 + [1] * 6
    by_stage = {(entry["stage"], entry["level"]): entry for entry in entries}
    # Each stage sees the copy in the state its description promises
    assert not by_stage["before_baking", 0]["baked"]
    assert by_stage["before_meshes", 0]["baked"]
    assert not by_stage["before_skeleton", 0]["game_rig"]
    assert by_stage["after_processing", 0]["game_rig"]
    # A suffix while the in-file results of the module have the name
    assert SUFFIX.sub("", by_stage["after_processing", 0]["rig"]) == result.name
    assert by_stage["start", 1]["keys"] > by_stage["after_processing", 1]["keys"], "LOD1 loses its keys"
    assert not any(entry["processed"] for entry in entries), "Never the original or a finished result"
    assert entries[-1]["files"] == result.files
    assert entries[-2]["files"] == [], "A script before the export gets no files"


def test_scripts_turned_off(source, tmp_path):
    script = write_script(tmp_path, "boom", "def main(context, human):\n    raise RuntimeError('ran')\n")
    settings = cheap_settings("blender")
    settings.scripts = ScriptsSettings(enabled=False, items=[ScriptSettings(path=script, stage="start")])
    copy = source.process.run(settings, bpy.context).humans[0]
    copy.delete()


def test_failing_script_stops(source, tmp_path):
    script = write_script(tmp_path, "boom", "def main(context, human):\n    raise RuntimeError('boom')\n")
    settings = cheap_settings("blender")
    settings.scripts = ScriptsSettings(enabled=True, items=[ScriptSettings(path=script, stage="before_skeleton")])
    before = set(bpy.data.objects)
    original = snapshot(source)
    with pytest.raises(HumGenException, match="boom"):
        source.process.run(settings, bpy.context)
    assert set(bpy.data.objects) == before
    assert snapshot(source) == original


def test_failing_script_skipped(source, tmp_path):
    script = write_script(tmp_path, "boom", "def main(context, human):\n    raise RuntimeError('boom')\n")
    settings = cheap_settings("blender")
    settings.scripts = ScriptsSettings(enabled=True, items=[ScriptSettings(path=script, stage="start", on_error="skip")])
    result = source.process.run(settings, bpy.context)
    try:
        assert len(result.humans) == 1
        assert any("boom.py failed" in warning for warning in result.warnings)
    finally:
        result.humans[0].delete()


# Refusals, failures and cancelling


def test_preflight_errors(source, tmp_path):
    settings = cheap_settings("unity", tmp_path / "out", **{"skeleton.names": "custom", "skeleton.names_file": str(tmp_path / "none.json")})
    settings.scripts = ScriptsSettings(enabled=True, items=[ScriptSettings(path=str(tmp_path / "gone.py"))])
    check = source.process.preflight(settings, bpy.context)
    assert not check.ok
    assert any("bone names file" in error for error in check.errors)
    assert any("Script not found" in error for error in check.errors)
    before = set(bpy.data.objects)
    with pytest.raises(HumGenException):
        source.process.run(settings, bpy.context)
    assert set(bpy.data.objects) == before
    assert not (tmp_path / "out").exists(), "Nothing is written before the checks pass"


def test_preflight_unwritable_folder(source):
    check = source.process.preflight(cheap_settings("unity", "/hg_no_such_root/sub"), bpy.context)
    assert any("Can't write" in error for error in check.errors)
    assert not os.path.exists("/hg_no_such_root")


def test_preflight_warnings(source):
    settings = cheap_settings("unity", tempfile.gettempdir(), **{"haircards.enabled": False, "textures.file_format": "jpeg", "animations.enabled": True, "animations.clips": []})
    warnings = " ".join(source.process.preflight(settings, bpy.context).warnings)
    assert "particle hair" in warnings
    assert "no clip is selected" in warnings
    settings = cheap_settings("unity", tempfile.gettempdir(), **{"meshes.enabled": False, "lods": [QualitySettings(), QualitySettings()]})
    warnings = " ".join(source.process.preflight(settings, bpy.context).warnings)
    assert "not game ready" in warnings
    assert "every LOD level has the original meshes" in warnings
    settings = cheap_settings("blender")
    settings.scripts = ScriptsSettings(enabled=True, items=[ScriptSettings(path=SHIPPED_SCRIPT, stage="after_export")])
    warnings = " ".join(source.process.preflight(settings, bpy.context).warnings)
    assert "runs at the export" in warnings


def test_failing_step_cleans_up(source, monkeypatch):
    from HumGen3D.human.process.process import ProcessSettings

    calls = []

    def fail(self, *args, **kwargs):
        calls.append(self)
        if len(calls) == 2:
            raise RuntimeError("Second level fails")

    monkeypatch.setattr(ProcessSettings, "convert_to_game_rig", fail)
    settings = cheap_settings("unity", None, **{"output.format": "in_file", "textures.enabled": False, "haircards.enabled": False, "lods": [QualitySettings(), QualitySettings.from_tier("low")]})
    before = set(bpy.data.objects)
    counts = datablock_counts()
    original = snapshot(source)
    with pytest.raises(RuntimeError, match="Second level fails"):
        source.process.run(settings, bpy.context)
    assert set(bpy.data.objects) == before, "Both the finished and the half made level are removed"
    assert datablock_counts()["armatures"] == counts["armatures"]
    assert snapshot(source) == original


@pytest.mark.parametrize("steps_before_closing", [1, 4, 8])
def test_cancel(source, steps_before_closing):
    """Esc in the interface closes the steps, which removes the copies."""
    settings = cheap_settings("unity", None, **{"output.format": "in_file", "textures.enabled": False, "lods": [QualitySettings(), QualitySettings.from_tier("low")]})
    before = set(bpy.data.objects)
    original = snapshot(source)
    steps = source.process.run_steps(settings, bpy.context)
    fractions = [next(steps) for _ in range(steps_before_closing)]
    assert fractions[-1] < 1
    assert set(bpy.data.objects) != before, "Work was done"
    steps.close()
    assert set(bpy.data.objects) == before
    assert snapshot(source) == original
