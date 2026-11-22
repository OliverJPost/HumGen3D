"""Finding the content folder and tidying the trial: the four folder states,
never swapping away from an unplugged drive, and an upgrade from the trial
that keeps every file the full library needs."""
import os
from types import SimpleNamespace

import pytest
from setup_fakes import exists, make_pack, write_pack

from HumGen3D.backend.setup import downloader, migration, user_settings
from HumGen3D.backend.setup.catalogue import installed_packs


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setenv(user_settings.ENV_OVERRIDE, str(path))
    return path


@pytest.fixture
def env(tmp_path, monkeypatch, settings_file):
    """Fake preferences, no other add-on copy, a default folder in tmp."""
    pref = SimpleNamespace(filepath_="")
    monkeypatch.setattr(migration, "_prefs", lambda: pref)
    monkeypatch.setattr(migration, "_other_copy_folders", lambda: [])
    monkeypatch.setattr(migration, "default_folder", lambda: str(tmp_path / "default"))
    return pref


def full(folder):
    write_pack(folder, "Base_Humans", (4, 1), ["models/HG_HUMAN.blend"])
    return str(folder)


# Folder states


def test_content_state(tmp_path):
    assert migration.content_state("") == "unset"
    assert migration.content_state(str(tmp_path / "deleted")) == "unreachable"
    assert migration.content_state(str(tmp_path)) == "empty"
    write_pack(tmp_path, "Base_Poses", (4, 0))
    assert migration.content_state(str(tmp_path)) == "empty"  # no humans
    write_pack(tmp_path, "Trial_Content", (4, 1))
    assert migration.content_state(str(tmp_path)) == "installed"


def test_drive_missing(tmp_path):
    assert migration.drive_missing("/Volumes/HG_No_Such_Drive_7f3a/HumGen Content")
    assert migration.content_state("/Volumes/HG_No_Such_Drive_7f3a/HumGen Content") == "unreachable"
    assert not migration.drive_missing(str(tmp_path / "gone"))
    assert not migration.drive_missing("")


# Resolving the folder


def test_resolve_keeps_an_unreachable_folder(env, tmp_path):
    """An unplugged drive keeps its place, even with content elsewhere."""
    env.filepath_ = "/Volumes/HG_No_Such_Drive_7f3a/Content/"
    other = full(tmp_path / "other")
    user_settings.update(content_folder=other)
    assert migration.resolve_content_folder() == "/Volumes/HG_No_Such_Drive_7f3a/Content/"
    assert env.filepath_ == "/Volumes/HG_No_Such_Drive_7f3a/Content/"
    assert user_settings.content_folder() == other
    env.filepath_ = str(tmp_path / "deleted")  # a deleted folder: also not swapped
    assert migration.resolve_content_folder() == str(tmp_path / "deleted")


def test_resolve_adopts_content_when_prefs_are_empty(env, tmp_path):
    other = full(tmp_path / "other")
    user_settings.update(content_folder=other)
    assert migration.resolve_content_folder() == other
    assert env.filepath_ == other


def test_resolve_finds_the_default_folder(env, tmp_path):
    full(tmp_path / "default")
    assert migration.resolve_content_folder() == str(tmp_path / "default")
    assert user_settings.content_folder() == str(tmp_path / "default")


def test_resolve_keeps_installed_prefs_and_syncs_settings(env, tmp_path):
    mine = full(tmp_path / "mine")
    full(tmp_path / "default")
    env.filepath_ = mine
    user_settings.update(content_folder=str(tmp_path / "old"))
    assert migration.resolve_content_folder() == mine
    assert user_settings.content_folder() == mine


def test_resolve_does_not_adopt_a_dead_settings_path(env, tmp_path):
    user_settings.update(content_folder=str(tmp_path / "deleted scratch folder"))
    assert migration.resolve_content_folder() == ""
    assert env.filepath_ == ""
    # A folder on a drive that is just not connected is kept as the answer
    user_settings.update(content_folder="/Volumes/HG_No_Such_Drive_7f3a/Content")
    assert migration.resolve_content_folder() == "/Volumes/HG_No_Such_Drive_7f3a/Content"


def test_resolve_keeps_an_empty_folder_the_user_picked(env, tmp_path):
    (tmp_path / "picked").mkdir()
    env.filepath_ = str(tmp_path / "picked")
    assert migration.resolve_content_folder() == str(tmp_path / "picked")
    other = full(tmp_path / "other")  # content found elsewhere wins over an empty folder
    user_settings.update(content_folder=other)
    assert migration.resolve_content_folder() == other


