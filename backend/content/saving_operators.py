# type:ignore

import os
import platform
import re
import subprocess
import time

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, StringProperty  # type:ignore
from HumGen3D.backend.logging import hg_log
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.common import find_hg_rig
from HumGen3D.human.clothing.add_obj_to_clothing import get_human_from_distance
from HumGen3D.human.human import Human
from HumGen3D.human.keys.keys import update_livekey_collection
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.user_interface.content_panel.operators import (
    refresh_hair_ul,
    refresh_outfit_ul,
)
from HumGen3D.user_interface.documentation.feedback_func import ShowMessageBox

from .possible_content import find_possible_content
from ...human.clothing.saving import has_deform_weights, is_valid_clothing_object
from ...user_interface.panel_functions import draw_paragraph


class HG_OT_START_SAVING_PROCESS(bpy.types.Operator):
    bl_idname = "hg3d.start_saving"
    bl_label = "Save to library"
    bl_description = "Save this item to the Human Generator content library"
    bl_options = {"UNDO"}

    category: StringProperty()
    key_name: StringProperty()

    def execute(self, context):
        cc_sett = context.scene.HG3D.custom_content
        cc_sett.content_saving_ui = True
        cc_sett.content_saving_type = self.category
        if self.category == "key":
            cc_sett.key.key_to_save = self.key_name
        cc_sett.content_saving_tab_index = 0
        cc_sett.content_saving_active_human = find_hg_rig(context.object)
        if self.category == "hair":
            refresh_hair_ul(self, context)
        elif self.category in ("outfit", "footwear"):
            refresh_outfit_ul(context, self.category)
        return {"FINISHED"}


class HG_OT_REFRESH_POSSIBLE_CONTENT(bpy.types.Operator):
    bl_idname = "hg3d.refresh_possible_content"
    bl_label = "Refresh"
    bl_description = "Refresh list of possible content items."
    bl_options = {"UNDO"}

    def execute(self, context):
        find_possible_content(context)
        return {"FINISHED"}


class HG_OT_AUTO_RENDER_THUMB(bpy.types.Operator):
    bl_idname = "hg3d.auto_render_thumbnail"
    bl_label = "Automatic thumbnail"
    bl_description = "Automatic thumbnail"
    bl_options = {"UNDO"}

    thumbnail_type: StringProperty()
    white_material: BoolProperty()

    def execute(self, context):
        cc_sett = context.scene.HG3D.custom_content
        human = Human.from_existing(cc_sett.content_saving_active_human)
        folder = os.path.join(get_prefs().filepath, "temp_data")

        human.render_thumbnail(
            folder,
            focus=self.thumbnail_type,
            context=context,
            white_material=self.white_material,
        )
        return {"FINISHED"}


class HG_OT_SAVE_TO_LIBRARY(bpy.types.Operator):
    bl_idname = "hg3d.save_to_library"
    bl_label = "Save to library"
    bl_description = "Save this item to the Human Generator content library"
    bl_options = {"UNDO"}

    def execute(self, context):
        cc_sett = context.scene.HG3D.custom_content
        category = cc_sett.content_saving_type
        human = Human.from_existing(cc_sett.content_saving_active_human)

        if cc_sett.thumbnail_saving_enum == "last_render":
            thumbnail = bpy.data.images.get("Render Result")
        elif cc_sett.thumbnail_saving_enum == "none":
            thumbnail = None
        else:
            thumbnail = cc_sett.preset_thumbnail

        if getattr(cc_sett, category).existing_or_new_category == "existing":
            subcategory = getattr(cc_sett, category).chosen_existing_subcategory
        else:
            subcategory = getattr(cc_sett, category).new_category_name

        if category == "key":
            key_to_save = cc_sett.key.key_to_save
            key_name = cc_sett.key.name
            key_category = cc_sett.key.category_to_save_to
            as_livekey = key_category != "expressions"
            delete_original = as_livekey and cc_sett.key.delete_original
            pattern = re.compile(
                r"^((?P<category>[^_])[_\{])?((?P<subcategory>.+)\}_)?(?P<name>.*)"  # noqa
            )
            match = pattern.match(key_to_save)
            hg_name = match.groupdict().get("name")
            human.keys[hg_name].save_to_library(
                key_name,
                key_category,
                subcategory,
                as_livekey=as_livekey,
                delete_original=delete_original,
            )
            update_livekey_collection()
        elif category == "pose":
            name = cc_sett.pose.name
            human.pose.save_to_library(name, subcategory, thumbnail, context)
            human.pose.refresh_pcoll()
        elif category == "starting_human":
            human.save_to_library(
                cc_sett.starting_human.name, subcategory, thumbnail, context
            )
        elif category == "hair":
            attr = "regular_hair" if cc_sett.hair.save_type == "head" else "face_hair"
            getattr(human.hair, attr).save_to_library(
                [ps.ps_name for ps in context.scene.savehair_col if ps.enabled],
                cc_sett.hair.name,
                subcategory,
                for_male=cc_sett.hair.save_for_male,
                for_female=cc_sett.hair.save_for_female,
                thumbnail=thumbnail,
                context=context,
            )
            getattr(human.hair, attr).refresh_pcoll(context)
        elif category in ("outfit", "footwear"):
            category_sett = getattr(cc_sett, category)
            enabled = {i.obj_name for i in context.scene.saveoutfit_col if i.enabled}
            objects = [
                obj
                for obj in getattr(human.clothing, category).objects
                if obj.name in enabled
            ]
            if not objects:
                ShowMessageBox("No objects selected to save.", title="HG Clothing")
                return {"CANCELLED"}
            getattr(human.clothing, category).save_to_library(
                category_sett.name,
                for_male=category_sett.save_for_male,
                for_female=category_sett.save_for_female,
                open_when_finished=cc_sett.open_when_finished,
                category=subcategory,
                thumbnail=thumbnail,
                objects=objects,
                context=context,
            )
            getattr(human.clothing, category).refresh_pcoll(context)
        elif category == "texture":
            category_sett = getattr(cc_sett, category)
            human.skin.texture.save_to_library(
                category_sett.name,
                category=subcategory,
                thumbnail=thumbnail,
            )
            human.skin.texture.refresh_pcoll(context)

        cc_sett.content_saving_ui = False
        ShowMessageBox("Successfully saved!", title="HG Content Saving")
        return {"FINISHED"}


