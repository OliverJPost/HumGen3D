# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE


import bpy
from HumGen3D.backend import get_prefs

from ...human.human import Human  # type: ignore
from ..documentation.tips_suggestions_ui import draw_tips_suggestions_ui  # type: ignore
from ..panel_functions import draw_panel_switch_header, draw_spoiler_box
from ..ui_baseclasses import MainPanelPart  # type: ignore


class HG_PT_PANEL(MainPanelPart, bpy.types.Panel):
    """Main Human Generator panel, divided into sections.

    One exception is the clothing material section. If a HumGen clothing object
    is selected, this UI shows options to change the material
    """

    bl_idname = "HG_PT_Panel"
    phase_name = "closed"
    menu_titles = [
        "body",
        "age",
        "face",
        "height",
        "skin",
        "hair",
        "clothing",
        "pose",
        "expression",
    ]

    def draw_header(self, context):
        draw_panel_switch_header(
            self.layout, context.scene.HG3D
        )  # type:ignore[attr-defined]

    def draw(self, context):
        layout = self.layout
        self.sett = context.scene.HG3D  # type:ignore[attr-defined]
        self.pref = get_prefs()

        self.human = Human.from_existing(context.active_object, strict_check=False)

        if self.draw_info_and_warning_labels(context):
            return

        col = self.layout.column(align=True)
        self.draw_top_widget(col, self.human)

        col = layout.column(align=True)
        for menu_title in self.menu_titles:
            draw_spoiler_box(self, col, menu_title)

        if get_prefs().show_tips:
            draw_tips_suggestions_ui(layout, context)
