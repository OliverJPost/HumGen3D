import bpy
from HumGen3D.human.human import Human

from ..ui_baseclasses import MainPanelPart, subpanel_draw


class HG_PT_LENGTH(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_LENGTH"
    phase_name = "length"

    @subpanel_draw
    def draw(self, context):
        col = self.layout.column(align=True)

        length_m = self.human.length.meters
        length_feet = length_m / 0.3048
        length_inches = int(length_feet * 12.0 - int(length_feet) * 12.0)
        length_label = (
            str(round(length_m, 2))
            + " m   |   "
            + str(int(length_feet))
            + "'"
            + str(length_inches)
            + '"'
        )  # example: 1.83m   |   5'11"

        row = col.row()
        row.scale_y = 2
        row.alignment = "CENTER"
        row.label(text=length_label, icon="EMPTY_SINGLE_ARROW")

        row = col.row(align=True)
        row.scale_y = 2
        row.scale_x = 1.2
        row.prop(self.sett, "human_length", text="Length [cm]")
        row.operator("hg3d.randomlength", text="", icon="FILE_REFRESH")
