import bpy


class HG_UTILITY_TESTS(bpy.types.Operator):
    bl_idname = "hg3d.utility_tests"
    bl_label = "Utility tests"
    bl_description = ""
    bl_options = {"UNDO", "REGISTER"}

    def execute(self, context):
        raise NotImplementedError
        return {"FINISHED"}
