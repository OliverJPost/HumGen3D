# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Batch mode for generating multiple humans at once."""

import os
import time

import bpy
from HumGen3D.backend import hg_log
from HumGen3D.backend.preferences.preference_func import get_addon_root
from HumGen3D.human.base.collections import add_to_collection
from HumGen3D.human.base.render import set_eevee_ao_and_strip
from HumGen3D.human.human import Human

from .batch_functions import get_batch_marker_list, has_associated_human
from .generator import BatchHumanGenerator


class HG_OT_ADD_BATCH_MARKER(bpy.types.Operator):
    bl_idname = "hg3d.add_batch_marker"
    bl_label = "Add marker"
    bl_description = "Adds this marker at the 3D cursor location"
    bl_options = {"REGISTER", "UNDO"}

    marker_type: bpy.props.StringProperty()

    def execute(self, context):
        blendfile = os.path.join(
            get_addon_root(),
            "batch_generator",
            "data",
            "hg_batch_markers.blend",
        )

        with bpy.data.libraries.load(blendfile, link=False) as (
            _,
            data_to,
        ):
            data_to.objects = [
                f"HG_MARKER_{self.marker_type.upper()}",
            ]

        # link to scene
        marker = data_to.objects[0]
        context.scene.collection.objects.link(marker)
        add_to_collection(context, marker, collection_name="HG Batch Markers")

        marker.location = context.scene.cursor.location

        marker["hg_batch_marker"] = self.marker_type

        return {"FINISHED"}


def status_text_callback(header, context):
    batch_sett = context.scene.HG3D.batch
    layout = header.layout

    layout.separator_spacer()
    layout.alignment = "EXPAND"

    row = layout.row(align=False)
    row.alignment = "CENTER"

    layout.label(text=f"Building Human {batch_sett.idx}", icon="TIME")

    col = layout.column()
    col.scale_x = 1.6
    col.prop(batch_sett, "progress")

    layout.label(text="Press ESC to cancel", icon="EVENT_ESC")

    layout.separator_spacer()


def set_generator_settings(generator, batch_sett):
    generator.female_chance = batch_sett.female_chance
    generator.male_chance = batch_sett.male_chance
    # TODO generator.human_preset_category_chances
    generator.add_clothing = batch_sett.clothing
    generator.clothing_categories = _choose_category_list()
    generator.add_expression = batch_sett.expression
    generator.add_hair = batch_sett.hair
    generator.hair_quality = batch_sett.hair_quality_particle

    if batch_sett.height_system == "metric":
        avg_height_cm_male = batch_sett.average_height_cm_male
        avg_height_cm_female = batch_sett.average_height_cm_female
    else:
        avg_height_cm_male = (
            batch_sett.average_height_ft_male * 30.48
            + batch_sett.average_height_in_male * 2.54
        )
        avg_height_cm_female = (
            batch_sett.average_height_ft_female * 30.48
            + batch_sett.average_height_in_female * 2.54
        )

    generator.average_height_female = avg_height_cm_male
    generator.average_height_male = avg_height_cm_female

    generator.height_one_standard_deviation = batch_sett.standard_deviation

    generator.texture_resolution = batch_sett.texture_resolution


def _choose_category_list():
    collection = bpy.context.scene.batch_clothing_col

    enabled_categories = [i.library_name for i in collection if i.enabled]
    if not enabled_categories:
        bpy.ops.hg3d.refresh_batch_uilists()

        enabled_categories = [i.library_name for i in collection]

    return enabled_categories


class HG_BATCH_GENERATE(bpy.types.Operator):
    bl_idname = "hg3d.generate"
    bl_label = "Generate"
    bl_description = "Generates specified amount of humans"
    bl_options = {"REGISTER", "UNDO"}

    run_immediately: bpy.props.BoolProperty(default=False)
    show_time_dialog: bpy.props.BoolProperty(default=False)

    def invoke(self, context, event):
        batch_sett = context.scene.HG3D.batch
        self.generate_queue = get_batch_marker_list(context)
        markers_with_associated_human = list(
            filter(has_associated_human, self.generate_queue)
        )

        if self.show_time_dialog:
            self.show_time_dialog = False
            return self.execute(context)

        if len(self.generate_queue) >= 3:
            self.show_time_dialog = True

        if self.run_immediately or not markers_with_associated_human:
            set_eevee_ao_and_strip(context)
            self.generator = BatchHumanGenerator()
            set_generator_settings(self.generator, batch_sett)

            if self.show_time_dialog:
                self.execute_first(context)
                bpy.app.timers.register(
                    lambda: bpy.ops.hg3d.generate(show_time_dialog=True),
                    first_interval=0,
                )
                return {"CANCELLED"}
            else:
                return self.execute(context)
        else:
            self._show_dialog_to_confirm_deleting_humans(context)
            return {"CANCELLED"}

    def execute_first(self, context):
        marker = self.generate_queue[0]
        pose_type = marker["hg_batch_marker"]

        if has_associated_human(marker):
            old_human = Human.from_existing(marker["associated_human"])
            old_human.delete()

        human = self.generator.generate_human(context, pose_type)

        human.location = marker.location
        human.rotation_euler = marker.rotation_euler
        marker["associated_human"] = human.rig_obj

    def execute(self, context):
        for marker in self.generate_queue:
            pose_type = marker["hg_batch_marker"]

            if has_associated_human(marker):
                old_human = Human.from_existing(marker["associated_human"])
                old_human.delete()

            human = self.generator.generate_human(context, pose_type)

            human.location = marker.location
            human.rotation_euler = marker.rotation_euler
            marker["associated_human"] = human.rig_obj

        return {"FINISHED"}

    def _show_dialog_to_confirm_deleting_humans(self, context):  # noqa CCE001
        generate_queue = self.generate_queue

        def draw(self, context):
            layout = self.layout

            nonlocal generate_queue

            for i, marker in enumerate(filter(has_associated_human, generate_queue)):
                layout.label(text=marker["associated_human"].name)

                if i > 9:
                    layout.label(text=f"+ {len(generate_queue) - 10} more")
                    break

            layout.separator()

            layout.operator_context = "INVOKE_DEFAULT"
            layout.operator(
                "hg3d.generate", text="Generate anyway"
            ).run_immediately = True
            return

        context.window_manager.popup_menu(draw, title="This will delete these humans:")


