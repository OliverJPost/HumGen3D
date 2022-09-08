import bpy
from HumGen3D import Human

from ...ui_baseclasses import MainPanelPart, subpanel_draw


class HG_PT_MODAPPLY(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_MODAPPLY"
    phase_name = "apply"

    @subpanel_draw
    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D

        col = layout.column(align=True)
        col.label(text="Select modifiers to be applied:")
        col.operator("hg3d.ulrefresh", text="Refresh modifiers").type = "modapply"
        col.template_list(
            "HG_UL_MODAPPLY",
            "",
            context.scene,
            "modapply_col",
            context.scene,
            "modapply_col_index",
        )

        row = col.row(align=True)
        row.operator("hg3d.selectmodapply", text="All").all = True
        row.operator("hg3d.selectmodapply", text="None").all = False

        col = layout.column(align=True)
        col.label(text="Objects to apply:")
        row = col.row(align=True)
        row.prop(sett, "modapply_search_objects", text="")
        col.separator()
        col.label(text="Modifier list display:")
        row = col.row(align=True)
        row.prop(sett, "modapply_search_modifiers", text="")

        layout.separator()
        col = layout.column(align=True)
        self.draw_centered_subtitle("Options", col, "SETTINGS")
        col.prop(sett, "modapply_keep_shapekeys", text="Keep shapekeys")
        col.prop(sett, "modapply_apply_hidden", text="Apply hidden modifiers")

        col_h = layout.column()
        col_h.scale_y = 1.5
        col_h.operator("hg3d.modapply", text="Apply selected modifiers", depress=True)
