# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Loads the add-on folder as the extension `bl_ext.hgtest.humgen3d` and reports.

Run by `tests/test_extension_mode.py` in a separate Blender Python with its own
user config, because the add-on can only be registered once per process and
the test process runs it as the legacy add-on `HumGen3D`. Prints one line that
starts with `PROBE ` followed by a JSON object with everything checked.

Usage: python extension_probe.py <path of the add-on folder>
   or: blender -b --python extension_probe.py -- <path of the add-on folder>
"""
import json
import os
import shutil
import sys
import tempfile
import traceback

REPO_MODULE = "hgtest"
EXTENSION_ID = "humgen3d"
MODULE_NAME = f"bl_ext.{REPO_MODULE}.{EXTENSION_ID}"

# Folders not needed to run the add-on, left out of the copy if a symlink can't be made
HEAVY_DIRS = {"tests", "docs", "venv", ".venv", ".git", "__pycache__", "scripts", "reports"}


def make_repository(addon_dir: str) -> str:
    """A folder holding the add-on as `<repo>/humgen3d`, the shape of an extension repository."""
    repo_dir = tempfile.mkdtemp(prefix="hg_ext_repo_")
    target = os.path.join(repo_dir, EXTENSION_ID)
    try:
        os.symlink(addon_dir, target)
    except OSError:
        shutil.copytree(addon_dir, target, ignore=shutil.ignore_patterns(*HEAVY_DIRS))
    return repo_dir


def main() -> None:
    # Last argument, so it also works as `blender -b --python extension_probe.py -- <folder>`
    addon_dir = os.path.abspath(sys.argv[-1])
    import bpy

    report = {
        "blender": bpy.app.version_string,
        "legacy_preloaded": "HumGen3D" in sys.modules,
        "legacy_enabled": bool(bpy.context.preferences.addons.get("HumGen3D")),
    }
    repo_dir = make_repository(addon_dir)
    repos = bpy.context.preferences.extensions.repos
    repo = repos.new(name="HG Test Repo", module=REPO_MODULE)
    repo.use_custom_directory = True
    repo.custom_directory = repo_dir
    try:
        bpy.ops.preferences.addon_enable(module=MODULE_NAME)
        report["enabled"] = MODULE_NAME in bpy.context.preferences.addons
        extension = sys.modules[MODULE_NAME]
        report["version"] = list(extension.__version__)

        # The public import name resolves to the extension's own modules
        import HumGen3D
        from HumGen3D import Human
        from HumGen3D.human.human import Human as human_module_class
        import HumGen3D.human.skin.skin as skin_alias

        report["alias_root_is_extension"] = HumGen3D is extension
        report["alias_class_identity"] = (
            Human is extension.Human and human_module_class is Human
        )
        report["alias_submodule_identity"] = skin_alias is sys.modules[
            MODULE_NAME + ".human.skin.skin"
        ]
        report["alias_module_name"] = sys.modules["HumGen3D"].__name__
        report["alias_spec_name"] = sys.modules["HumGen3D.human.skin.skin"].__spec__.name
        report["alias_entries"] = sorted(
            name for name in sys.modules if name == "HumGen3D" or name.startswith("HumGen3D.")
        )[:5]

        from HumGen3D.package import addon_package, is_extension, addon_version
        from HumGen3D.backend.preferences.preference_func import get_prefs
        from HumGen3D.backend.preferences.preferences import HG_PREF
        from HumGen3D.backend.updates import addon_updater_ops
        from HumGen3D import alias
        from HumGen3D.user_interface.main_panel.main_panel import HG_PT_PANEL

        report["package"] = addon_package()
        report["is_extension"] = is_extension()
        report["addon_version"] = list(addon_version())
        report["pref_idname"] = HG_PREF.bl_idname
        report["prefs_reachable"] = get_prefs().tab_name == "HumGen"
        report["updater_registered"] = any(
            getattr(cls, "is_registered", False) for cls in addon_updater_ops.classes
        )
        report["panel_registered"] = HG_PT_PANEL.is_registered
        report["finder_aliases"] = list(alias.installed().aliases)
        report["finder_package"] = alias.installed().package
        if get_prefs().filepath and os.path.isdir(get_prefs().filepath):
            report["preset_count"] = len(Human.get_preset_options("male", context=bpy.context))

        bpy.ops.preferences.addon_disable(module=MODULE_NAME)
        report["disabled"] = MODULE_NAME not in bpy.context.preferences.addons
        report["alias_after_disable"] = "HumGen3D" in sys.modules
        report["panel_after_disable"] = HG_PT_PANEL.is_registered
        report["finder_after_disable"] = alias.installed() is not None
    except Exception:  # noqa: BLE001
        report["error"] = traceback.format_exc()
    finally:
        repos.remove(repo)
    print("PROBE " + json.dumps(report))


if __name__ == "__main__":
    main()