class HG_BATCH_GENERATE_MODAL(bpy.types.Operator):
    bl_idname = "hg3d.generate_modal"
    bl_label = "Generate"
    bl_description = "Generates specified amount of humans"
    bl_options = {"REGISTER", "UNDO"}

    run_immediately: bpy.props.BoolProperty(default=False)

    def __init__(self):
        self.human_idx = 0
        self.generate_queue = get_batch_marker_list(bpy.context)
        self.finish_modal = False
        self.timer = None
        self.start_time = time.time()

    def invoke(self, context, event):
        batch_sett = context.scene.HG3D.batch

        markers_with_associated_human = list(
            filter(has_associated_human, self.generate_queue)
        )

        if self.run_immediately or not markers_with_associated_human:
            self._initiate_modal(context, batch_sett)
            set_eevee_ao_and_strip(context)
            self.generator = BatchHumanGenerator()
            set_generator_settings(self.generator, batch_sett)
            return {"RUNNING_MODAL"}
        else:
            self._show_dialog_to_confirm_deleting_humans(context)
            return {"CANCELLED"}

    def _initiate_modal(self, context, batch_sett):  # noqa
        wm = context.window_manager
        wm.modal_handler_add(self)

        batch_sett.progress = 0

        self.human_idx = 0
        self.timer = wm.event_timer_add(0.01, window=context.window)

        batch_sett.idx = 1
        context.workspace.status_text_set(status_text_callback)
        context.area.tag_redraw()

    def _show_dialog_to_confirm_deleting_humans(self, context):  # noqa CCE001
        generate_queue = self.generate_queue

        def draw(self, context):
            layout = self.layout

            nonlocal generate_queue

            for i, marker in enumerate(filter(has_associated_human, generate_queue)):
                layout.label(text=marker["associated_human"].name)

                if i > 9:
                    layout.label(text=f"+ {len(generate_queue) - 10} more")
                    break

            layout.separator()

            layout.operator_context = "INVOKE_DEFAULT"
            layout.operator(
                "hg3d.generate", text="Generate anyway"
            ).run_immediately = True
            return

        context.window_manager.popup_menu(draw, title="This will delete these humans:")

    def modal(self, context, event):  # noqa CFQ004
        """Event handling."""
        batch_sett = context.scene.HG3D.batch

        if self.finish_modal:
            context.area.tag_redraw()
            context.workspace.status_text_set(text=None)

            batch_sett.idx = 0

            hg_log(
                "Batch modal total running time: ",
                round(time.time() - self.start_time, 2),
                "s",
            )

            return {"FINISHED"}

        elif event.type in ["ESC"]:
            self._cancel(batch_sett, context)

            return {"RUNNING_MODAL"}

        elif event.type == "TIMER":

            # Check if all humans in the list are already generated
            if self.human_idx == len(self.generate_queue):
                self.finish_modal = True
                return {"RUNNING_MODAL"}

            current_marker = self.generate_queue[self.human_idx]

            pose_type = current_marker["hg_batch_marker"]

            human = self.generator.generate_human(context, pose_type)

            human.location = current_marker.location
            human.rotation_euler = current_marker.rotation_euler
            current_marker["associated_human"] = human.rig_obj

            self.human_idx += 1

            if self.human_idx > 0:
                progress = self.human_idx / (len(self.generate_queue))
                batch_sett.progress = int(progress * 100)

            batch_sett.idx += 1

            context.workspace.status_text_set(status_text_callback)

            return {"RUNNING_MODAL"}

        else:
            return {"RUNNING_MODAL"}

    def _delete_old_associated_human(self, marker):
        associated_rig = marker["associated_human"]
        human = Human.from_existing(associated_rig)
        human.delete()

    def _cancel(self, batch_sett, context):
        hg_log("Batch modal is cancelling")
        batch_sett.progress = batch_sett.progress + (100 - batch_sett.progress) / 2.0

        self.finish_modal = True
        context.workspace.status_text_set(status_text_callback)
        return {"CANCELLED"}


class HG_RESET_BATCH_OPERATOR(bpy.types.Operator):
    """Operator for testing bits of code."""

    bl_idname = "hg3d.reset_batch_operator"
    bl_label = "Reset batch operator"
    bl_description = "If an error occured during batch creation, use this to get the purple button back"  # noqa E501
    bl_options = {"UNDO"}

    def execute(self, context):
        context.scene.HG3D.batch_idx = 0
        return {"FINISHED"}
