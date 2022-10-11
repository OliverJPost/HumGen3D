# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy
from HumGen3D.backend.properties.ui_properties import UserInterfaceProps
from HumGen3D.human.human import Human

from ..ui_baseclasses import MainPanelPart, subpanel_draw


class HG_PT_BODY(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_Body"
    phase_name = "body"

    """First section shown to the user after adding a human

    Shows sliders for body proportion shapekeys, including a randomize
    button for these sliders
    Also shows a collapsable menu for changing individual body part size
    """

    @subpanel_draw
    def draw(self, context):

        # row.alignment = "CENTER"
        # row.label(text="Body Proportions", icon="COMMUNITY")
        # row = self.layout.row()
        # row.scale_y = 0.2
        # row.alignment = "CENTER"
        # for i in range(8):
        #     row.label(text="", icon="KEYTYPE_KEYFRAME_VEC")

        sett = context.scene.HG3D  # type:ignore[attr-defined]
        col = self.layout.column()
        row = col.row()
        row.scale_y = 1.5
        row.operator("hg3d.random_value", icon="FILE_REFRESH").random_type = "body"

        col.separator()

        keys = self.human.body.keys
        subcategories = set(key.subcategory for key in keys)

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
                sett,
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
                sett,
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
                and not key.subcategory == "main"
                and not getattr(sett.ui, key.subcategory)
            ):
                continue
            else:
                section = getattr(self, f"box_{key.subcategory}")
            key_bpy = key.as_bpy()
            section.prop(
                key_bpy,
                "value",
                text=key.name.capitalize(),
                expand=True,
            )
