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
            self.draw_hairmat_sliders(box, human)

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
        human.age.age_wrinkles.draw_prop(col, "Wrinkles")
        human.age.age_color.draw_prop(col, "Age Color")
        human.skin.cavity_strength.draw_prop(col, "Cavity strength")
        human.skin.normal_strength.draw_prop(col, "Normal Strength")

    def draw_hairmat_sliders(self, box, human):
        col = box.column(align=True)
        col.scale_y = 1.2

        human.hair.regular_hair.lightness.draw_prop(col, "Main Lightness")
        human.hair.eyebrows.lightness.draw_prop(col, "Eye hair Lightness")
        human.hair.regular_hair.redness.draw_prop(col, "Main Redness")
        human.hair.eyebrows.redness.draw_prop(col, "Eye hair Redness")
        human.hair.regular_hair.salt_and_pepper.draw_prop(col, "Main Salt and Pepper")

        return col
