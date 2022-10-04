# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""
Inactive file to be implemented later, batch mode for generating multiple
humans at once
"""

import json
import os
import random
import subprocess
import time
from pathlib import Path

import bpy
from HumGen3D.API import BatchHumanGenerator
from HumGen3D.backend import hg_log, hg_delete
from HumGen3D.human.base.render import set_eevee_ao_and_strip
from HumGen3D.backend.preferences.preference_func import get_addon_root
from HumGen3D.human.base.collections import add_to_collection

from .batch_functions import get_batch_marker_list, has_associated_human


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


class HG_BATCH_GENERATE(bpy.types.Operator):  # ), HG_CREATION_BASE):
    """
    clears searchfield INACTIVE
    """

    bl_idname = "hg3d.generate"
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

            return {"RUNNING_MODAL"}
        else:
            self._show_dialog_to_confirm_deleting_humans(context)
            return {"CANCELLED"}

    def _initiate_modal(self, context, batch_sett):
        wm = context.window_manager
        wm.modal_handler_add(self)

        batch_sett.progress = 0

        self.human_idx = 0
        self.timer = wm.event_timer_add(0.01, window=context.window)

        batch_sett.idx = 1
        context.workspace.status_text_set(status_text_callback)
        context.area.tag_redraw()

    def _show_dialog_to_confirm_deleting_humans(self, context):
        generate_queue = self.generate_queue

        def draw(self, context):
            layout = self.layout

            nonlocal generate_queue

            i = 0
            for marker in filter(has_associated_human, generate_queue):
                layout.label(text=marker["associated_human"].name)
                i += 1

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

    def modal(self, context, event):
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
            if has_associated_human(current_marker):
                self._delete_old_associated_human(current_marker)

            pose_type = current_marker["hg_batch_marker"]

            generator = self._create_generator_instance(batch_sett)
            result = generator.generate_in_background(
                context=context,
                gender=str(
                    random.choices(
                        ("male", "female"),
                        weights=(batch_sett.male_chance, batch_sett.female_chance),
                        k=1,
                    )[0]
                ),
                ethnicity=str(
                    random.choices(
                        ("caucasian", "black", "asian"),
                        weights=(
                            batch_sett.caucasian_chance,
                            batch_sett.black_chance,
                            batch_sett.asian_chance,
                        ),
                        k=1,
                    )[0]
                ),
                add_hair=batch_sett.hair,
                hair_type="particle",  # sett.batch_hairtype,
                hair_quality=getattr(
                    batch_sett, f"hair_quality_particle"
                ),  # {sett.batch_hairtype}'),
                add_expression=batch_sett.expression,
                expression_category=self._choose_category_list(context, "expressions"),
                add_clothing=batch_sett.clothing,
                clothing_category=self._choose_category_list(context, "outfits"),
                pose_type=pose_type,
            )
            # FIXME repair return
            # if not result:
            #     self._cancel(sett, context)
            #     return {"RUNNING_MODAL"}
            # else:
            hg_rig = result  # result.rig_object

            hg_rig.location = current_marker.location
            hg_rig.rotation_euler = current_marker.rotation_euler
            current_marker["associated_human"] = hg_rig

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
        associated_human = marker["associated_human"]
        for child in associated_human.children[:]:
            hg_delete(child)
        hg_delete(associated_human)

    def _cancel(self, batch_sett, context):
        hg_log("Batch modal is cancelling")
        batch_sett.progress = batch_sett.progress + (100 - batch_sett.progress) / 2.0

        self.finish_modal = True
        context.workspace.status_text_set(status_text_callback)
        return {"CANCELLED"}

    def _choose_category_list(self, context, pcoll_name):

        # TODO fix naming inconsistency
        label = "expressions" if pcoll_name == "expressions" else "clothing"

        collection = getattr(context.scene, f"batch_{label}_col")

        enabled_categories = [i.library_name for i in collection if i.enabled]
        if not enabled_categories:
            bpy.ops.hg3d.refresh_batch_uilists()

            enabled_categories = [i.library_name for i in collection]

        return random.choice(enabled_categories)

    def _create_generator_instance(self, batch_sett):
        q_names = [
            "delete_backup",
            "apply_shapekeys",
            "apply_armature_modifier",
            "remove_clothing_subdiv",
            "remove_clothing_solidify",
            "apply_clothing_geometry_masks",
            "texture_resolution",
        ]

        quality_dict = {name: getattr(batch_sett, name) for name in q_names}

        generator = BatchHumanGenerator(**quality_dict)

        return generator


class HG_RESET_BATCH_OPERATOR(bpy.types.Operator):
    """Operator for testing bits of code"""

    bl_idname = "hg3d.reset_batch_operator"
    bl_label = "Reset batch operator"
    bl_description = "If an error occured during batch creation, use this to get the purple button back"
    bl_options = {"UNDO"}

    def execute(self, context):
        context.scene.HG3D.batch_idx = 0
        return {"FINISHED"}
