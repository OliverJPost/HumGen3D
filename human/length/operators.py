import bpy
import random


class HG_RANDOM_LENGTH(bpy.types.Operator):
    """Randomizes the length of the human between an even range of 150-200

    Operator type:
        Length

    Prereq:
        Active object is part of a HumGen human
    """

    bl_idname = "hg3d.randomlength"
    bl_label = "Random Length"
    bl_description = "Random Length"
    bl_options = {"UNDO"}

    def execute(self, context):
        sett = context.scene.HG3D
        sett.human_length = random.randrange(150, 200)
        return {"FINISHED"}
