# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Notices that take the place of the add-on when it can't run normally.

`register()` in the package decides a mode before anything else:

- "full": the normal add-on.
- "unsupported": Blender older than 4.2. The legacy loader still loads the
  add-on there (bl_info), but it only says which Blender it needs.
- "twice": this copy is the extension and the legacy `HumGen3D` add-on in the
  add-ons folder is switched on too. Registering both would swap their classes
  and break both, so this copy only offers "Use the new version", which takes
  over the preferences of the legacy copy, switches it off and then registers
  the add-on for real (see `use_new_version` in the package).
- "old_copy": the same from the other side, this is the legacy copy and an
  extension copy is switched on.

The notice classes are made by `notice_classes`, not defined in the module, so
the class discovery of `backend/auto_classes.py` never registers them with the
add-on. Nothing here imports the rest of the add-on, so it works on every
Blender the legacy loader accepts.
"""
import importlib
import importlib.machinery
import importlib.util
import sys
from typing import Any, Dict, List, Optional, Sequence

import bpy

from ..common.documentation import docs_url
from ..common.i18n import tr
from ..package import (
    PUBLIC_NAME,
    addon_package,
    blender_supported,
    is_extension,
    manifest_version,
    other_copies,
)

MODES = ("full", "unsupported", "twice", "old_copy")
TWICE_PANEL = "HG_PT_notice_twice"
USE_NEW_VERSION = "hg3d.use_new_version"
# The version 4.0 and 4.1 users go back to with the updater (a GitHub tag)
LAST_OLD_BLENDER_VERSION = "4.0.33"

# The notice classes this copy registered, unregistered by `unregister`
_registered: List[Any] = []


def _code_present(name: str) -> bool:
    """Whether the package `name` can be imported, without the alias finder,
    which would answer for `HumGen3D` with this copy."""
    module = sys.modules.get(name)
    if module is not None and getattr(module, "__name__", "") == name:
        return True
    try:
        if "." not in name:
            return importlib.machinery.PathFinder.find_spec(name) is not None
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def other_copy() -> Optional[str]:
    """The package name of the other enabled Human Generator, or None."""
    try:
        enabled = list(bpy.context.preferences.addons.keys())
    except AttributeError:  # no preferences while Blender starts up headless
        return None
    for name in other_copies(enabled, addon_package()):
        if _code_present(name):
            return name
    return None


def startup_mode() -> str:
    """Which of `MODES` this copy registers in."""
    if not blender_supported():
        return "unsupported"
    if other_copy() is None:
        return "full"
    return "twice" if is_extension() else "old_copy"


# Preferences of the legacy copy

# UI state, not preferences
SKIP_PREFERENCES = {"rna_type", "bl_idname", "pref_tabs"}


def _plain(value: Any) -> Any:
    """An ID property value as plain Python."""
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "to_list"):
        return value.to_list()
    return value


def _stored_values(prefs: Any) -> Dict[str, Any]:
    """What Blender stored for the add-on, whatever preferences class that
    copy registered (an older version, or only a notice). Enums as numbers."""
    try:
        # Blender 5.0 keeps the values of registered properties apart
        get_store = getattr(prefs, "bl_system_properties_get", None)
        store = get_store() if get_store is not None else prefs
        if store is None:
            return {}
        return {key: _plain(store[key]) for key in store.keys()}
    except (AttributeError, TypeError, KeyError):
        return {}


def _registered_values(prefs: Any) -> Dict[str, Any]:
    """The values of the properties of the registered preferences class."""
    values: Dict[str, Any] = {}
    for prop in prefs.bl_rna.properties:
        key = prop.identifier
        if key in SKIP_PREFERENCES or prop.is_readonly or prop.type in ("POINTER", "COLLECTION"):
            continue
        value = getattr(prefs, key, None)
        if getattr(prop, "is_array", False) or hasattr(value, "__len__") and not isinstance(value, (str, set)):
            value = tuple(value)
        values[key] = value
    return values


def preference_values(prefs: Any) -> Dict[str, Any]:
    """Every preference of an add-on, to take over with `apply_preference_values`."""
    if prefs is None:
        return {}
    values = _stored_values(prefs)
    values.update(_registered_values(prefs))
    return values


def _enum_identifier(prop: Any, value: int) -> Any:
    for item in prop.enum_items:
        if item.value == value:
            return item.identifier
    return value


def apply_preference_values(prefs: Any, values: Dict[str, Any], skip: Sequence[str] = ()) -> None:
    """Set `values` from `preference_values` on another add-on's preferences.

    Properties that run an update when set are in `skip` until the add-on is
    fully registered (the tab name registers the panels again).
    """
    properties = prefs.bl_rna.properties
    for key, value in values.items():
        prop = properties.get(key)
        if prop is None or key in skip or key in SKIP_PREFERENCES:
            continue
        if prop.is_readonly or prop.type in ("POINTER", "COLLECTION"):
            continue
        if prop.type == "ENUM" and isinstance(value, int):
            value = _enum_identifier(prop, value)
        try:
            current = getattr(prefs, key)
            if hasattr(current, "__len__") and not isinstance(current, (str, set)):
                current = tuple(current)
            if current != value:
                setattr(prefs, key, value)
        except (TypeError, ValueError, AttributeError) as e:
            print(f"HumGen: could not take over the preference {key}:", repr(e))


def forget_legacy_modules() -> None:
    """Drop the switched-off legacy package from `sys.modules`, so `import
    HumGen3D` reaches this copy through the alias from now on."""
    for name in list(sys.modules):
        if name == PUBLIC_NAME or name.startswith(PUBLIC_NAME + "."):
            module = sys.modules[name]
            if getattr(module, "__name__", name) == name:
                del sys.modules[name]


# Drawing


def _version_text() -> str:
    return ".".join(str(n) for n in manifest_version())


def _lines(layout: Any, *texts: str) -> None:
    col = layout.column(align=True)
    for text in texts:
        col.label(text=text)


def _updater_ops() -> Optional[Any]:
    """The legacy updater's operators module, None when it didn't load."""
    try:
        return importlib.import_module(addon_package() + ".backend.updates.addon_updater_ops")
    except Exception:  # noqa: BLE001 - the notice must draw whatever happens
        return None


def draw_notice(layout: Any, mode: str, prefs: Any = None) -> None:
    """The notice of `mode`, for the sidebar panel and, with `prefs`, the
    add-on preferences."""
    if mode == "unsupported":
        _lines(
            layout,
            tr("Human Generator {version} needs Blender 4.2 or newer.").format(version=_version_text()),
            tr("Your content and saved files are not affected."),
        )
        # The way back: the updater installs the last version for this Blender
        if prefs is None:
            _lines(
                layout,
                tr("To keep using it here, go back to version {version}").format(version=LAST_OLD_BLENDER_VERSION),
                tr("with the updater in the add-on preferences."),
            )
            layout.operator("preferences.addon_show", text=tr("Open the updater"), icon="PREFERENCES").module = addon_package()
        else:
            _lines(
                layout,
                tr("To keep using it here, go back to version {version} with the updater below:").format(version=LAST_OLD_BLENDER_VERSION),
                tr("press Check now for humgen3d update, then Install main / old version, and choose v{version}.").format(
                    version=LAST_OLD_BLENDER_VERSION
                ),
            )
        layout.operator("wm.url_open", text=tr("Learn more"), icon="HELP").url = (
            docs_url("guide/installation") + "#blender-version"
        )
        ops = _updater_ops() if prefs is not None else None
        if ops is not None:
            ops.update_settings_ui(prefs, bpy.context, element=layout)
    elif mode == "twice":
        if other_copy() is not None:
            _lines(
                layout,
                tr("Human Generator is installed twice."),
                tr("The older copy in your add-ons folder is still switched on."),
            )
        else:
            _lines(layout, tr("The older copy of Human Generator is switched off."))
        row = layout.row()
        row.scale_y = 1.4
        row.operator(USE_NEW_VERSION, text=tr("Use the new version"), icon="CHECKMARK", depress=True)
        col = layout.column()
        col.enabled = False
        col.label(text=tr("Keeps your content folder and settings."))
    elif mode == "old_copy":
        _lines(
            layout,
            tr("A newer Human Generator is installed as an extension."),
            tr("This older copy is switched off."),
        )
        layout.operator("hg3d.switch_off_old_copy", text=tr("Switch off this copy"), icon="QUIT")


# Operators


def _use_new_version_registered() -> bool:
    try:
        bpy.ops.hg3d.use_new_version.get_rna_type()
    except (KeyError, AttributeError):
        return False
    return True


def _switch_off_later() -> None:
    """From a timer, so the operator that asked is no longer running when its
    add-on is switched off."""
    if _use_new_version_registered():
        bpy.ops.hg3d.use_new_version()
    else:
        bpy.ops.preferences.addon_disable(module=addon_package())
    return None


def _updater_properties() -> Dict[str, Any]:
    from bpy.props import BoolProperty, IntProperty

    return {
        "auto_check_update": BoolProperty(
            name="Auto-check for Update", description="If enabled, auto-check for updates using an interval", default=False
        ),
        "updater_interval_months": IntProperty(name="Months", description="Number of months between checking for updates", default=0, min=0),
        "updater_interval_days": IntProperty(name="Days", description="Number of days between checking for updates", default=7, min=0, max=31),
        "updater_interval_hours": IntProperty(name="Hours", description="Number of hours between checking for updates", default=0, min=0, max=23),
        "updater_interval_minutes": IntProperty(
            name="Minutes", description="Number of minutes between checking for updates", default=0, min=0, max=59
        ),
    }


def register_updater() -> None:
    """The legacy updater, so Blender 4.0 and 4.1 can go back to
    `LAST_OLD_BLENDER_VERSION`. The notice works without it."""
    ops = _updater_ops()
    if ops is None:
        print("HumGen: the updater could not be loaded")
        return
    try:
        ops.register(_bl_info())
    except Exception as e:  # noqa: BLE001
        print("HumGen: could not register the updater:", repr(e))


def unregister_updater() -> None:
    ops = _updater_ops()
    if ops is not None:
        try:
            ops.unregister()
        except Exception as e:  # noqa: BLE001
            print("HumGen: could not unregister the updater:", repr(e))


def _bl_info() -> Dict[str, Any]:
    return getattr(sys.modules[addon_package()], "bl_info")


def notice_classes(mode: str) -> List[Any]:
    """New notice classes for `mode`: a sidebar panel, the add-on preferences
    and the operator of the button."""
    package = addon_package()

    class HG_PT_install_notice(bpy.types.Panel):
        bl_idname = "HG_PT_notice_" + mode
        bl_label = "Human Generator"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "HumGen"

        @classmethod
        def poll(cls, context):
            # Both copies in notice mode: the extension's notice says it all
            return mode != "old_copy" or not hasattr(bpy.types, TWICE_PANEL)

        def draw(self, context):
            draw_notice(self.layout, mode)

    class HG_PREF_install_notice(bpy.types.AddonPreferences):
        bl_idname = package

        def draw(self, context):
            draw_notice(self.layout, mode, prefs=self)

    if mode == "unsupported":
        # The legacy updater keeps its settings in the add-on preferences, the
        # same names as in `HGPreferenceBackend`
        HG_PREF_install_notice.__annotations__ = _updater_properties()

    classes: List[Any] = [HG_PT_install_notice, HG_PREF_install_notice]

    if mode == "twice":

        class HG3D_OT_use_new_version(bpy.types.Operator):
            """Switch off the older copy in your add-ons folder and use this one, with the same content folder and settings"""

            bl_idname = USE_NEW_VERSION
            bl_label = "Use the new version"
            bl_options = {"INTERNAL"}

            def execute(self, context):
                switched, message = importlib.import_module(package).use_new_version()
                self.report({"INFO"} if switched else {"WARNING"}, message)
                return {"FINISHED"} if switched else {"CANCELLED"}

        classes.append(HG3D_OT_use_new_version)

    elif mode == "old_copy":

        class HG3D_OT_switch_off_old_copy(bpy.types.Operator):
            """Switch off this older copy of Human Generator. The extension takes over"""

            bl_idname = "hg3d.switch_off_old_copy"
            bl_label = "Switch off this copy"
            bl_options = {"INTERNAL"}

            def execute(self, context):
                bpy.app.timers.register(_switch_off_later, first_interval=0)
                return {"FINISHED"}

        classes.append(HG3D_OT_switch_off_old_copy)

    return classes


def register(mode: str) -> None:
    """Register the notice of `mode`. Nothing for "full"."""
    if mode == "full":
        return
    for cls in notice_classes(mode):
        bpy.utils.register_class(cls)
        _registered.append(cls)


def unregister_preferences() -> None:
    """Make room for the add-on's own preferences class, keep the rest."""
    for cls in [c for c in _registered if issubclass(c, bpy.types.AddonPreferences)]:
        bpy.utils.unregister_class(cls)
        _registered.remove(cls)


def unregister() -> None:
    while _registered:
        cls = _registered.pop()
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError as e:
            print("HumGen: could not unregister", cls.__name__, repr(e))