def test_find_existing_content_order(env, tmp_path, monkeypatch):
    assert migration.find_existing_content() is None
    legacy = full(tmp_path / "legacy")
    monkeypatch.setattr(migration, "_other_copy_folders", lambda: [legacy])
    assert migration.find_existing_content() == legacy
    saved = full(tmp_path / "saved")
    user_settings.update(content_folder=saved)
    assert migration.find_existing_content() == saved
    env.filepath_ = full(tmp_path / "prefs")
    assert migration.find_existing_content() == env.filepath_


# The trial cleanup


TRIAL_FILES = {
    "models/HG_HUMAN.blend": b"trial copy",
    "livekeys/body_proportions/main/male_skinny.npz": b"shared",
    "livekeys/body_proportions/Arms/Forearm Length.trial.npz": b"t",
    "livekeys/body_proportions/Arms/Upper Arm Length. trial.npz": b"t",
    "textures/male/Default 4K/Male Trial.png": b"t",
}


def test_upgrade_from_trial_keeps_the_shared_files(tmp_path):
    """B1: the trial and the base packs share files, HG_HUMAN.blend among them."""
    folder = str(tmp_path / "content")
    trial = tmp_path / "trial.hgpack"
    trial.write_bytes(make_pack("Trial_Content", (4, 1), TRIAL_FILES))
    downloader.install(str(trial), folder)
    base = tmp_path / "base.hgpack"
    base.write_bytes(make_pack("Base_Humans", (4, 1), {"models/HG_HUMAN.blend": b"full", "livekeys/body_proportions/main/male_skinny.npz": b"full", "livekeys/body_proportions/Arms/Forearm Length.npz": b"full"}))
    downloader.install(str(base), folder)
    assert migration.cleanup_trial(folder)
    assert exists(folder, "models/HG_HUMAN.blend")
    assert exists(folder, "livekeys/body_proportions/main/male_skinny.npz")
    assert exists(folder, "livekeys/body_proportions/Arms/Forearm Length.npz")
    assert not exists(folder, "livekeys/body_proportions/Arms/Forearm Length.trial.npz")
    assert not exists(folder, "livekeys/body_proportions/Arms/Upper Arm Length. trial.npz")
    assert not exists(folder, "textures/male/Default 4K/Male Trial.png")
    assert not os.path.exists(os.path.join(folder, "textures"))  # emptied by the cleanup
    assert set(installed_packs(folder)) == {"Base_Humans"}
    assert not migration.cleanup_trial(folder)


def test_cleanup_with_an_older_base_json(tmp_path):
    """Older base pack JSONs do not list every file they installed (a real
    Base_Humans.json lacks models/HG_HUMAN.blend): the trial's shared files
    stay all the same."""
    folder = str(tmp_path)
    write_pack(folder, "Trial_Content", (4, 0), list(TRIAL_FILES))
    write_pack(folder, "Base_Humans", (4, 1), ["livekeys/face.npz"])
    assert migration.cleanup_trial(folder)
    assert exists(folder, "models/HG_HUMAN.blend")
    assert exists(folder, "livekeys/body_proportions/main/male_skinny.npz")
    assert not exists(folder, "textures/male/Default 4K/Male Trial.png")
    assert "Trial_Content" not in installed_packs(folder)


def test_cleanup_leaves_a_trial_install_alone(tmp_path):
    write_pack(tmp_path, "Trial_Content", (4, 1), list(TRIAL_FILES))
    assert not migration.cleanup_trial(str(tmp_path))
    assert exists(tmp_path, "textures/male/Default 4K/Male Trial.png")


def test_startup_cleanup(env, tmp_path):
    folder = tmp_path / "content"
    write_pack(folder, "Trial_Content", (4, 1), list(TRIAL_FILES))
    write_pack(folder, "Base_Humans", (4, 1), ["models/HG_HUMAN.blend"])
    env.filepath_ = str(folder)
    assert migration.startup_cleanup()
    assert exists(folder, "models/HG_HUMAN.blend") and "Trial_Content" not in installed_packs(str(folder))
    assert not migration.startup_cleanup()
    assert not migration.startup_cleanup("/Volumes/HG_No_Such_Drive_7f3a/Content")
    assert not migration.startup_cleanup("")
