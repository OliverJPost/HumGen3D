# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy
from HumGen3D.human.human import Human

from ..panel_functions import draw_panel_switch_header
from ..ui_baseclasses import HGPanel, MainPanelPart


class HG_PT_CREATE(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_CREATE"

    @classmethod
    def poll(self, context):
        if not HGPanel.poll(context):
            return False
        ui_sett = context.scene.HG3D.ui
        return not Human.find_hg_rig(context.object) and ui_sett.active_tab == "CREATE"

    def draw_header(self, context):
        draw_panel_switch_header(
            self.layout, context.scene.HG3D
        )  # type:ignore[attr-defined]

    def draw(self, context):
        """UI that shows when no human is selected, with buttons for creating a
        new human.

        Shows a template icon view of all 'starting humans', a switch for male
        and female genders and a pink button to add the selected human
        """
        self.human = None
        self.sett = context.scene.HG3D  # type:ignore[attr-defined]
        if self.draw_info_and_warning_labels(context):
            return

        col = self.layout.column(align=True)

        self.draw_top_widget(col, self.human)

        col.separator()
        box = col.box().column(align=True)
        self.draw_centered_subtitle("Select a starting human", box)
        box.template_icon_view(
            context.scene.HG3D.pcoll,
            "humans",
            show_labels=True,
            scale=8,
            scale_popup=6,
        )

        row = box.row(align=True)
        row.scale_y = 2
        row.scale_x = 1.3
        row.prop(context.scene.HG3D, "gender", expand=True)
        row.operator(
            "hg3d.random_choice", text="", icon="FILE_REFRESH"
        ).pcoll_name = "humans"

        row = box.row(align=True)
        row.scale_y = 1.5
        row.prop(context.scene.HG3D.pcoll, "humans_category", text="")

        col = col.column()
        col.scale_y = 2
        col.alert = True
        col.operator("hg3d.startcreation", icon="COMMUNITY", depress=True)

        if context.object and "hg_batch_marker" in context.object:
            self._draw_batch_marker_notification(col)

    def _draw_batch_marker_notification(self, layout):
        col = layout.column(align=True)
        col.separator()
        col.separator()
        col.scale_y = 0.4
        row = col.row()
        row.alignment = "CENTER"
        row.label(text="Go to the batch panel to", icon="INFO")
        row = col.row()
        row.alignment = "CENTER"
        row.label(text="generate humans from this")
        row = col.row()
        row.alignment = "CENTER"
        row.label(text="batch marker.")

        col.separator()

        row = col.row()
        row.alignment = "CENTER"
        row.label(text="(Switch at the top of the UI)")
