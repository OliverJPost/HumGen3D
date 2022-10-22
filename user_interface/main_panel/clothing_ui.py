# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy

from ..ui_baseclasses import MainPanelPart, subpanel_draw


class ClothingPanel(MainPanelPart):
    @subpanel_draw
    def draw(self, context):
        """Draws a template_icon_view for adding outfits."""
        self.draw_content_selector()


class HG_PT_OUTFIT(ClothingPanel, bpy.types.Panel):
    bl_idname = "HG_PT_OUTFIT"
    phase_name = "outfit"


class HG_PT_FOOTWEAR(ClothingPanel, bpy.types.Panel):
    bl_idname = "HG_PT_FOOTWEAR"
    phase_name = "footwear"
