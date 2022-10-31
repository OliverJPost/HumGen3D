# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy

from ..ui_baseclasses import MainPanelPart, subpanel_draw


class HG_PT_HAIR(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_HAIR"
    phase_name = "hair"

    @subpanel_draw
    def draw(self, context):
        sett = self.sett
        body_obj = self.human.body_obj

        hair_systems = self._get_hair_systems(body_obj)

        col = self.layout.column()

        row = col.row()
        row.scale_y = 1.5
        row.prop(sett.ui, "hair_ui_tab", expand=True)

        if sett.ui.hair_ui_tab == "head":
            self.draw_content_selector(col, pcoll_name="hair")
            hair_systems = self.human.hair.regular_hair.particle_systems
        elif sett.ui.hair_ui_tab == "face":
            self.draw_content_selector(pcoll_name="face_hair")
            hair_systems = self.human.hair.face_hair.particle_systems
        else:
            self._draw_eyebrow_switch(self.layout)
            hair_systems = list(self.human.hair.eyebrows.particle_systems) + list(
                self.human.hair.eyelashes.particle_systems
            )
        col = self.layout.column()

        self._draw_hair_material_ui(col, sett.ui.hair_ui_tab)
        self._draw_hair_length_ui(hair_systems, col)

    def _draw_face_hair_section(self, box, sett):
        """Shows template_icon_view for facial hair systems.

        Args:
            box (UILayout): box of hair section
            sett (PropertyGroup): HumGen props
        """
        is_open, boxbox = self.draw_sub_spoiler(box, sett.ui, "face_hair", "Face Hair")
        if not is_open:
            return

        self.draw_content_selector(layout=boxbox, pcoll_name="face_hair")

    def _draw_hair_material_ui(self, layout, category):
        """Draws subsection with sliders for the three hair materials.

        Args:
            box (UILayout): layout.box of hair section
        """
        is_open, box = self.draw_sub_spoiler(
            layout, self.sett.ui, "hair_mat", "Material"
        )

        if not is_open:
            return

        row = box.row()
        row.scale_y = 1.5
        row.prop(self.sett, "hair_shader_type", text="Shader")

        mat_names = {
            "eye": ".HG_Hair_Eye",
            "face": ".HG_Hair_Face",
            "head": ".HG_Hair_Head",
        }
        hair_mat = next(
            mat
            for mat in self.human.body_obj.data.materials
            if mat.name.startswith(mat_names[category])
        )

        hair_node = hair_mat.node_tree.nodes["HG_Hair_V4"]

        col = box.column(align=True)
        col.scale_y = 1.2
        col_h = col.column(align=True)
        col_h.prop(
            hair_node.inputs["Lightness"],
            "default_value",
            text="Lightness",
            slider=True,
        )
        col_h.prop(
            hair_node.inputs["Redness"],
            "default_value",
            text="Redness",
            slider=True,
        )

        if category == "eye":
            return

        col.separator()

        self.draw_subtitle("Effects", col, "GP_MULTIFRAME_EDITING")
        col.prop(
            hair_node.inputs["Hue"],
            "default_value",
            text="Hue (For dyed hair)",
        )
        col.prop(hair_node.inputs["Roughness"], "default_value", text="Roughness")
        col.prop(
            hair_node.inputs["Pepper & Salt"],
            "default_value",
            text="Pepper & Salt",
            slider=True,
        )
        col.prop(
            hair_node.inputs["Roots"],
            "default_value",
            text="Roots",
            slider=True,
        )

        if hair_node.inputs["Roots"].default_value > 0:
            col.prop(
                hair_node.inputs["Root Lightness"],
                "default_value",
                text="Root Lightness",
            )
            col.prop(
                hair_node.inputs["Root Redness"],
                "default_value",
                text="Root Redness",
            )
            if "Roots Hue" in hair_node.inputs:
                col.prop(
                    hair_node.inputs["Roots Hue"],
                    "default_value",
                    text="Root Hue",
                )

    def _draw_hair_cards_ui(self, box):
        """Draws button for adding hair cards.

        Args:
            box (UILayout): layout.box of hair section
        """
        boxbox = box.box()
        boxbox.prop(
            self.sett,
            "hair_cards_ui",
            icon="TRIA_DOWN" if self.sett.hair_cards_ui else "TRIA_RIGHT",
            emboss=False,
            toggle=True,
        )

        if self.sett.hair_cards_ui:
            box.operator("hg3d.haircards")

    def _draw_eyebrow_switch(self, layout) -> bpy.types.UILayout:
        """UI for switching between different types of eyebrows.

        Args:
            box (UILayout): eye section layout.box

        Returns:
            UILayout: box in box for other hair controls to be placed in
        """
        row = layout.row()
        row.alignment = "CENTER"
        row.label(text="Eyebrows:", icon="OUTLINER_OB_CURVES")
        row = layout.row(align=True)
        row.operator(
            "hg3d.eyebrowswitch", text="Previous", icon="TRIA_LEFT"
        ).forward = False
        row.operator(
            "hg3d.eyebrowswitch", text="Next", icon="TRIA_RIGHT"
        ).forward = True
