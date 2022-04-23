import bpy


class HG_API_TESTS(bpy.types.Operator):
    bl_idname = "hg3d.api_tests"
    bl_label = "API tests"
    bl_description = ""
    bl_options = {"UNDO", "REGISTER"}

    def execute(self, context):
        raise NotImplementedError
        return {"FINISHED"}
