from pathlib import Path
import bpy


def get_prefs() -> bpy.types.AddonPreferences:
    """Get HumGen preferences

    Returns:
        AddonPreferences: HumGen user preferences
    """
    addon_name = "HumGen3D"

    return bpy.context.preferences.addons[addon_name].preferences

def get_addon_root(self) -> str:
    """Get the filepath of the addon root folder in the Blender addons directory

    Returns:
        str: path of the root directory of the add-on
    """

    root_folder = Path(__file__).parent.parent.parent.parent.absolute()  # TODO

    return str(root_folder)