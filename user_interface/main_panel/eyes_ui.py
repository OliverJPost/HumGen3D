import bpy

from .main_panel_baseclass import MainPanelPart, subpanel_draw


class HG_PT_EYES(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_EYES"
    phase_name = "eyes"

    @subpanel_draw
    def draw(self, context):
        """Options for changing eyebrows and eye shader"""

        col = self.layout.column()

        if "hg_baked" in self.human.rig_obj:
            col.label(text="Textures are baked", icon="INFO")
            self._draw_eyebrow_switch(col)
            return

        hg_eyes = self.human.eye_obj

        mat = hg_eyes.data.materials[1]
        nodes = mat.node_tree.nodes

        row = col.row()
        row.alignment = "CENTER"
        row.label(text="Color:", icon="RESTRICT_COLOR_OFF")

        col = col.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False
        row = col.row(align=True)
        row.prop(nodes["HG_Eye_Color"].inputs[2], "default_value", text="Iris Color")
        row.operator(
            "hg3d.random", text="", icon="FILE_REFRESH"
        ).random_type = "iris_color"
        col.prop(
            nodes["HG_Scelera_Color"].inputs[2],
            "default_value",
            text="Sclera Color",
        )

        col.separator()

        boxbox = self._draw_eyebrow_switch(col)

        eye_systems = self._get_eye_systems(self.human.body_obj)

        self._draw_hair_length_ui(eye_systems, col)

    def _draw_eyebrow_switch(self, col) -> bpy.types.UILayout:
        """UI for switching between different types of eyebrows

        Args:
            box (UILayout): eye section layout.box

        Returns:
            UILayout: box in box for other hair controls to be placed in
        """

        row = col.row()
        row.alignment = "CENTER"
        row.label(text="Eyebrows:", icon="OUTLINER_OB_CURVES")
        row = col.row(align=True)
        row.operator(
            "hg3d.eyebrowswitch", text="Previous", icon="TRIA_LEFT"
        ).forward = False
        row.operator(
            "hg3d.eyebrowswitch", text="Next", icon="TRIA_RIGHT"
        ).forward = True

    def _get_eye_systems(self, body_obj) -> list:
        """Get a list of all particle systems belojnging to eyeborws and eyelashes

        Args:
            body_obj (Object): HumGen body object

        Returns:
            list: list of modifiers belonging to eyebrow and eyelash systems
        """
        eye_systems = []

        for mod in body_obj.modifiers:
            if (
                mod.type == "PARTICLE_SYSTEM"
                and mod.particle_system.name.startswith(("Eyebrows", "Eyelashes"))
                and (mod.show_viewport or mod.show_render)
            ):
                eye_systems.append(mod.particle_system)

        return eye_systems
