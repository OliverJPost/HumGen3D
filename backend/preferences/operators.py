# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import os

import bpy
from bpy.types import Operator  # type:ignore
from bpy_extras.io_utils import ImportHelper  # type:ignore
from HumGen3D.backend import get_prefs


class HG_PATHCHANGE(Operator, ImportHelper):
    """Changes the path via file browser popup."""

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
