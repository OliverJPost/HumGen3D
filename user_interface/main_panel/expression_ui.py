# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy

from HumGen3D.backend import get_prefs
from ..ui_baseclasses import MainPanelPart, forbidden_for_lod, subpanel_draw


class HG_PT_EXPRESSION(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_EXPRESSION"
    phase_name = "expression"

    @subpanel_draw
    @forbidden_for_lod
    def draw(self, context):
        """UI for selecting expressions from template_icon_view or adding facial rig."""

        col = self.layout.column()

        row = col.row(align=True)
        row.scale_y = 1.5
        row.prop(self.sett.ui, "expression_type", expand=True)

        if self.sett.ui.expression_type == "1click":
            self._draw_oneclick_subsection(col)
        else:
            self._draw_frig_subsection(col)

    def _draw_oneclick_subsection(self, layout):
        if "facial_rig" in self.human.objects.body:
            layout.label(text="Library not compatible with face rig")

            col = layout.column()
            col.alert = True
            col.scale_y = 1.5
            col.operator(
                "hg3d.removefrig",
                text="Remove facial rig",
                icon="TRASH",
                depress=True,
            )
            return

        self.draw_content_selector(layout)

        layout.separator(factor=0.5)

        filtered_obj_sks = self.human.objects.body.data.shape_keys
        if filtered_obj_sks:
            self._draw_sk_sliders_subsection(filtered_obj_sks)

    def _draw_sk_sliders_subsection(self, filtered_obj_sks):
        """Draws sliders for each non-corrective shapekey to adjust the strength.

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of expression section
            obj_sks (list): list of non-basis and non-corrective shapekeys
        """
        expr_sks = self.human.expression.keys
        if not expr_sks:
            return

        is_open, boxbox = self.draw_sub_spoiler(
            self.layout, self.sett.ui, "expression_sliders", "⚙️ Strength"
        )
        if not is_open:
            return

        flow = self.get_flow(self.layout, animation=True)
        for key in expr_sks:
            row = key.draw_prop(flow)
            row.active = not key.as_bpy().mute
            row.operator(
                "hg3d.removesk", text="", icon="TRASH"
            ).shapekey = key.as_bpy().name

    def _draw_frig_subsection(self, box):
        """Draws subsection for adding facial rig.

        Args:
            box (UILayout): layout.box of expression section
        """
        is_trial = get_prefs().is_trial
        if is_trial:
            tbox = box.box()
            row = tbox.row(align=True)
            row.alert = True
            row.label(text="Disabled in Trial Version")
            tbox.operator("wm.url_open", text="Buy Human Generator", depress=True).url = (
                "https://humgen3d.com/pricing"
                "?utm_source=addon"
                "&utm_medium=ui_link"
                "&utm_campaign=trial_click"
            )
        col = box.column()
        col.enabled = not is_trial
        if "facial_rig" in self.human.objects.body:
            col.label(text="Facial rig added")
            col.label(text="Use pose mode to adjust", icon="INFO")
            col_h = col.column()
            col_h.scale_y = 1.5
            tutorial_op = col_h.operator(
                "hg3d.draw_tutorial", text="ARKit tutorial", icon="HELP"
            )
            tutorial_op.first_time = False
            tutorial_op.tutorial_name = "arkit_tutorial"
            col_h.operator("hg3d.prepare_for_arkit", text="Prepare for ARKit")
        else:
            col.scale_y = 2
            col.operator("hg3d.addfrig", text="Add facial rig", depress=True)