class HG_OT_ADD_OBJ_TO_OUTFIT(bpy.types.Operator):
    bl_idname = "hg3d.add_obj_to_outfit"
    bl_label = "Add object to outfit"
    bl_description = "Add object to outfit"

    cloth_type: EnumProperty(
        items=[
            ("torso", "Torso", "", 0),
            ("pants", "Pants", "", 1),
            ("full", "Full Body", "", 2),
            ("footwear", "Footwear", "", 3),
        ],
        default="torso",
    )

    override_weights: BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == "MESH"

    def invoke(self, context, event):
        cloth_object = context.object
        try:
            self.human = get_human_from_distance(cloth_object)
        except HumGenException as e:
            # A parent human wins over the distance check
            self.human = (
                Human.from_existing(cloth_object.parent, strict_check=False)
                if cloth_object.parent
                else None
            )
            if not self.human:
                ShowMessageBox(
                    f"{e} Make sure the object sits on a human. Is this message "
                    "incorrect? Manually parent the object to a human rig.",
                    title="HG Clothing",
                )
                return {"CANCELLED"}

        self.has_valid_vertex_groups = has_deform_weights(
            cloth_object, self.human.objects.rig
        )

        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        obj = context.object
        self._draw_info_labels(context, obj)

        col = self.layout.column()
        col.label(text="What type of clothing is this?")

        col = col.column()
        col.scale_y = 1.5
        col.prop(self, "cloth_type", expand=True)

        if self.has_valid_vertex_groups:
            col = self.layout.column()
            col.label(text="Valid weights found.")
            col.prop(self, "override_weights", text="Recalculate weights")

        col = self.layout.column()
        col.scale_y = 0.8
        col.label(text="Converting takes a few seconds, up to about a minute for")
        col.label(text="dense meshes. The status bar shows the progress.")

    def _draw_info_labels(self, context, obj):
        if "hg_body" in obj:
            col = self.layout.column()
            col.alert = True
            draw_paragraph(
                col,
                """
This object seems to be the body object.

If you made clothing by separating part of the body, you can ignore this message.
If you accidentily selected the body object, please select the clothing object instead.
Press ESC to cancel.
""",
                max_width_percentage=140,
            )
        if "cloth" in obj or "shoe" in obj:
            col = self.layout.column()
            col.alert = True
            if is_valid_clothing_object(context.object):
                draw_paragraph(
                    col,
                    """
It looks like you selected an object which has been previously added as clothing
and fulfills all the requirements to be clothing.
If you want to reset the clothing properties and add it as clothing again, please
continue. Otherwise, press ESC to cancel.
""",
                    max_width_percentage=140,
                )
            else:
                draw_paragraph(
                    col,
                    """
It looks like you selected an object which has been previously added as clothing
but does not fulfill all the requirements to be clothing.
Continuing will reset the clothing properties and add it as clothing again.
NOTE: This will reset weight painting.
Press ESC to cancel.
""",
                    max_width_percentage=140,
                )

    def execute(self, context):
        recalculate_weights = not self.has_valid_vertex_groups or self.override_weights
        # The conversion runs as a modal operator so the interface stays alive
        # and shows progress. A dialog operator cannot become modal itself.
        bpy.ops.hg3d.convert_to_clothing(
            "INVOKE_DEFAULT",
            rig_name=self.human.objects.rig.name,
            cloth_type=self.cloth_type,
            recalculate_weights=recalculate_weights,
        )
        return {"FINISHED"}


