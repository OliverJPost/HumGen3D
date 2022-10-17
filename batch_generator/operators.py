# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Batch mode for generating multiple humans at once."""

import os
import time

import bpy
from HumGen3D.backend.preferences.preference_func import get_addon_root
from HumGen3D.human.base.collections import add_to_collection
from HumGen3D.human.base.render import set_eevee_ao_and_strip
from HumGen3D.human.human import Human
from HumGen3D.user_interface.documentation.feedback_func import ShowMessageBox

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
    do_timing_run_first: bpy.props.BoolProperty(default=False)
    timing_run_marker: bpy.props.StringProperty()

    def invoke(self, context, event):
        batch_sett = context.scene.HG3D.batch
        self.generate_queue = get_batch_marker_list(context)
        markers_with_associated_human = list(
            filter(has_associated_human, self.generate_queue)
        )

        # Show a dialog asking the user if markers should be overwritten
        if not self.run_immediately and markers_with_associated_human:
            self._show_dialog_to_confirm_deleting_humans(context)
            return {"CANCELLED"}

        set_eevee_ao_and_strip(context)
        self.generator = BatchHumanGenerator()
        set_generator_settings(self.generator, batch_sett)

        # Generate the remaining humans from the timing run
        if self.do_timing_run_first:
            self.do_timing_run_first = False
            return self.execute(context)

        if len(self.generate_queue) < 3:
            return self.execute(context)
        else:
            t = time.time()
            # Generate just one human to get timing
            marker = self.generate_queue[0]
            self._generate_human_for_marker(context, marker)
            t_delta = time.time() - t

            # Show message box with estimated time needed
            len_markers = len(self.generate_queue)
            # For some reason it takes almost twice as long as expected from timing.
            t_total = (len_markers - 1) * t_delta * 2
            t_min = int(t_total // 60)
            t_sec = int(t_total % 60)
            ShowMessageBox(
                (
                    "Generating humans....\n"
                    + f"All {len_markers} humans expected to take {t_min}m {t_sec}s."
                )
            )
            bpy.app.timers.register(
                lambda: bpy.ops.hg3d.generate(
                    do_timing_run_first=True,
                    run_immediately=True,
                    timing_run_marker=marker.name,
                ),
                first_interval=1,
            )
            return {"FINISHED"}

    def execute(self, context):
        # Call invoke if it wasn't run because of the timer
        if not hasattr(self, "generate_queue"):
            self.invoke(context, None)
            # Skip first marker since it was generated during intital run
            marker_obj = bpy.data.objects.get(self.timing_run_marker)
            self.generate_queue.remove(marker_obj)

        for marker in self.generate_queue:
            self._generate_human_for_marker(context, marker)

        ShowMessageBox("Batch Generation Completed!")
        return {"FINISHED"}

    def _generate_human_for_marker(self, context, marker):
        """Generate a new human at the position of this batch marker.

        Uses self.generator
        """
        pose_type = marker["hg_batch_marker"]

        if has_associated_human(marker):
            old_human = Human.from_existing(marker["associated_human"])
            old_human.delete()

        human = self.generator.generate_human(context, pose_type)

        human.location = marker.location
        human.rotation_euler = marker.rotation_euler
        marker["associated_human"] = human.rig_obj

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
