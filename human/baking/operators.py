# TODO document

"""
Texture baking operators
"""

import os
from pathlib import Path

import bpy
from HumGen3D.backend import get_prefs, hg_log
from HumGen3D.human.base.exceptions import HumGenException
from HumGen3D.human.human import Human
from HumGen3D.user_interface.documentation.feedback_func import ShowMessageBox  # type: ignore


def status_text_callback(header, context):
    bake_sett = context.scene.HG3D.bake
    layout = header.layout

    layout.separator_spacer()
    layout.alignment = "EXPAND"

    row = layout.row(align=False)
    row.alignment = "CENTER"

    layout.label(
        text=f"Rendering texture {bake_sett.idx}/{bake_sett.total}",
        icon="TIME",
    )

    col = layout.column()
    col.scale_x = 1.6
    col.prop(bake_sett, "progress")

    layout.label(text="Press ESC to cancel", icon="EVENT_ESC")

    layout.separator_spacer()


# TODO progress bar
class HG_BAKE(bpy.types.Operator):
    """Bake all textures"""

    bl_idname = "hg3d.bake"
    bl_label = "Bake"
    bl_description = "Bake all textures"
    bl_options = {"UNDO"}

    def __init__(self):
        self.timer = None
        self.bake_idx = 0
        self.image_dict = {}
        self.finish_modal = False

    def invoke(self, context, event):
        self.human = Human.from_existing(context.object)
        self.baketextures = self.human.baking.get_baking_list()

        bake_sett = context.scene.HG3D.bake
        bake_sett.total = len(self.baketextures)
        bake_sett.idx = 1

        (
            cancelled,
            self.switched_to_cuda,
            self.old_samples,
            _,
        ) = self.human.baking._check_bake_render_settings(
            context, samples=int(bake_sett.samples), force_cycles=False
        )

        if cancelled:
            return {"FINISHED"}

        wm = context.window_manager
        wm.modal_handler_add(self)

        self.timer = wm.event_timer_add(0.01, window=context.window)
        context.workspace.status_text_set(status_text_callback)

        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        bake_sett = context.scene.HG3D.bake

        if self.finish_modal:
            self.human.baking.set_up_new_materials(self.baketextures)
            context.area.tag_redraw()
            context.workspace.status_text_set(text=None)
            bake_sett.idx = 0

            if self.switched_to_cuda:
                context.preferences.addons[
                    "cycles"
                ].preferences.compute_device_type = "OPTIX"

            context.scene.cycles.samples = self.old_samples

            return {"FINISHED"}

        elif event.type in ["ESC"]:
            hg_log("Cancelling baking modal")

            self.finish_modal = True
            return {"RUNNING_MODAL"}

        elif event.type == "TIMER":
            if self.bake_idx == bake_sett.total:
                self.finish_modal = True
                return {"RUNNING_MODAL"}

            baketexture = self.baketextures[self.bake_idx - 1]

            self.human.baking.bake_single_texture(baketexture)
            self.bake_idx += 1
            bake_sett.idx += 1

            if self.bake_idx > 0:
                progress = self.bake_idx / bake_sett.total
                bake_sett.progress = int(progress * 100)

            context.workspace.status_text_set(status_text_callback)
            return {"RUNNING_MODAL"}

        else:
            return {"RUNNING_MODAL"}