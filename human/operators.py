import bpy
from .human import Human


class HG_START_CREATION(bpy.types.Operator):
    """Imports human, setting the correct custom properties.

    Operator type:
        Object importer
        Prop setter
        Material

    Prereq:
        Starting human selected in humans preview collection
    """

    bl_idname = "hg3d.startcreation"
    bl_label = "Generate New Human"
    bl_description = "Generate a new human"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.scene.HG3D.pcoll.humans != "none"
            or context.scene.HG3D.ui.active_tab == "BATCH"
        )

    def execute(self, context):
        sett = context.scene.HG3D
        sett.ui.phase = "closed"

        human = Human.from_preset(sett.pcoll.humans, context)
        hg_rig = human.rig_obj
        hg_rig.select_set(True)
        context.view_layer.objects.active = hg_rig

        self.report({"INFO"}, "You've created: {}".format(human.name))

        return {"FINISHED"}
