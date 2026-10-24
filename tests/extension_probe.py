# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Loads the add-on folder as the extension `bl_ext.hgtest.humgen3d` and reports.

Run by `tests/test_extension_mode.py` in a separate Blender Python with its own
user config, because the add-on can only be registered once per process and
the test process runs it as the legacy add-on `HumGen3D`. Prints one line that
starts with `PROBE ` followed by a JSON object with everything checked.

Usage: python extension_probe.py [scenario] <path of the add-on folder>
   or: blender -b --python extension_probe.py -- [scenario] <path of the add-on folder>

Scenarios:
    extension   (default) the extension alone
    twice       the legacy add-on in use, then the extension switched on next to it
    old_copy    the extension in use, then the legacy add-on switched on next to it
    old_blender the legacy add-on on a Blender older than 4.2: only a notice
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
    scenario = sys.argv[-2] if len(sys.argv) >= 3 and sys.argv[-2] in SCENARIOS else "extension"
    SCENARIOS[scenario](addon_dir)


def probe_extension(addon_dir: str) -> None:
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


# Two copies at once


def _handlers(name: str) -> list:
    """The modules of the load_post handlers called `name`."""
    import bpy

    return [h.__module__ for h in bpy.app.handlers.load_post if getattr(h, "__name__", "") == name]


class _Layout:
    """Stands in for a UILayout in a background Blender: records the texts of
    labels and buttons, every other call gives another stand-in."""

    def __init__(self, texts: list) -> None:
        self.__dict__["texts"] = texts

    def __getattr__(self, name: str):
        def call(*args, **kwargs):
            if "text" in kwargs:
                self.texts.append(kwargs["text"])
            if name == "operator" and args:
                self.texts.append("op:" + args[0])
            return _Layout(self.texts)

        return call

    def __setattr__(self, name: str, value) -> None:
        pass


def _add_menu_entries() -> list:
    import bpy

    funcs = bpy.types.VIEW3D_MT_add._dyn_ui_initialize()
    return [f.__module__ for f in funcs if getattr(f, "__name__", "") == "add_hg_primitive_menu"]


def _main_panel_owner() -> str:
    """The package whose main panel class is registered, "" for none."""
    import bpy

    cls = getattr(bpy.types, "HG_PT_Panel", None)
    return cls.__module__.rsplit(".user_interface", 1)[0] if cls is not None else ""


def _state(report: dict, prefix: str) -> None:
    import bpy

    addons = bpy.context.preferences.addons
    report[prefix + "_legacy_enabled"] = LEGACY in addons
    report[prefix + "_extension_enabled"] = MODULE_NAME in addons
    report[prefix + "_main_panel"] = _main_panel_owner()
    report[prefix + "_twice_notice"] = hasattr(bpy.types, "HG_PT_notice_twice")
    report[prefix + "_old_copy_notice"] = hasattr(bpy.types, "HG_PT_notice_old_copy")
    report[prefix + "_handlers"] = _handlers("HG_start")
    report[prefix + "_add_menu"] = _add_menu_entries()
    report[prefix + "_modes"] = {
        name: getattr(sys.modules.get(name), "_mode", None) for name in (LEGACY, MODULE_NAME) if name in addons
    }


def probe_twice(addon_dir: str) -> None:
    import bpy

    report: dict = {"blender": bpy.app.version_string, "scenario": "twice"}
    settings_file = os.environ.get("HUMGEN_SETTINGS_FILE", "")
    content = tempfile.mkdtemp(prefix="hg_twice_content_")
    repo_dir = make_repository(addon_dir)
    repos = bpy.context.preferences.extensions.repos
    repo = repos.new(name="HG Test Repo", module=REPO_MODULE)
    repo.use_custom_directory = True
    repo.custom_directory = repo_dir
    try:
        # 1. The legacy add-on in use, then the new zip dragged in next to it
        report["legacy_enable"] = sorted(bpy.ops.preferences.addon_enable(module=LEGACY))
        legacy_prefs = bpy.context.preferences.addons[LEGACY].preferences
        legacy_prefs.filepath_ = content
        legacy_prefs.units = "imperial"
        legacy_prefs.tab_name = "HG Test"
        report["extension_enable"] = sorted(bpy.ops.preferences.addon_enable(module=MODULE_NAME))
        _state(report, "both")
        report["extension_prefs_class"] = type(bpy.context.preferences.addons[MODULE_NAME].preferences).__name__

        # 2. "Use the new version"
        report["use_new_version"] = sorted(bpy.ops.hg3d.use_new_version())
        _state(report, "switched")
        prefs = bpy.context.preferences.addons[MODULE_NAME].preferences
        report["switched_filepath"] = prefs.filepath_ == content
        report["switched_units"] = prefs.units
        report["switched_tab_name"] = prefs.tab_name
        report["switched_panel_category"] = getattr(getattr(bpy.types, "HG_PT_Panel", None), "bl_category", "")
        if settings_file and os.path.isfile(settings_file):
            with open(settings_file, encoding="utf-8") as f:
                report["settings_content_folder"] = json.load(f).get("content_folder") == content
        import HumGen3D

        report["public_import_is_extension"] = HumGen3D is sys.modules[MODULE_NAME]

        # 3. Off: nothing of either copy left behind
        report["extension_disable"] = sorted(bpy.ops.preferences.addon_disable(module=MODULE_NAME))
        _state(report, "all_off")
    except Exception:  # noqa: BLE001
        report["error"] = traceback.format_exc()
    finally:
        repos.remove(repo)
    print("PROBE " + json.dumps(report))


