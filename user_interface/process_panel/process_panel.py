import bpy
from HumGen3D.user_interface.panel_functions import draw_panel_switch_header

from ..ui_baseclasses import draw_icon_title


class HG_PT_PROCESS(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"
    bl_idname = "HG_PT_PROCESS"
    bl_label = "Process"

    def draw_header(self, context) -> None:
        draw_panel_switch_header(self.layout, context.scene.HG3D)

    @classmethod
    def poll(cls, context):
        return context.scene.HG3D.ui.active_tab == "PROCESS"

    def draw(self, context):
        col = self.layout.column()

        row = col.row(align=True)
        row.scale_x = 0.7
        row.alignment = "CENTER"
        draw_icon_title("Processing", row, True)
