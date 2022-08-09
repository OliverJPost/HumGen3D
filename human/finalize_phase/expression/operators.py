from pathlib import Path

import bpy
from HumGen3D.backend import hg_delete, remove_broken_drivers, get_prefs
from HumGen3D.human.base.drivers import build_driver_dict

from HumGen3D.human.human import Human


class HG_REMOVE_SHAPEKEY(bpy.types.Operator):
    """Removes the corresponding shapekey

    Operator type
        Shapekeys

    Prereq:
        shapekey str passed
        active object is part of HumGen human

    Args:
        shapekey (str): name of shapekey to remove
    """

    bl_idname = "hg3d.removesk"
    bl_label = "Remove this shapekey"
    bl_description = "Remove this shapekey"
    bl_options = {"UNDO"}

    shapekey: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        hg_rig = Human.from_existing(context.active_object).rig_obj
        hg_body = hg_rig.HG.body_obj

        sk_delete = hg_body.data.shape_keys.key_blocks[self.shapekey]
        hg_body.shape_key_remove(sk_delete)

        return {"FINISHED"}


class HG_ADD_FRIG(bpy.types.Operator):
    """Adds the facial rig to this human, importing the necessary shapekeys

    Operator type:
        Facial rig
        Shapekeys

    Prereq:
        Active object is part of HumGen human
        Human doesn't already have a facial rig
    """

    bl_idname = "hg3d.addfrig"
    bl_label = "Add facial rig"
    bl_description = "Adds facial rig"
    bl_options = {"UNDO"}

    def execute(self, context):
        human = Human.from_existing(context.object)
        human.finalize_phase.expression.load_facial_rig()
        return {"FINISHED"}


class HG_REMOVE_FRIG(bpy.types.Operator):
    """Removes the facial rig, including its shapekeys

    Operator type:
        Facial rig
        Shapekeys

    Prereq:
        Active object is part of HumGen human
        Human has a facial rig loaded
    """

    bl_idname = "hg3d.removefrig"
    bl_label = "Remove facial rig"
    bl_description = "Remove facial rig"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        human = Human.from_existing(context.object)
        human.finalize_phase.expression.remove_facial_rig()
        return {"FINISHED"}
