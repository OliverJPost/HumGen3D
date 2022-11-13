# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy

from ..ui_baseclasses import MainPanelPart, subpanel_draw


class HG_PT_BODY(MainPanelPart, bpy.types.Panel):
    """First section shown to the user after adding a human.

    Shows sliders for body proportion shapekeys, including a randomize
    button for these sliders
    Also shows a collapsable menu for changing individual body part size
    """

    bl_idname = "HG_PT_Body"
    phase_name = "body"

    @subpanel_draw
    def draw(self, context):

        sett = context.scene.HG3D  # type:ignore[attr-defined]
        col = self.layout.column()
        row = col.row(align=True)
        row.scale_y = 1.5
        row.operator("hg3d.random_value", icon="FILE_REFRESH").random_type = "body"
        row.operator("hg3d.reset_values", icon="LOOP_BACK", text="").categ = "body"

        col.separator()

        keys = self.human.body.keys
        subcategories = {key.subcategory for key in keys}

        self.box_main = col.column(align=True)
        self.box_main.scale_y = 1.5
        col.separator()

        any_without_category = False
        for subcategory in subcategories:
            if not subcategory or subcategory == "main":
                continue
            if not hasattr(sett.ui, subcategory):
                any_without_category = True
                continue

            is_open, box = self.draw_sub_spoiler(
                col.column(align=True),
                sett.ui,
                subcategory,
                subcategory.capitalize(),
            )
            if not is_open:
                continue
            box_aligned = box.column(align=True)
            box_aligned.scale_y = 1.3
            setattr(self, f"box_{subcategory}", box_aligned)

        if any_without_category:
            is_open, box = self.draw_sub_spoiler(
                col.column(align=True),
                sett.ui,
                "other",
                "Other",
            )
            if is_open:
                box_other = box.column(align=True)
                box_other.scale_y = 1.5

        for key in keys:
            if not hasattr(sett.ui, key.subcategory):
                if not sett.ui.other:
                    continue
                section = box_other
            elif (
                key.subcategory
                and key.subcategory != "main"
                and not getattr(sett.ui, key.subcategory)
            ):
                continue
            else:
                section = getattr(self, f"box_{key.subcategory}")
            key_bpy = key.as_bpy()
            section.prop(
                key_bpy,
                "value_limited",
                text=key.name.capitalize(),
                expand=True,
            )
