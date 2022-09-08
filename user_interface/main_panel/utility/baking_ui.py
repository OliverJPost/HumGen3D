import bpy
from HumGen3D import Human

from ...panel_functions import get_flow
from ...ui_baseclasses import MainPanelPart, subpanel_draw


class HG_PT_BAKE(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_BAKE"
    phase_name = "baking"

    @subpanel_draw
    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D
        bake_sett = sett.bake

        if self._draw_baking_warning_labels(context, layout):
            return

        col = get_flow(sett, layout)
        self.draw_centered_subtitle("Quality", col, "SETTINGS")
        col.prop(bake_sett, "samples", text="Samples")

        layout.separator()

        col = get_flow(sett, layout)

        self.draw_centered_subtitle("Resolution", col, "IMAGE_PLANE")

        for res_type in ["body", "eyes", "teeth", "clothes"]:
            col.prop(bake_sett, f"res_{res_type}", text=res_type.capitalize())

        layout.separator()

        col = get_flow(sett, layout)

        self.draw_centered_subtitle("Output", col, "FILE_TICK")

        col.prop(bake_sett, "file_type", text="Format:")
        col.prop(bake_sett, "export_folder", text="Folder")

        row = col.row()
        row.alignment = "RIGHT"
        row.label(text="HG folder when empty", icon="INFO")

        layout.separator()

        col = layout.column()
        col.scale_y = 1.5
        col.alert = True
        col.operator("hg3d.bake", icon="OUTPUT", depress=True)

    def _draw_baking_warning_labels(self, context, layout) -> bool:
        """Draws warning if no human is selected or textures are already baked

        Args:
            context (bpy.context): Blender context
            layout (UILayout): layout to draw warning labels in

        Returns:
            bool: True if problem found, causing rest of ui to cancel
        """
        human = Human.from_existing(context.object)
        if not human:
            layout.label(text="No human selected")
            return True

        if "hg_baked" in human.rig_obj:
            if context.scene.HG3D.batch_idx:
                layout.label(text="Baking in progress")
            else:
                layout.label(text="Already baked")

            return True

        return False
