import bpy


def get_prefs() -> bpy.types.AddonPreferences:
    """Get HumGen preferences

    Returns:
        AddonPreferences: HumGen user preferences
    """
    addon_name = "HumGen3D"

    return bpy.context.preferences.addons[addon_name].preferences