class HG_OT_CONVERT_TO_CLOTHING(bpy.types.Operator):
    """Convert the active object to clothing of a human, with a progress bar.

    The conversion is done in short steps on a timer, in between Blender keeps
    responding and redraws the progress bar in the status bar. Esc cancels, the
    object is not changed until the conversion is complete.
    """

    bl_idname = "hg3d.convert_to_clothing"
    bl_label = "Convert to clothing"
    bl_description = "Weight paint the object and add corrective shape keys"
    bl_options = {"UNDO", "INTERNAL"}

    rig_name: StringProperty()
    cloth_type: StringProperty(default="torso")
    recalculate_weights: BoolProperty(default=True)

    # Work per timer tick. Long enough to get work done, short enough to keep
    # the interface fluid.
    _budget = 0.05

    def invoke(self, context, event):
        self.cloth_obj = context.object
        self.human = Human.from_existing(bpy.data.objects[self.rig_name])
        settings = (
            self.human.clothing.footwear
            if self.cloth_type == "footwear"
            else self.human.clothing.outfit
        )
        self._steps = settings.add_obj_steps(
            self.cloth_obj, self.cloth_type, self.recalculate_weights, context
        )
        self._fraction = 0.0
        self._started = time.monotonic()

        # Blender installs this as the draw function of the status bar header,
        # which has to be a plain function, not a method of this operator.
        operator = self

        def draw_status(header, context):
            operator._draw_status(header.layout)

        self._draw_fn = draw_status
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.02, window=context.window)
        wm.modal_handler_add(self)
        context.workspace.status_text_set(self._draw_fn)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC":
            self._finish(context)
            self.report({"INFO"}, "Converting to clothing cancelled")
            return {"CANCELLED"}
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        deadline = time.monotonic() + self._budget
        try:
            while time.monotonic() < deadline:
                self._fraction = max(self._fraction, next(self._steps))
        except StopIteration as finished:
            self._finish(context)
            self._report_result(context, finished.value)
            return {"FINISHED"}
        except Exception as e:  # noqa: BLE001
            self._finish(context)
            self.report({"ERROR"}, f"Converting to clothing failed: {e}")
            return {"CANCELLED"}
        # Redraw, so the status bar shows the new value
        context.workspace.status_text_set(self._draw_fn)
        return {"RUNNING_MODAL"}

    def _draw_status(self, layout):
        layout.separator_spacer()
        row = layout.row(align=True)
        row.ui_units_x = 16
        row.progress(
            text=f"Converting {self.cloth_obj.name} to clothing: {self._fraction:.0%}",
            factor=self._fraction,
            type="BAR",
        )
        layout.label(text="Esc to cancel")
        layout.separator_spacer()

    def _finish(self, context):
        self._steps.close()
        context.window_manager.event_timer_remove(self._timer)
        context.workspace.status_text_set(None)

    def _report_result(self, context, solver):
        seconds = time.monotonic() - self._started
        hg_log(f"Converted {self.cloth_obj.name} in {seconds:.1f}s", level="DEBUG")
        find_possible_content(context)
        message = "Successfully added weight painting and corrective shape keys! This is now a valid clothing object. Save it to the library in the panel below."
        if solver == "closest_point":
            message += " NOTE: Automatic weight painting could not be fully solved for this mesh, check the weights before saving."
        ShowMessageBox(message, title="HG Clothing")


class HG_OT_SAVE_SK(bpy.types.Operator):
    bl_idname = "hg3d.save_sk_to_library"
    bl_label = "Save shapekey to library"
    bl_description = "Saves this shape key to the library as a LiveKey"
    bl_options = {"UNDO"}

    save_type: EnumProperty(
        items=[
            ("shapekey", "Shape key by default", "", 0),
            ("livekey", "LiveKey", "", 1),
        ],
        default="livekey",
    )
    delete_original = BoolProperty(default=False, name="Delete original")

    sk_name: StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout

        layout.label(text="How do you want to save this key?")
        col = layout.column(align=True)
        col.prop(self, "save_type", expand=True)

        if self.save_type == "livekey":
            col.prop(self, "delete_original")

    def execute(self, context):
        human = Human.from_existing(context.object)
        bpy_key = human.objects.body.data.shape_keys.key_blocks[self.sk_name]

        key = next(key for key in human.keys if key.as_bpy() == bpy_key)

        delete_original = self.save_type == "livekey" and self.delete_original
        key.save_to_library(
            as_livekey=self.save_type == "livekey", delete_original=delete_original
        )
        return {"FINISHED"}


class HG_OT_OPEN_FOLDER(bpy.types.Operator):
    """Open the folder that belongs to this section.

    API: False

    Operator type:
        Open subprocess

    Prereq:
        subpath passed
    """

    bl_idname = "hg3d.openfolder"
    bl_label = "Open folder"
    bl_description = "Opens the folder that belongs to this type of content"

    subpath: bpy.props.StringProperty()

    def execute(self, context):
        pref = get_prefs()
        path = os.path.join(pref.filepath, self.subpath)

        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

        return {"FINISHED"}
