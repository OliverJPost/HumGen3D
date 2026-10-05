import contextlib
import os

import bpy
import numpy as np
import pytest
from HumGen3D.backend import get_prefs
from HumGen3D.tests.test_fixtures import *

SAVED_HAIR_NAME = "Pytest hair"
SAVED_HAIR_CATEGORY = "Pytest"
# Hair is refitted per face of the body, which shifts the strands a little
SAVED_HAIR_TOLERANCE = 0.02


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
def test_hair(human, context):
    hash_before = hash(human.hair)
    chosen_hair = human.hair.regular_hair.get_options(context)[3]

    human.hair.regular_hair.set(chosen_hair, context)

    assert (
        hash(human.hair) != hash_before
    ), f"Hash is the same after setting {chosen_hair=}"


@pytest.fixture
def temp_library(tmp_path, monkeypatch):
    """Empty content library to save to, without touching the real one."""
    os.symlink(
        os.path.join(get_prefs().filepath, "content_packs"),
        tmp_path / "content_packs",
    )
    # The saved file is purged by a separate Blender process, it has to be usable
    # without that
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: None)
    return tmp_path


@contextlib.contextmanager
def _use_library(path):
    pref = get_prefs()
    original_path = pref.filepath
    pref.filepath = str(path) + os.sep
    try:
        yield
    finally:
        pref.filepath = original_path


def _hair_key_coords(human, context):
    particle_systems = human.hair.regular_hair.get_evaluated_particle_systems(context)
    return np.array(
        [
            key.co
            for ps in particle_systems
            for particle in ps.particles
            for key in particle.hair_keys
        ]
    )


def test_save_hair_and_load_on_other_body(male_human, context, temp_library):
    human = male_human
    regular_hair = human.hair.regular_hair
    body = human.objects.body
    stock_hair = regular_hair.get_options(context)[3]

    human.keys["Big Head"].value = 0.8
    regular_hair.set(stock_hair, context)
    body_name = body.name
    object_count = len(bpy.data.objects)
    driver_count = len(body.data.shape_keys.animation_data.drivers)

    with _use_library(temp_library):
        regular_hair.save_to_library(
            [ps.name for ps in regular_hair.particle_systems],
            SAVED_HAIR_NAME,
            SAVED_HAIR_CATEGORY,
            for_female=False,
            context=context,
        )

    assert body.name == body_name
    assert len(bpy.data.objects) == object_count
    assert len(body.data.shape_keys.animation_data.drivers) == driver_count

    blend_path = temp_library / "hair" / "head" / f"{SAVED_HAIR_NAME}.blend"
    with bpy.data.libraries.load(str(blend_path)) as (data_from, _):
        # Nothing of the human the hair was saved from should be in the file
        assert data_from.objects == ["HG_Body"]
        assert not data_from.armatures

    human.keys["Big Head"].value = -0.5
    regular_hair.set(stock_hair, context)
    expected_coords = _hair_key_coords(human, context)

    with _use_library(temp_library):
        regular_hair.set(
            f"hair/head/male/{SAVED_HAIR_CATEGORY}/{SAVED_HAIR_NAME}.json", context
        )

    assert len(bpy.data.objects) == object_count
    coords = _hair_key_coords(human, context)
    assert coords.shape == expected_coords.shape
    offsets = np.linalg.norm(coords - expected_coords, axis=1)
    assert offsets.max() < SAVED_HAIR_TOLERANCE


def test_save_face_hair(male_human, context, temp_library):
    face_hair = male_human.hair.face_hair
    face_hair.set(face_hair.get_options(context)[0], context)

    with _use_library(temp_library):
        face_hair.save_to_library(
            [ps.name for ps in face_hair.particle_systems],
            SAVED_HAIR_NAME,
            SAVED_HAIR_CATEGORY,
            context=context,
        )

    folder = temp_library / "hair" / "face_hair"
    assert (folder / f"{SAVED_HAIR_NAME}.blend").is_file()
    assert (folder / SAVED_HAIR_CATEGORY / f"{SAVED_HAIR_NAME}.json").is_file()
