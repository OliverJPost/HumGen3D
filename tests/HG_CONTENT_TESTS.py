import os
import time

import bpy

from ..blender_operators.common.HG_COMMON_FUNC import hg_delete, hg_log


class HG_CONTENT_TESTS(bpy.types.Operator):
    bl_idname = "hg3d.content_tests"
    bl_label = "Test installed contents"
    bl_description = (
        "Function for devs to check for errors with installed content"
    )
    bl_options = {"UNDO", "REGISTER"}

    def execute(self, context):
        start_time = time.perf_counter()
        hg_log("Starting content tests")
        self.test_starting_humans(context)

        # TODO other tests
        total_time = time.perf_counter() - start_time
        hg_log(f"Finished all content tests, took {total_time}")

        return {"FINISHED"}

    def test_starting_humans(self, context):
        """Creates all starting humans in the content packs folder and deletes
        them again. Does not run when there are already humans in the scene"""
        assert not [obj for obj in bpy.data.objects if obj.HG.ishuman]

        bpy.ops.hg3d.deselect()
        context.scene.HG3D.gender = "female"
        self.__create_all_starting_humans(context)

        context.scene.HG3D.gender = "male"
        self.__create_all_starting_humans(context)

    def __create_all_starting_humans(self, context):
        pcoll_list = context.scene.HG3D["previews_list_humans"]

        for item_name in pcoll_list:
            context.scene.HG3D.pcoll_humans = item_name
            bpy.ops.hg3d.startcreation()

            human = next(obj for obj in bpy.data.objects if obj.HG.ishuman)

            for child in human.children:
                hg_delete(child)
            hg_delete(human)
