# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import os
from pathlib import Path

import bpy
import HumGen3D


def get_prefs() -> bpy.types.AddonPreferences:
    """Get HumGen preferences

    Returns:
        AddonPreferences: HumGen user preferences
    """
    addon_name = "HumGen3D"

    return bpy.context.preferences.addons[addon_name].preferences


def get_addon_root() -> str:
    """Get the filepath of the addon root folder in the Blender addons directory

    Returns:
        str: path of the root directory of the add-on
    """

    return os.path.dirname(os.path.abspath(HumGen3D.__file__))
