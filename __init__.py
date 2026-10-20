"""
    Created by Oliver J Post & Alexander Lashko

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

# flake8: noqa E402

bl_info = {
    "name": "Human Generator 3D",
    "author": "OliverJPost",
    "description": "Human Generator allows you to generate humans including clothing, poses and emotions",  # noqa
    "blender": (4, 0, 0),
    "version": (4, 0, 38),  # RELEASE update version number
    "location": "Add-On Sidepanel > HumGen",
    "wiki_url": "https://humgen3d.com",
    "tracker_url": "https://humgen3d.com",
    "warning": "",
    "category": "",
}

import os
from typing import Any, Dict, Optional, Tuple

import bpy  # type: ignore
from bpy.app.handlers import persistent as _persistent

from . import alias as _alias
from .package import PUBLIC_NAME as _PUBLIC_NAME
from .package import blender_supported as _blender_supported
from .package import is_extension as _is_extension
from .package import manifest_version as _manifest_version
from .user_interface import install_notices as _notices

__version__ = _manifest_version()
"""The version, from blender_manifest.toml. bl_info mirrors it for Blender 4.0 and 4.1."""

# Blender older than 4.2 only gets a notice (see user_interface/install_notices.py),
# so nothing that may need a newer Blender is imported there
if _blender_supported():
    # Has to be imported like this, otherwise returns error for some users
    import bpy.utils.previews  # type: ignore
    from .backend.auto_classes import _get_bpy_classes
    from .backend.content import content_packs  # type: ignore
    from .backend.content.content_packs import cpacks_refresh as _cpacks_refresh
    from .backend.preferences.preference_func import get_prefs
    from .backend.preview_collections import PREVIEW_COLLECTION_DATA, PreviewCollection
    from .backend.preview_collections import preview_collections as _preview_collections
    from .backend.properties.object_props import HG_OBJECT_PROPS
    from .backend.updates import addon_updater_ops
    from .common import i18n as _i18n
    from .backend.setup import migration as _migration
    from .backend.setup import update_check as _update_check
    from .backend.setup import user_settings as _user_settings
    from .backend.vscode_reload import _post_vscode_reload  # noqa
    from .batch_generator.generator import BatchHumanGenerator
    from .common.exceptions import HumGenException
    from .human.human import Human
    from .human.process.export_pack import ExportPackMissing
    from .human.process.pipeline import ExportResult
    from .human.process.settings import (
        AnimationClipSettings,
        ExportSettings,
        FbxSettings,
        GltfSettings,
        HaircardSettings,
        MeshSettings,
        OutputSettings,
        QualitySettings,
        ScriptSettings,
        ScriptsSettings,
        ShapeKeySettings,
        SkeletonSettings,
        TextureBakeSettings,
    )
    from .human.keys.bpy_livekey import BpyLiveKey
    from .human.keys.keys import KeyItem, LiveKeyItem, ShapeKeyItem
    from .user_interface.batch_panel import batch_ui_lists
    from .user_interface.content_panel import utility_ui_lists
    from .user_interface.icons.icons import hg_icons
    from .user_interface.setup_overlay import operator as _setup_operator

__all__ = [
    "Human",
    "BatchHumanGenerator",
    "HumGenException",
    "LiveKeyItem",
    "ShapeKeyItem",
    "KeyItem",
    "get_prefs",
    # The settings of the process system, see human/process/settings.py
    "ExportSettings",
    "ExportResult",
    "ExportPackMissing",
    "OutputSettings",
    "FbxSettings",
    "GltfSettings",
    "QualitySettings",
    "MeshSettings",
    "HaircardSettings",
    "SkeletonSettings",
    "ShapeKeySettings",
    "TextureBakeSettings",
    "AnimationClipSettings",
    "ScriptsSettings",
    "ScriptSettings",
]

# What register() did, one of install_notices.MODES
_mode = "full"
# Whether HG_start ran since register(): at startup load_post follows register,
# when the add-on is switched on later nothing does
_started = False


# `import HumGen3D` keeps working when Blender loaded the package as an extension.
# Not while the other copy is switched on: `HumGen3D` is that copy then.
if _blender_supported() and _notices.other_copy() is None:
    _alias.install()


# Startup procedure
@_persistent
def HG_start(dummy: Any) -> None:
    """Runs the activating class when a file is loaded or blender is opened.

    Never raises, so the update check at the end always gets scheduled.
    """
    global _started
    _started = True
    try:
        # The preferences' filepath also covers the developer's HUMGEN_DEV_CONTENT
        folder = _migration.resolve_content_folder() or get_prefs().filepath
        if folder:
            # Safe trial cleanup when the full packs were installed over it
            _migration.startup_cleanup(folder)
        if _migration.folder_has_content(folder):
            bpy.ops.HG3D.activate()
        else:  # nothing installed yet: the Setup panel takes over
            print("HumGen: no content installed yet, open the Setup panel in the HumGen tab")
    except Exception as e:  # noqa: BLE001
        print("HumGen: could not prepare the content folder:", repr(e))
    try:
        _cpacks_refresh(None, bpy.context)
    except Exception as e:  # noqa: BLE001
        print("HumGen: could not read the content packs:", repr(e))
    try:
        _update_check.schedule()
    except Exception as e:  # noqa: BLE001
        print("HumGen: could not schedule the update check:", repr(e))


def _after_register() -> None:
    """Zero-delay timer after register(): find the content folder and check
    for updates when no load_post follows (the add-on was switched on in a
    running Blender), then open the setup once on a fresh install."""
    if not _started:
        HG_start(None)
    try:
        _setup_operator.maybe_auto_open()
    except Exception as e:  # noqa: BLE001
        print("HumGen: could not open the setup:", repr(e))
    return None


def _initiate_preview_collections() -> None:
    # Initiate preview collections
    for pcoll_name in PREVIEW_COLLECTION_DATA:
        _preview_collections[pcoll_name] = PreviewCollection(
            pcoll_name, bpy.utils.previews.new()
        )


def _initiate_custom_icons() -> None:
    """Load custom icons"""

    hg_icons.append(bpy.utils.previews.new())

    icon_dir = os.path.join(os.path.dirname(__file__), "user_interface", "icons")
    for root, _, fns in os.walk(icon_dir):
        png_files = [f for f in fns if f.endswith(".png")]
        for fn in png_files:
            fn_base = os.path.splitext(fn)[0]
            full_path = os.path.join(root, fn)
            hg_icons[0].load(fn_base, full_path, "IMAGE")


def _initiate_ui_lists() -> None:
    # Import in local namespace to prevent cluttering package namespace
    from .backend.content import custom_content_packs
    from .backend.content.possible_content import POSSIBLE_CONTENT_ITEM
    from .backend.updates import update
    from .user_interface.documentation import tips_suggestions_ui

    collections = {
        "batch_clothing_col": batch_ui_lists.BATCH_CLOTHING_ITEM,
        "contentpacks_col": content_packs.HG_CONTENT_PACK,
        "installpacks_col": content_packs.HG_INSTALLPACK,
        "shapekeys_col": utility_ui_lists.SHAPEKEY_ITEM,
        "savehair_col": utility_ui_lists.SAVEHAIR_ITEM,
        "saveoutfit_col": utility_ui_lists.SAVEOUTFIT_ITEM,
        "custom_content_col": custom_content_packs.CUSTOM_CONTENT_ITEM,
        "hg_update_col": update.UPDATE_INFO_ITEM,
        "hg_tips_and_suggestions": tips_suggestions_ui.TIPS_ITEM,
        "possible_content_col": POSSIBLE_CONTENT_ITEM,
    }

    scene = bpy.types.Scene
    for coll_name, coll_class in collections.items():
        coll_prop = bpy.props.CollectionProperty(type=coll_class)  # type:ignore
        setattr(scene, coll_name, coll_prop)
        index = bpy.props.IntProperty(name="Index", default=0)  # type:ignore
        setattr(scene, f"{coll_name}_index", index)


if _blender_supported():
    hg_classes = _get_bpy_classes()
else:
    hg_classes = []
ui_tab_classes = [cls for cls in hg_classes if hasattr(cls, "bl_category")]
non_ui_tab_classes = [cls for cls in hg_classes if cls not in ui_tab_classes]


def register() -> None:
    global _mode
    _mode = _notices.startup_mode()
    if _mode == "unsupported":
        _notices.register(_mode)
        return
    if _mode != "full":
        print(f"HumGen: {_notices.other_copy()} is switched on too, showing a notice instead of the add-on")
        _notices.register(_mode)
        return
    _register_full()


def _register_full(preferences: Optional[Dict[str, Any]] = None) -> None:
    """Register the add-on. `preferences` are raw values taken over from the
    legacy copy, see `use_new_version`."""
    global _started
    _started = False
    _alias.install()
    _i18n.register()
    # As an extension, Blender's repository delivers the updates instead
    if not _is_extension():
        addon_updater_ops.register(bl_info)

    _initiate_custom_icons()

    for cls in non_ui_tab_classes:
        bpy.utils.register_class(cls)

    if preferences:
        # The tab name registers the panels again when set, so it comes last
        _notices.apply_preference_values(get_prefs(), preferences, skip=("tab_name",))

    # Main props
    from .backend.properties.scene_main_properties import HG_SETTINGS

    bpy.types.Scene.HG3D = bpy.props.PointerProperty(type=HG_SETTINGS)  # type:ignore
    # Object specific props
    bpy.types.Object.HG = bpy.props.PointerProperty(type=HG_OBJECT_PROPS)  # type:ignore

    for cls in ui_tab_classes:
        # Add custom tab name to class so people can organize their tabs
        cls.bl_category = get_prefs().tab_name
        bpy.utils.register_class(cls)

    _initiate_preview_collections()
    _initiate_ui_lists()

    from .user_interface.batch_panel.primitive_menu import add_hg_primitive_menu

    bpy.types.VIEW3D_MT_add.append(add_hg_primitive_menu)

    livekeys_coll = bpy.props.CollectionProperty(type=BpyLiveKey)  # type:ignore
    bpy.types.WindowManager.livekeys = livekeys_coll

    from .user_interface.setup_overlay.operator import HG_SETUP_PROPS

    bpy.types.WindowManager.hg_setup = bpy.props.PointerProperty(type=HG_SETUP_PROPS)  # type:ignore

    # load handler
    if HG_start not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(HG_start)

    if preferences and preferences.get("tab_name"):
        _notices.apply_preference_values(get_prefs(), {"tab_name": preferences["tab_name"]})

    # Headless runs (tests, render farms) get load_post for their file and
    # need neither the network nor the overlay
    if not bpy.app.background:
        bpy.app.timers.register(_after_register, first_interval=0)


def use_new_version() -> Tuple[bool, str]:
    """The extension next to the legacy add-on: take over every preference of
    the legacy copy, switch it off and register this copy. For the button of
    the "installed twice" notice. Returns (switched, message for the user)."""
    global _mode
    if _mode != "twice":
        return False, "This copy is already in use."
    addons = bpy.context.preferences.addons
    legacy = addons.get(_PUBLIC_NAME)
    values = _notices.preference_values(legacy.preferences) if legacy is not None else {}
    if legacy is not None:
        try:
            bpy.ops.preferences.addon_disable(module=_PUBLIC_NAME)
        except Exception as e:  # noqa: BLE001  its unregister failed half-way
            print("HumGen: the older copy raised while switching off:", repr(e))
        if _PUBLIC_NAME in addons:
            return False, "The older copy could not be switched off. Switch it off in Preferences > Add-ons."
    _notices.forget_legacy_modules()

    folder = values.get("filepath_")
    if isinstance(folder, str) and folder:
        _user_settings.update(content_folder=folder)

    _notices.unregister_preferences()
    try:
        _register_full(values)
    except Exception as e:  # noqa: BLE001
        print("HumGen: could not register after switching off the older copy:", repr(e))
        return False, "Restart Blender to finish switching to the new version."
    _mode = "full"
    if not bpy.app.background:
        try:
            # Otherwise the older copy is switched on again at the next start
            bpy.ops.wm.save_userpref()
        except RuntimeError:
            pass
    return True, "Human Generator now runs as an extension. You can remove the older copy in Preferences > Add-ons."


def _stop_setup() -> None:
    """Stop what the setup runs in the background, so nothing of this copy is
    left running after it is switched off or updated: the overlay and its draw
    handler, the poll timer, the download thread (its partial file is kept for
    a resume) and the timers of the update check."""
    try:
        _setup_operator.shutdown()
    except Exception as e:  # noqa: BLE001
        print("HumGen: could not stop the setup:", repr(e))
    if bpy.app.timers.is_registered(_after_register):
        bpy.app.timers.unregister(_after_register)
    _update_check.stop()


def unregister() -> None:
    _notices.unregister()
    if _mode != "full":
        return
    _stop_setup()
    if not _is_extension():
        addon_updater_ops.unregister()

    for cls in hg_classes:
        bpy.utils.unregister_class(cls)

    # remove handlers
    if HG_start in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(HG_start)
    # The overlay adds its file-load cleanup while it is open
    if _setup_operator.on_load_pre in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_setup_operator.on_load_pre)

    from .user_interface.batch_panel.primitive_menu import add_hg_primitive_menu

    bpy.types.VIEW3D_MT_add.remove(add_hg_primitive_menu)

    # remove pcolls
    for pcoll_item in _preview_collections.values():
        bpy.utils.previews.remove(pcoll_item.pcoll)
    bpy.utils.previews.remove(hg_icons.pop())

    _preview_collections.clear()
    del bpy.types.WindowManager.hg_setup
    _i18n.unregister()
    _alias.uninstall()


if __name__ == "__main__":
    register()
