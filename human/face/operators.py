# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements Blender operators related to facial proportions."""

import bpy

from ..human import Human


class HG_RESET_FACE(bpy.types.Operator):
    """Resets all face deformation values to 0"""

    bl_idname = "hg3d.resetface"
    bl_label = "Reset face"
    bl_description = "Resets all face deformation values to 0"
    bl_options = {"UNDO"}

    def execute(self, context):
        Human.from_existing(context.object).face.reset()
        return {"FINISHED"}
