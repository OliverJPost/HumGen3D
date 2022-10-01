# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy

from ..ui_baseclasses import MainPanelPart, subpanel_draw


class ClothingPanel(MainPanelPart):
    @subpanel_draw
    def draw(self, context):
        """draws a template_icon_view for adding outfits"""

        category = self.phase_name

        col = self.layout.column(align=True)

        self.searchbox(self.sett, category, col)

        row = col.row(align=True)
        row.template_icon_view(
            self.sett.pcoll, category, show_labels=True, scale=8.4, scale_popup=6
        )

        row_h = col.row(align=True)
        row_h.scale_y = 1.5

        row_h.prop(self.sett.pcoll, f"{category}_category", text="")
        row_h.operator(
            "hg3d.random_choice", text="Random", icon="FILE_REFRESH"
        ).pcoll_name = category


class HG_PT_OUTFIT(ClothingPanel, bpy.types.Panel):
    bl_idname = "HG_PT_OUTFIT"
    phase_name = "outfit"


class HG_PT_FOOTWEAR(ClothingPanel, bpy.types.Panel):
    bl_idname = "HG_PT_FOOTWEAR"
    phase_name = "footwear"