def probe_old_copy(addon_dir: str) -> None:
    """The extension in use, then the legacy add-on switched on again.

    In a session of its own: once a script did `import HumGen3D`, that name is
    the extension, and Blender would take it for the legacy add-on.
    """
    import bpy

    report: dict = {"blender": bpy.app.version_string, "scenario": "old_copy"}
    repo_dir = make_repository(addon_dir)
    repos = bpy.context.preferences.extensions.repos
    repo = repos.new(name="HG Test Repo", module=REPO_MODULE)
    repo.use_custom_directory = True
    repo.custom_directory = repo_dir
    try:
        report["extension_enable"] = sorted(bpy.ops.preferences.addon_enable(module=MODULE_NAME))
        _state(report, "extension")
        report["legacy_enable"] = sorted(bpy.ops.preferences.addon_enable(module=LEGACY))
        _state(report, "both")
        report["legacy_file"] = getattr(sys.modules.get(LEGACY), "__file__", "")
        report["legacy_prefs_class"] = type(bpy.context.preferences.addons[LEGACY].preferences).__name__
        report["legacy_disable"] = sorted(bpy.ops.preferences.addon_disable(module=LEGACY))
        _state(report, "legacy_off")
        report["extension_disable"] = sorted(bpy.ops.preferences.addon_disable(module=MODULE_NAME))
        _state(report, "all_off")
    except Exception:  # noqa: BLE001
        report["error"] = traceback.format_exc()
    finally:
        repos.remove(repo)
    print("PROBE " + json.dumps(report))


def probe_old_blender(addon_dir: str) -> None:
    """The legacy add-on on Blender 4.0 or 4.1, run with that Blender's Python."""
    import bpy

    report: dict = {"blender": list(bpy.app.version), "scenario": "old_blender"}
    try:
        report["enable"] = sorted(bpy.ops.preferences.addon_enable(module=LEGACY))
        module = sys.modules[LEGACY]
        report["file"] = module.__file__
        report["mode"] = module._mode
        report["notice_panel"] = hasattr(bpy.types, "HG_PT_notice_unsupported")
        report["main_panel"] = hasattr(bpy.types, "HG_PT_Panel")
        report["setup_panel"] = hasattr(bpy.types, "HG_PT_SETUP")
        prefs = bpy.context.preferences.addons[LEGACY].preferences
        report["prefs_class"] = type(prefs).__name__
        # The updater, to go back to the last version for this Blender
        report["updater_settings"] = hasattr(prefs, "auto_check_update") and prefs.updater_interval_days == 7
        try:
            bpy.ops.humgen3d.updater_update_target.get_rna_type()
            report["updater_operators"] = True
        except (KeyError, AttributeError):
            report["updater_operators"] = False
        texts: list = []
        type(prefs).draw(type("Self", (), {"layout": _Layout(texts)})(), bpy.context)
        report["prefs_texts"] = texts
        panel_texts: list = []
        bpy.types.HG_PT_notice_unsupported.draw(type("Self", (), {"layout": _Layout(panel_texts)})(), bpy.context)
        report["panel_texts"] = panel_texts
        report["handlers"] = _handlers("HG_start")
        report["timers_or_scene_props"] = hasattr(bpy.types.Scene, "HG3D")
        # Nothing that may need a newer Blender is even imported
        report["heavy_imported"] = sorted(
            name for name in (LEGACY + ".human.human", LEGACY + ".user_interface.setup_overlay.operator") if name in sys.modules
        )
        report["disable"] = sorted(bpy.ops.preferences.addon_disable(module=LEGACY))
        report["notice_after_disable"] = hasattr(bpy.types, "HG_PT_notice_unsupported")
    except Exception:  # noqa: BLE001
        report["error"] = traceback.format_exc()
    print("PROBE " + json.dumps(report))


LEGACY = "HumGen3D"
SCENARIOS = {
    "extension": probe_extension,
    "twice": probe_twice,
    "old_copy": probe_old_copy,
    "old_blender": probe_old_blender,
}


if __name__ == "__main__":
    main()
