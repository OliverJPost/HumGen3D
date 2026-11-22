# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Saving a skin texture to the library, which once needed Pillow."""
import os

import bpy
import pytest

from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.tests.test_fixtures import *  # noqa: F401, F403


@pytest.fixture
def content_folder(tmp_path):
    """Point the content folder at a temporary one for the duration of a test."""
    prefs = get_prefs()
    original = prefs.filepath_
    prefs.filepath_ = str(tmp_path)
    try:
        yield str(tmp_path)
    finally:
        prefs.filepath_ = original


def _size(path):
    image = bpy.data.images.load(path, check_existing=False)
    try:
        return tuple(image.size)
    finally:
        bpy.data.images.remove(image)


def test_save_to_library_writes_three_resolutions(male_human, content_folder):
    thumbnail = bpy.data.images.new("hg_test_thumb", 64, 64)
    try:
        male_human.skin.texture.save_to_library("hg_saved_skin", category="Test", thumbnail=thumbnail)
    finally:
        if thumbnail.name in bpy.data.images:
            bpy.data.images.remove(thumbnail)

    folder = os.path.join(content_folder, "textures", "male")
    source = male_human.materials.body.node_tree.nodes["Color"].image.filepath
    ext = os.path.splitext(source)[1]
    expected = {"Test 4K": _size(bpy.path.abspath(source)), "Test 1K": (1024, 1024), "Test 512px": (512, 512)}
    for category, size in expected.items():
        texture = os.path.join(folder, category, "hg_saved_skin" + ext)
        assert os.path.isfile(texture), texture
        assert _size(texture) == size
        assert os.path.isfile(os.path.join(folder, category, "hg_saved_skin.jpg")), "thumbnail"


def test_save_to_library_leaves_no_image_datablocks(male_human, content_folder):
    thumbnail = bpy.data.images.new("hg_test_thumb2", 64, 64)
    thumbnail_name = thumbnail.name
    before = {image.name for image in bpy.data.images}
    try:
        male_human.skin.texture.save_to_library("hg_saved_skin2", category="Test", thumbnail=thumbnail)
    finally:
        bpy.data.images.remove(thumbnail)
    after = {image.name for image in bpy.data.images}
    assert after == before - {thumbnail_name}
