"""
Operator and corresponding functions for finishing the cration phase
"""

import bpy  # type: ignore

from ...backend.preference_func import get_prefs
from ...backend.preview_collections import refresh_pcoll
from ...user_interface.info_popups import HG_OT_INFO
from ..human import Human


class HG_FINISH_CREATION(bpy.types.Operator):
    """Finish the creation phase, going over:
        -applying body and face shapekeys
        -removing unused eyebrow styles
        -applying the length to the rig
        -correcting the origin after length change
        -adding a backup human for reverting to creation phase
        -changing constraints for posing
        -removing stretch bones
        -probably more

    Operator type:
        HumGen phase change

    Prereq:
        Active object is part of a HumGen human
        That human is in creation phase
    """

    bl_idname = "hg3d.finishcreation"
    bl_label = "Click to confirm. You can't go back to previous tabs"
    bl_description = "Complete creation phase, moving on to finalizing phase"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        pref = get_prefs()

        if pref.show_confirmation:
            return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        human = Human.from_existing(context.object)
        children_hide_state = human.hair.children_ishidden
        human.creation_phase.finish(context)
        if children_hide_state:
            self.report(
                {"INFO"},
                "Hair children were hidden to improve performance. This can be turned off in preferences",
            )
            if get_prefs().auto_hide_popup:
                HG_OT_INFO.ShowMessageBox(None, "autohide_hair")

        return {"FINISHED"}

        pref = get_prefs()

        hg_rig = human.rig_obj
        hg_rig.select_set(True)
        hg_rig.hide_set(False)
        hg_rig.hide_viewport = False
        bpy.context.view_layer.objects.active = hg_rig
        HG = hg_rig.HG
        hg_body = HG.body_obj

        for obj in context.selected_objects:
            if obj != hg_rig:
                obj.select_set(False)

        # TODO common func this

        finish_creation_phase(self, context, hg_rig, hg_body)
        hg_rig.HG.phase = "clothing"

        if not pref.auto_hide_hair_switch:
            for mod in [
                m for m in hg_body.modifiers if m.type == "PARTICLE_SYSTEM"
            ]:
                ps_sett = mod.particle_system.settings
                ps_sett.child_nbr = ps_sett.rendered_child_count

        return {"FINISHED"}
