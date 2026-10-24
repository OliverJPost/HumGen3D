# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from typing import TYPE_CHECKING

import addon_utils  # type:ignore
import bpy

from ...package import addon_package, addon_root

if TYPE_CHECKING:
    from ...backend.preferences.preferences import HG_PREF


def get_prefs() -> "HG_PREF":
    """Get HumGen preferences.

    Returns:
        HG_PREF: HumGen user preferences
    """
    return bpy.context.preferences.addons[addon_package()].preferences  # type: ignore


def get_addon_root() -> str:
    """Get the filepath of the addon root folder in the Blender addons directory.

    Returns:
        str: path of the root directory of the add-on
    """
    return addon_root()


def open_preferences_as_new_window() -> None:
    old_area = bpy.context.area
    old_ui_type = old_area.ui_type

    bpy.context.area.ui_type = "PREFERENCES"
    bpy.context.preferences.active_section = "ADDONS"
    bpy.context.window_manager.addon_support = {"COMMUNITY"}
    bpy.context.window_manager.addon_search = "Human Generator 3D"

    try:
        mod = addon_utils.addons_fake_modules[addon_package()]
        info = addon_utils.module_bl_info(mod)
        info["show_expanded"] = True
    except Exception as e:
        raise e
    finally:
        bpy.ops.screen.area_dupli("INVOKE_DEFAULT")  # type:ignore[call-arg]
        old_area.ui_type = old_ui_type
