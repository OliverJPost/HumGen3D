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
            self.draw_content_selector(col, pcoll_name="face_hair")
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
            "eye": "eyebrows",
            "face": "face_hair",
            "head": "regular_hair",
        }
        hair_attr = getattr(self.human.hair, mat_names[category])

        col = box.column(align=True)
        col.scale_y = 1.2
        col_h = col.column(align=True)

        hair_attr.lightness.draw_prop(col_h, "Lightness")
        hair_attr.redness.draw_prop(col_h, "Redness")

        if category == "eye":
            return

        col.separator()

        self.draw_subtitle("Effects", col, "GP_MULTIFRAME_EDITING")
        hair_attr.hue.draw_prop(col, "Hue")
        hair_attr.roughness.draw_prop(col, "Roughness")
        hair_attr.salt_and_pepper.draw_prop(col, "Salt and Pepper")
        hair_attr.roots.draw_prop(col, "Roots")

        if hair_attr.roots.value > 0:
            hair_attr.root_lightness.draw_prop(col, "Root Lightness")
            hair_attr.root_redness.draw_prop(col, "Root Redness")
            hair_attr.root_hue.draw_prop(col, "Root Hue")

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
