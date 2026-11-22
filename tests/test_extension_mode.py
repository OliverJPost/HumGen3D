# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The add-on loaded as a Blender extension, in a separate Blender Python.

See `extension_probe.py`. The probe gets an empty user config, so no add-on is
enabled at startup and the legacy `HumGen3D` is not in the way, unless a test
switches it on to check the double install. The last test loads the legacy
add-on in Blender 4.0's Python, where it only shows a notice.
"""
import json
import os
import subprocess
import sys
import tempfile

import pytest

from HumGen3D.package import addon_root

PROBE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extension_probe.py")


# Blender 4.0's Python module, for the "needs a newer Blender" notice
OLD_BPY_PYTHON = "/opt/homebrew/Caskroom/miniforge/base/envs/bpy/bin/python"


def run_probe(scenario: str, python: str = sys.executable, **env_extra: str) -> dict:
    """Run the probe in a fresh Blender Python with an empty user config and
    settings file. Fails on any traceback in its output."""
    env = dict(os.environ)
    env["BLENDER_USER_CONFIG"] = tempfile.mkdtemp(prefix="hg_ext_config_")
    env["HUMGEN_SETTINGS_FILE"] = os.path.join(tempfile.mkdtemp(prefix="hg_ext_settings_"), "settings.json")
    env.update(env_extra)
    result = subprocess.run(
        [python, PROBE, scenario, addon_root()],
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    lines = [line for line in result.stdout.splitlines() if line.startswith("PROBE ")]
    assert lines, f"No report from the probe\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    report = json.loads(lines[-1][len("PROBE "):])
    assert "error" not in report, report["error"]
    output = result.stdout + result.stderr
    assert "Traceback" not in output, output
    report["settings_file"] = env["HUMGEN_SETTINGS_FILE"]
    return report


@pytest.fixture(scope="module")
def probe_report() -> dict:
    return run_probe("extension")


def test_probe_started_clean(probe_report):
    assert not probe_report["legacy_preloaded"]
    assert not probe_report["legacy_enabled"]


def test_extension_enables(probe_report):
    assert probe_report["enabled"]
    assert probe_report["package"] == "bl_ext.hgtest.humgen3d"
    assert probe_report["is_extension"]
    assert probe_report["panel_registered"]


def test_public_import_is_the_extension(probe_report):
    assert probe_report["alias_root_is_extension"]
    assert probe_report["alias_class_identity"]
    assert probe_report["alias_submodule_identity"]
    # The shared module objects keep their real names
    assert probe_report["alias_module_name"] == "bl_ext.hgtest.humgen3d"
    assert probe_report["alias_spec_name"] == "bl_ext.hgtest.humgen3d.human.skin.skin"
    assert "HumGen3D" in probe_report["alias_entries"]
    assert probe_report["finder_package"] == "bl_ext.hgtest.humgen3d"
    assert set(probe_report["finder_aliases"]) == {"HumGen3D", "HG3D"}


def test_preferences_use_the_package_name(probe_report):
    assert probe_report["pref_idname"] == "bl_ext.hgtest.humgen3d"
    assert probe_report["prefs_reachable"]


def test_version_from_manifest(probe_report):
    from HumGen3D.package import manifest_version

    assert tuple(probe_report["version"]) == manifest_version()
    assert tuple(probe_report["addon_version"]) == manifest_version()


def test_updater_not_registered_as_extension(probe_report):
    assert not probe_report["updater_registered"]


def test_content_reachable(probe_report):
    if "preset_count" not in probe_report:
        pytest.skip("No content folder on this machine")
    assert probe_report["preset_count"] > 0


def test_disable_cleans_up(probe_report):
    assert probe_report["disabled"]
    assert not probe_report["alias_after_disable"]
    assert not probe_report["panel_after_disable"]
    assert not probe_report["finder_after_disable"]


# Installed twice: the legacy add-on in the add-ons folder and the extension


@pytest.fixture(scope="module")
def twice_report() -> dict:
    return run_probe("twice")


def test_twice_registers_one_set_of_classes(twice_report):
    r = twice_report
    assert r["legacy_enable"] == ["FINISHED"] and r["extension_enable"] == ["FINISHED"]
    assert r["both_modes"] == {"HumGen3D": "full", "bl_ext.hgtest.humgen3d": "twice"}
    # The legacy copy keeps working, untouched
    assert r["both_main_panel"] == "HumGen3D"
    assert r["both_handlers"] == ["HumGen3D"]
    assert r["both_add_menu"] == ["HumGen3D.user_interface.batch_panel.primitive_menu"]
    # The extension only shows its notice
    assert r["both_twice_notice"]
    assert r["extension_prefs_class"] == "HG_PREF_install_notice"


def test_use_new_version_takes_over(twice_report):
    r = twice_report
    assert r["use_new_version"] == ["FINISHED"]
    assert not r["switched_legacy_enabled"]
    assert r["switched_modes"] == {"bl_ext.hgtest.humgen3d": "full"}
    assert r["switched_main_panel"] == "bl_ext.hgtest.humgen3d"
    assert r["switched_handlers"] == ["bl_ext.hgtest.humgen3d"]
    assert r["switched_add_menu"] == ["bl_ext.hgtest.humgen3d.user_interface.batch_panel.primitive_menu"]
    assert r["public_import_is_extension"]


def test_use_new_version_keeps_the_preferences(twice_report):
    r = twice_report
    assert r["switched_filepath"]
    assert r["switched_units"] == "imperial"
    assert r["switched_tab_name"] == "HG Test"
    assert r["switched_panel_category"] == "HG Test"
    assert r["settings_content_folder"]


def test_twice_disables_cleanly(twice_report):
    r = twice_report
    assert r["extension_disable"] == ["FINISHED"]
    assert r["all_off_main_panel"] == ""
    assert not r["all_off_twice_notice"]
    assert r["all_off_handlers"] == []
    assert r["all_off_add_menu"] == []


@pytest.fixture(scope="module")
def old_copy_report() -> dict:
    return run_probe("old_copy")


def test_legacy_copy_next_to_the_extension_only_shows_a_notice(old_copy_report):
    r = old_copy_report
    assert r["both_modes"] == {"HumGen3D": "old_copy", "bl_ext.hgtest.humgen3d": "full"}
    # The real legacy package, not the extension through the alias
    assert r["legacy_file"].endswith(os.path.join("HumGen3D", "__init__.py"))
    assert r["legacy_prefs_class"] == "HG_PREF_install_notice"
    assert r["both_old_copy_notice"]
    assert r["both_main_panel"] == "bl_ext.hgtest.humgen3d"
    assert r["both_handlers"] == ["bl_ext.hgtest.humgen3d"]
    assert r["both_add_menu"] == ["bl_ext.hgtest.humgen3d.user_interface.batch_panel.primitive_menu"]


def test_switching_off_the_legacy_copy_leaves_the_extension(old_copy_report):
    r = old_copy_report
    assert r["legacy_disable"] == ["FINISHED"]
    assert not r["legacy_off_old_copy_notice"]
    assert r["legacy_off_main_panel"] == "bl_ext.hgtest.humgen3d"
    assert r["legacy_off_handlers"] == ["bl_ext.hgtest.humgen3d"]
    assert r["all_off_main_panel"] == ""
    assert r["all_off_handlers"] == []


# Blender older than 4.2


@pytest.mark.skipif(not os.path.isfile(OLD_BPY_PYTHON), reason="No Blender 4.0 Python module on this machine")
def test_old_blender_only_registers_a_notice():
    r = run_probe("old_blender", python=OLD_BPY_PYTHON, PYTHONPATH=os.path.dirname(addon_root()))
    assert r["blender"][:2] == [4, 0]
    assert r["file"].startswith(addon_root())
    assert r["enable"] == ["FINISHED"]
    assert r["mode"] == "unsupported"
    assert r["notice_panel"]
    assert r["prefs_class"] == "HG_PREF_install_notice"
    # The way back to the last version for this Blender: the updater, in the preferences
    assert r["updater_settings"] and r["updater_operators"]
    assert any("4.0.33" in text for text in r["prefs_texts"])
    assert "op:humgen3d.updater_update_target" in r["prefs_texts"]
    assert "op:preferences.addon_show" in r["panel_texts"]
    assert not r["main_panel"] and not r["setup_panel"]
    assert r["handlers"] == []
    assert not r["timers_or_scene_props"]
    assert r["heavy_imported"] == []
    assert r["disable"] == ["FINISHED"]
    assert not r["notice_after_disable"]
    # Nothing written outside Blender
    assert not os.path.exists(r["settings_file"])
