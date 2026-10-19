# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The add-on loaded as a Blender extension, in a separate Blender Python.

See `extension_probe.py`. The probe gets an empty user config, so no add-on is
enabled at startup and the legacy `HumGen3D` is not in the way.
"""
import json
import os
import subprocess
import sys
import tempfile

import pytest

from HumGen3D.package import addon_root

PROBE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extension_probe.py")


@pytest.fixture(scope="module")
def probe_report() -> dict:
    env = dict(os.environ)
    env["BLENDER_USER_CONFIG"] = tempfile.mkdtemp(prefix="hg_ext_config_")
    result = subprocess.run(
        [sys.executable, PROBE, addon_root()],
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    lines = [line for line in result.stdout.splitlines() if line.startswith("PROBE ")]
    assert lines, f"No report from the probe\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    report = json.loads(lines[-1][len("PROBE "):])
    assert "error" not in report, report["error"]
    return report


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
