# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy

from HumGen3D import HumGenException
from HumGen3D.backend import hg_delete, hg_log
from HumGen3D.common.collections import add_to_collection
from HumGen3D.common.drivers import build_driver_dict
from HumGen3D.human.human import Human
from HumGen3D.user_interface.documentation.feedback_func import ShowMessageBox

RIGIFY_ERROR = "Rigify addon not enabled. Please enable it in Blender preferences."


class HG_RIGIFY(bpy.types.Operator):
    """Changes the rig to make it compatible with Rigify, then generates the rig

    Operator type:
        Pose
        Rigify

    Prereq:
        Active object is part of HumGen human
        Human still has normal rig
    """

    bl_idname = "hg3d.rigify"
    bl_label = "Generate Rigify Rig"
    bl_description = "Generates a Rigify rig for this human"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        human = Human.from_existing(context.active_object)
        try:
            human.pose.rigify.generate(context=context)
        except HumGenException as e:
            if str(e) != RIGIFY_ERROR:
                raise

            ShowMessageBox(RIGIFY_ERROR, "Error", "ERROR")
            self.report({"ERROR"}, RIGIFY_ERROR)
            return {"CANCELLED"}

        return {"FINISHED"}
