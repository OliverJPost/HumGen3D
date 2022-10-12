# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy
from HumGen3D.backend import get_prefs
from HumGen3D.human.human import Human
from HumGen3D.user_interface.icons.icons import get_hg_icon
from HumGen3D.user_interface.ui_baseclasses import HGPanel, draw_icon_title

from ..documentation.tips_suggestions_ui import draw_tips_suggestions_ui  # type: ignore
from ..panel_functions import draw_panel_switch_header, draw_paragraph, get_flow


class HG_PT_CONTENT(HGPanel, bpy.types.Panel):
    """Panel with extra functionality for HumGen that is not suitable for the
    main panel. Things like content pack creation, texture baking etc.

    Args:
        Tools_PT_Base (class): Adds bl_info and commonly used tools
    """

    bl_idname = "HG_PT_CONTENT"
    bl_label = "Content"

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False

        sett = context.scene.HG3D  # type:ignore[attr-defined]
        return sett.ui.active_tab == "CONTENT" and not sett.ui.content_saving

    def draw_header(self, context):
        draw_panel_switch_header(
            self.layout, context.scene.HG3D
        )  # type:ignore[attr-defined]

    def draw(self, context):
        layout = self.layout

        col = layout.column()

        row = col.row(align=True)
        row.scale_x = 0.7
        row.alignment = "CENTER"
        draw_icon_title("Custom Content", row, True)
        draw_paragraph(
            col,
            "Save and share your custom content.",
            alignment="CENTER",
            enabled=False,
        )
        if not get_prefs().filepath:
            layout.alert = True
            layout.label(text="No filepath selected", icon="ERROR")
            return

        human = Human.from_existing(context.object, strict_check=False)
        if not human:
            box = col.box()
            message = "No human selected, select a human to see greyed out options."
            draw_paragraph(box, message, alignment="CENTER")


class HG_PT_ADD_TO_HUMAN(HGPanel, bpy.types.Panel):
    bl_parent_id = "HG_PT_CONTENT"
    bl_idname = "HG_PT_ADD_TO_HUMAN"
    bl_label = "Add to human"

    def draw_header(self, context) -> None:
        self.layout.label(icon="COMMUNITY")

    def draw(self, context):
        subcol = self.layout.column()
        subcol.scale_y = 1.5
        subcol.operator(
            "hg3d.add_obj_to_outfit",
            text="Add object as clothing",
            icon_value=get_hg_icon("clothing"),
        )


class HG_PT_SAVE_TO_LIBRARY(HGPanel, bpy.types.Panel):
    bl_parent_id = "HG_PT_CONTENT"
    bl_idname = "HG_PT_SAVE_TO_LIBRARY"
    bl_label = "Save to library"

    def draw_header(self, context) -> None:
        self.layout.label(icon_value=get_hg_icon("custom_content"))

    def draw(self, context):
        self.layout.enabled = bool(Human.find_hg_rig(context.object))

        col = self.layout.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.2
        row.operator(
            "hg3d.refresh_possible_content", text="Refresh list", icon="FILE_REFRESH"
        )
        row.prop(
            context.scene.HG3D.custom_content,
            "show_unchanged",
            toggle=True,
            icon_only=True,
            icon="HIDE_OFF",
        )

        amount_of_items = len(context.scene.possible_content_col)
        col.template_list(
            "HG_UL_POSSIBLE_CONTENT",
            "",
            context.scene,
            "possible_content_col",
            context.scene,
            "possible_content_col_index",
            rows=amount_of_items if amount_of_items <= 15 else 15,
            sort_lock=True,
        )


class HG_PT_EXTRAS_TIPS(HGPanel, bpy.types.Panel):
    bl_parent_id = "HG_PT_CONTENT"
    bl_label = "Tips and suggestions!"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return get_prefs().show_tips

    def draw(self, context):
        layout = self.layout

        draw_tips_suggestions_ui(layout, context)
        if get_prefs().full_height_menu:
            layout.separator(factor=200)
