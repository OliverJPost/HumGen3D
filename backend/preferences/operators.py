import os

import bpy
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper
from HumGen3D.backend.preferences import get_prefs


class HG_PATHCHANGE(Operator, ImportHelper):
    """
    Changes the path via file browser popup

    Operator Type:
        -Preferences
        -Prop setter
        -Path selection

    Prereq:
        None
    """

    bl_idname = "hg3d.pathchange"
    bl_label = "Change Path"
    bl_description = "Change the install path"

    def execute(self, context):
        pref = get_prefs()

        pref.filepath = os.path.join(
            os.path.dirname(self.filepath), ""
        )  # use join to get slash at the end
        pref.pref_tabs = "cpacks"
        pref.pref_tabs = "settings"

        bpy.ops.wm.save_userpref()
        return {"FINISHED"}
