# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import addon_utils
import bpy

from ..ui_baseclasses import MainPanelPart, subpanel_draw


class HG_PT_POSE(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_POSE"
    phase_name = "pose"

    @subpanel_draw
    def draw(self, context):
        sett = self.sett

        col = self.layout.column()

        row_h = col.row(align=True)
        row_h.scale_y = 1.5
        row_h.prop(sett.ui, "pose_tab_switch", expand=True)

        if sett.ui.pose_tab_switch == "library":
            self._draw_pose_library(sett, col)
        elif sett.ui.pose_tab_switch == "rigify":
            self._draw_rigify_subsection(col)

    def _draw_rigify_subsection(self, box):
        """Draws ui for adding rigify, context info if added.

        Args:
            box (UILayout): layout.box of pose section
        """
        if "hg_rigify" in self.human.rig_obj.data:
            box.label(text="Rigify rig active")
            box.label(text="Use Rigify add-on to adjust", icon="INFO")
        elif addon_utils.check("rigify"):
            box.label(text="Load facial rig first", icon="INFO")
            col = box.column()
            col.scale_y = 1.5
            col.alert = True
            col.operator("hg3d.rigify", depress=True)
        else:
            box.label(text="Rigify is not enabled")

    def _draw_pose_library(self, sett, layout):
        """Draws template_icon_view for selecting poses from the library.

        Args:
            sett (PropertyGroup): HumGen properties
            box (UILayout): layout.box of pose section
        """
        if "hg_rigify" in self.human.rig_obj.data:
            col = layout.column(align=True)

            row = col.row(align=True)
            row.label(text="Rigify not supported", icon="ERROR")
            row.operator(
                "hg3d.showinfo", text="", icon="QUESTION"
            ).info = "rigify_library"
            return

        self.draw_content_selector(layout)
