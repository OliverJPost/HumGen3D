# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import os
from typing import TYPE_CHECKING

import bpy
import HumGen3D

if TYPE_CHECKING:
    from HumGen3D.backend.preferences.preferences import HG_PREF


def get_prefs() -> "HG_PREF":
    """Get HumGen preferences.

    Returns:
        HG_PREF: HumGen user preferences
    """
    addon_name = "HumGen3D"

    return bpy.context.preferences.addons[addon_name].preferences  # type: ignore


def get_addon_root() -> str:
    """Get the filepath of the addon root folder in the Blender addons directory.

    Returns:
        str: path of the root directory of the add-on
    """
    return os.path.dirname(os.path.abspath(HumGen3D.__file__))  # type: ignore
