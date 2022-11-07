# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy

from ..ui_baseclasses import MainPanelPart, subpanel_draw


class HG_PT_CLOTHING(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_CLOTHING"
    phase_name = "clothing"

    @subpanel_draw
    def draw(self, context):
        """Draws a template_icon_view for adding outfits."""

        col = self.layout.column()
        sett = bpy.context.window_manager.humgen3d
        row = col.row(align=True)
        row.scale_y = 1.5
        row.prop(sett.ui, "clothing_tab", expand=True)

        self.draw_content_selector(col, sett.ui.clothing_tab)
