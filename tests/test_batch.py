import random

import bpy


class HG_BATCH_TESTS(bpy.types.Operator):
    bl_idname = "hg3d.batch_tests"
    bl_label = "Batch tests"
    bl_description = ""
    bl_options = {"UNDO", "REGISTER"}

    def execute(self, context):
        self.add_markers(context)

        self.test_height_variation(context)

        bpy.ops.hg3d.generate("INVOKE_DEFAULT", run_immediately=True)

        sett = context.scene.HG3D
        sett.batch_hair = True
        sett.batch_clothing = True
        sett.batch_expression = True

        bpy.ops.hg3d.generate("INVOKE_DEFAULT", run_immediately=True)

        sett.batch_delete_backup = False
        sett.batch_apply_shapekeys = False
        sett.batch_remove_clothing_subdiv = False

        bpy.ops.hg3d.generate("INVOKE_DEFAULT", run_immediately=True)

        return {"FINISHED"}

    def add_markers(self, context):
        bpy.ops.hg3d.add_batch_marker(marker_type="standing_around")
        bpy.ops.hg3d.add_batch_marker(marker_type="a_pose")
        bpy.ops.hg3d.add_batch_marker(marker_type="t_pose")

        for marker in [o for o in bpy.data.objects if "hg_batch_marker" in o]:
            x = random.uniform(-10, 10)
            y = random.uniform(-10, 10)
            z = random.uniform(-10, 10)
            marker.location = x, y, z

    def test_height_variation(self, context):
        sett = context.scene.HG3D
        sett.batch_height_system = "imperial"
        sett.batch_height_system = "metric"
        sett.batch_average_height_cm_male = 180
        sett.batch_standard_deviation = 3
