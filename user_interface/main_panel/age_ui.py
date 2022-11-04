# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy
from HumGen3D.human.human import Human
from HumGen3D.human.skin.skin import SkinNodes

from ..ui_baseclasses import MainPanelPart, subpanel_draw


class HG_PT_AGE(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_AGE"
    phase_name = "age"

    @subpanel_draw
    def draw(self, context):
        human = Human.from_existing(context.object)
        col = self.layout.column()
        self.draw_subtitle("Main adjustment:", col)
        row = col.row()
        row.scale_y = 1.5
        row.prop(self.sett, "age", text="Age")

        col.separator()

        is_open, box = self.draw_sub_spoiler(
            col, self.sett.ui, "age_hairmat_ui", "Hair Color"
        )
        if is_open:
            self.draw_hairmat_sliders(box)

        is_open, box = self.draw_sub_spoiler(
            col, self.sett.ui, "age_slider_ui", "Age adjustments"
        )
        if is_open:
            self.draw_general_sliders(human, box)

    def draw_general_sliders(self, human, box):
        col = box.column(align=True)
        col.scale_y = 1.2
        for key in human.age.keys:
            col.prop(
                key.as_bpy(),
                "value_positive_limited",
                slider=True,
                text="Body aging",
            )
        nodes = SkinNodes(human)
        age_normal_strength = nodes.get("HG_Age").inputs["Strength"]
        col.prop(
            age_normal_strength, "default_value", slider=True, text="Skin wrinkles"
        )
        age_multiply_strength = nodes.get("Age_Multiply").inputs["Fac"]
        col.prop(
            age_multiply_strength,
            "default_value",
            slider=True,
            text="Skin aging",
        )
        cavity_map_input = nodes.get("Cavity_Multiply").inputs["Fac"]
        col.prop(
            cavity_map_input,
            "default_value",
            slider=True,
            text="Skin cavities",
        )
        normal_input = nodes.get("Normal Map").inputs["Strength"]
        col.prop(normal_input, "default_value", slider=True, text="Normal Strength")

    def draw_hairmat_sliders(self, box):
        hair_mat_regular = self.human.hair.regular_hair.material
        main_hair_node = hair_mat_regular.node_tree.nodes["HG_Hair_V4"]
        hair_mat_eye = self.human.hair.eyebrows.material
        eye_hair_node = hair_mat_eye.node_tree.nodes["HG_Hair_V4"]

        col = box.column(align=True)
        col.scale_y = 1.2

        col.prop(
            main_hair_node.inputs["Lightness"],
            "default_value",
            text="Main Lightness",
            slider=True,
        )
        col.prop(
            eye_hair_node.inputs["Lightness"],
            "default_value",
            text="Eye Hair Lightness",
            slider=True,
        )
        col.prop(
            main_hair_node.inputs["Redness"],
            "default_value",
            text="Main Redness",
            slider=True,
        )
        col.prop(
            eye_hair_node.inputs["Redness"],
            "default_value",
            text="Eye Hair Redness",
            slider=True,
        )
        col.prop(
            main_hair_node.inputs[3],
            "default_value",
            text="Main Salt & Pepper",
            slider=True,
        )

        return col
