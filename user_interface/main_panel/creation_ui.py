import bpy
from HumGen3D.human.human import Human

from ..ui_baseclasses import MainPanelPart


class HG_PT_CREATE(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_CREATE"

    @classmethod
    def poll(self, context):
        return not Human.find(context.object)

    def draw_header(self, context):
        self.draw_panel_switch_header(self.layout, context.scene.HG3D)

    def draw(self, context):
        """UI that shows when no human is selected, with buttons for creating a
        new human.

        Shows a template icon view of all 'starting humans', a switch for male
        and female genders and a pink button to add the selected human
        """
        self.human = None
        self.sett = context.scene.HG3D
        if self.draw_info_and_warning_labels(context):
            return

        col = self.layout.column(align=True)

        self.draw_top_widget(col, self.human)

        box = col.box()

        col = box.column(align=True)
        self.draw_centered_subtitle("Select a starting human", col)
        col.template_icon_view(
            context.scene.HG3D.pcoll,
            "humans",
            show_labels=True,
            scale=8,
            scale_popup=6,
        )

        row = col.row(align=True)
        row.scale_y = 2
        row.scale_x = 1.3
        row.prop(context.scene.HG3D, "gender", expand=True)
        row.operator("hg3d.random", text="", icon="FILE_REFRESH").random_type = "humans"

        col = box.column()
        col.scale_y = 2
        col.alert = True
        col.operator("hg3d.startcreation", icon="COMMUNITY", depress=True)

        if "hg_batch_marker" in context.object:
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
