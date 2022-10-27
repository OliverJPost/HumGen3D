# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

# TODO document

"""Texture baking operators."""


import uuid

import bpy
from HumGen3D.backend import hg_log
from HumGen3D.common.collections import add_to_collection
from HumGen3D.human.human import Human
from mathutils import Vector


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


class HG_OT_PROCESS(bpy.types.Operator):
    bl_idname = "hg3d.process"
    bl_label = "Process"
    bl_description = "Process according to these settings."
    bl_options = {"UNDO"}

    def execute(self, context):  # noqa
        pr_sett = context.scene.HG3D.process
        human_rigs = Human.find_multiple_in_list(context.selected_objects)
        for rig_obj in human_rigs:
            human = Human.from_existing(rig_obj)
            if pr_sett.output != "replace":
                human = human.duplicate(context)
                human.location += Vector((0, 2, 0))
                for obj in human.objects:
                    add_to_collection(context, obj, "Processing Results")

            if pr_sett.bake:
                human.process.baking.bake_all(
                    int(context.scene.HG3D.bake.samples), context
                )

            if pr_sett.lod_enabled:
                human.process.lod.set_body_lod(int(pr_sett.lod.body_lod))
                human.process.lod.set_clothing_lod(
                    pr_sett.lod.decimate_ratio,
                    pr_sett.lod.remove_clothing_subdiv,
                    pr_sett.lod.remove_clothing_solidify,
                )

            if pr_sett.output == "export":
                pass  # TODO export

        return {"FINISHED"}


class HG_OT_ADD_LOD_OUTPUT(bpy.types.Operator):
    bl_idname = "hg3d.add_lod_output"
    bl_label = "Add LOD output."
    bl_description = "Adds a new output item for LODs."
    bl_options = {"UNDO"}

    def execute(self, context):
        coll = context.scene.lod_output_col

        last_item = coll[-1] if coll else None
        item = coll.add()
        item.name = str(uuid.uuid4())
        if last_item and last_item.suffix[-1].isdigit():
            new_index = int(last_item.suffix[-1]) + 1
            item.suffix = f"_LOD{new_index}"

        return {"FINISHED"}


class HG_OT_REMOVE_LOD_OUTPUT(bpy.types.Operator):
    bl_idname = "hg3d.remove_lod_output"
    bl_label = "Remove LOD output."
    bl_description = "Remove this output from the list."
    bl_options = {"UNDO"}

    name: bpy.props.StringProperty()

    def execute(self, context):
        item = context.scene.lod_output_col.find(self.name)
        context.scene.lod_output_col.remove(item)
        return {"FINISHED"}


# TODO progress bar
class HG_BAKE(bpy.types.Operator):
    """Bake all textures."""

    bl_idname = "hg3d.bake"
    bl_label = "Bake"
    bl_description = "Bake all textures"
    bl_options = {"UNDO"}

    def __init__(self):
        """Init"""
        self.timer = None
        self.bake_idx = 0
        self.image_dict = {}
        self.finish_modal = False

    def invoke(self, context, event):
        self.human = Human.from_existing(context.object)
        self.baketextures = self.human.process.baking.get_baking_list()

        bake_sett = context.scene.HG3D.bake
        bake_sett.total = len(self.baketextures)
        bake_sett.idx = 1

        (
            cancelled,
            self.switched_to_cuda,
            self.old_samples,
            _,
        ) = self.human.process.baking._check_bake_render_settings(
            context, samples=int(bake_sett.samples), force_cycles=False
        )

        if cancelled:
            return {"FINISHED"}

        wm = context.window_manager
        wm.modal_handler_add(self)

        self.timer = wm.event_timer_add(0.01, window=context.window)
        context.workspace.status_text_set(status_text_callback)

        return {"RUNNING_MODAL"}

    def modal(self, context, event):  # noqa CCR001
        bake_sett = context.scene.HG3D.bake

        if self.finish_modal:
            self.human.process.baking.set_up_new_materials(self.baketextures)
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

            self.human.process.baking.bake_single_texture(baketexture)
            self.bake_idx += 1
            bake_sett.idx += 1

            if self.bake_idx > 0:
                progress = self.bake_idx / bake_sett.total
                bake_sett.progress = int(progress * 100)

            context.workspace.status_text_set(status_text_callback)
            return {"RUNNING_MODAL"}

        else:
            return {"RUNNING_MODAL"}
