import os
from pathlib import Path
from sys import platform

import addon_utils  # type:ignore
import bpy
from HumGen3D import bl_info
from HumGen3D.backend import get_prefs

from ...backend.preview_collections import preview_collections
from ...human.human import Human  # type: ignore
from ..panel_functions import (
    draw_panel_switch_header,
    draw_spoiler_box,
    draw_sub_spoiler,
    get_flow,
    searchbox,
)
from ..tips_suggestions_ui import draw_tips_suggestions_ui  # type: ignore
from ..ui_baseclasses import MainPanelPart  # type: ignore


class HG_PT_PANEL(MainPanelPart, bpy.types.Panel):
    """Main Human Generator panel, divided into creation phase and finalize
    phase. These phases are then divided into sections (i.e. hair, body, face)

    One exception is the clothing material section. If a HumGen clothing object
    is selected, this UI shows options to change the material
    """

    bl_idname = "HG_PT_Panel"
    phase_name = "closed"
    menu_titles = [
        "body",
        "length",
        "face",
        "skin",
        "eyes",
        "hair",
        "outfit",
        "footwear",
        "pose",
        "expression",
    ]

    def draw_header(self, context):
        self.draw_panel_switch_header(self.layout, context.scene.HG3D)

    def draw(self, context):
        layout = self.layout
        self.sett = context.scene.HG3D
        self.pref = get_prefs()

        self.human = Human.from_existing(context.active_object, strict_check=False)

        if self.draw_info_and_warning_labels(context):
            return

        self.draw_top_widget(self.human)

        col = layout.column(align=True)
        for menu_title in self.menu_titles:
            draw_spoiler_box(self, col, menu_title)

        if get_prefs().show_tips:
            draw_tips_suggestions_ui(layout, context)
