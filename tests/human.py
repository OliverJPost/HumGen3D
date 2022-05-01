import bpy


class HG_HUMAN_TESTS(bpy.types.Operator):
    bl_idname = "hg3d.main_operator_tests"
    bl_label = "Main operator tests"
    bl_description = ""
    bl_options = {"UNDO", "REGISTER"}

    def execute(self, context):
        return {"FINISHED"}
