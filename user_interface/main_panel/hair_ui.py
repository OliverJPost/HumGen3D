# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy

from ..ui_baseclasses import MainPanelPart, subpanel_draw


class HG_PT_HAIR(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_HAIR"
    phase_name = "hair"

    @subpanel_draw
    def draw(self, context):
        sett = self.sett
        hg_rig = self.human.rig_obj
        body_obj = self.human.body_obj

        hair_systems = self._get_hair_systems(body_obj)

        col = self.layout.column()

        top_col = col.column(align=True)
        top_col.template_icon_view(
            sett.pcoll, "hair", show_labels=True, scale=8.4, scale_popup=6
        )

        row = top_col.row(align=True)
        row.scale_y = 1.5
        row.prop(sett.pcoll, "hair_category", text="")
        if hg_rig.HG.gender == "male":
            self._draw_facial_hair_section(col, sett)

        self._draw_hair_length_ui(hair_systems, col)
        self._draw_hair_material_ui(col)

        return  # disable hair cards UI until operator works

        if hair_systems:
            self._draw_hair_cards_ui(box)

    def _draw_facial_hair_section(self, box, sett):
        """shows template_icon_view for facial hair systems

        Args:
            box (UILayout): box of hair section
            sett (PropertyGroup): HumGen props
        """

        is_open, boxbox = self.draw_sub_spoiler(box, sett, "face_hair", "Face Hair")
        if not is_open:
            return
        col = box.column(align=True)

        col.template_icon_view(
            sett.pcoll, "face_hair", show_labels=True, scale=10, scale_popup=6
        )

        col_h = col.column()
        col_h.scale_y = 1.5
        col_h.prop(sett.pcoll, "face_hair_category", text="")

    def _draw_hair_material_ui(self, box):
        """draws subsection with sliders for the three hair materials

        Args:
            box (UILayout): layout.box of hair section
        """
        boxbox = box.box()
        boxbox.prop(
            self.sett.ui,
            "hair_mat",
            icon="TRIA_DOWN" if self.sett.ui.hair_mat else "TRIA_RIGHT",
            emboss=False,
            toggle=True,
        )
        if not self.sett.ui.hair_mat:
            return

        gender = self.human.gender

        categ = (
            self.sett.hair_mat_male if gender == "male" else self.sett.hair_mat_female
        )

        mat_names = {
            "eye": ".HG_Hair_Eye",
            "face": ".HG_Hair_Face",
            "head": ".HG_Hair_Head",
        }
        hair_mat = next(
            mat
            for mat in self.human.body_obj.data.materials
            if mat.name.startswith(mat_names[categ])
        )
        if "HG_Hair_V3" in [n.name for n in hair_mat.node_tree.nodes]:
            hair_node = hair_mat.node_tree.nodes["HG_Hair_V3"]
            new_hair_node = True
        elif "HG_Hair_V2" in [n.name for n in hair_mat.node_tree.nodes]:
            hair_node = hair_mat.node_tree.nodes["HG_Hair_V2"]
            new_hair_node = True
        else:
            hair_node = hair_mat.node_tree.nodes["HG_Hair"]
            new_hair_node = False

        if new_hair_node:
            boxbox.prop(self.sett, "hair_shader_type", text="Shader")

        row = boxbox.row(align=True)
        row.scale_y = 1.5
        row.prop(self.sett, "hair_mat_{}".format(gender), expand=True)

        col = boxbox.column()

        col.prop(
            hair_node.inputs["Hair Lightness"],
            "default_value",
            text="Lightness",
            slider=True,
        )
        col.prop(
            hair_node.inputs["Hair Redness"],
            "default_value",
            text="Redness",
            slider=True,
        )
        col.prop(hair_node.inputs["Roughness"], "default_value", text="Roughness")

        if "Hue" in hair_node.inputs:
            col.prop(
                hair_node.inputs["Hue"],
                "default_value",
                text="Hue (For dyed hair)",
            )

        if categ == "eye":
            return

        col.label(text="Effects:")
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
        """draws button for adding hair cards

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
