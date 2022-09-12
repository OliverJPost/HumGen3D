"""
Operators and functions to be used by the developer and content pack creators
"""

import bpy
from HumGen3D.human.human import Human
from mathutils import Matrix


# REMOVE
class HG_TESTOP(bpy.types.Operator):
    """Operator for testing bits of code"""

    bl_idname = "hg3d.testop"
    bl_label = "Test"
    bl_description = "Empty operator used for internal testing"
    bl_options = {"UNDO"}

    def execute(self, context):
        return {"FINISHED"}


class HG_RESET_BATCH_OPERATOR(bpy.types.Operator):
    """Operator for testing bits of code"""

    bl_idname = "hg3d.reset_batch_operator"
    bl_label = "Reset batch operator"
    bl_description = "If an error occured during batch creation, use this to get the purple button back"
    bl_options = {"UNDO"}

    def execute(self, context):
        context.scene.HG3D.batch_idx = 0
        return {"FINISHED"}
