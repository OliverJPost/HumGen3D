# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy
from HumGen3D.backend import get_prefs

from ..documentation.tips_suggestions_ui import draw_tips_suggestions_ui
from .base_draw_functions import (
    _draw_name_ui,
    _draw_thumbnail_selection_ui,
    _draw_warning_if_different_active_human,
    draw_category_ui,
)
from .save_clothing_ui import _draw_clothing_gender_ui
from .save_hair_ui import (
    _draw_hair_gender_ui,
    _draw_hairtype_ui,
    _draw_particle_system_selection_ui,
)


class HG_PT_CONTENT_SAVING(bpy.types.Panel):
    """Panel that shows step by step options for saving various kinds of custom content.

    Which custom content it displays options for is determined by
    sett.content_saving_type. Which tab it shows is determined by
    content_saving_tab_index
    """

    bl_idname = "HG_PT_CONTENT_SAVING"
    bl_label = " Content Saving"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"
    # fmt: off
    content_draw_functions = {
        "hair": [
            _draw_particle_system_selection_ui,
            _draw_thumbnail_selection_ui,
            _draw_hairtype_ui,
            _draw_hair_gender_ui,
            draw_category_ui,
            _draw_name_ui,
        ],
        "starting_human": [
            _draw_thumbnail_selection_ui,
            draw_category_ui,
            _draw_name_ui
        ],
        "key": [
            draw_category_ui,
            _draw_name_ui
        ],
        "outfit": [
            _draw_thumbnail_selection_ui,
            _draw_clothing_gender_ui,
            draw_category_ui,
            _draw_name_ui,
        ],
        "footwear": [
            _draw_thumbnail_selection_ui,
            _draw_clothing_gender_ui,
            draw_category_ui,
            _draw_name_ui,
        ],
        "pose": [
            _draw_thumbnail_selection_ui,
            draw_category_ui,
            _draw_name_ui
        ],
        "texture": [
            _draw_thumbnail_selection_ui,
            draw_category_ui,
            _draw_name_ui
        ]
    }
    # fmt: on

    @classmethod
    def poll(cls, context):
        return context.scene.HG3D.custom_content.content_saving_ui

    def draw_header(self, context):
        row = self.layout.row()
        row.alert = True
        row.operator("hg3d.cancel_content_saving_ui", text="Cancel", icon="X")

    def draw(self, context):
        layout = self.layout
        cc_sett = context.scene.HG3D.custom_content
        self.cc_sett = cc_sett

        content_type = cc_sett.content_saving_type

        tab_idx = cc_sett.content_saving_tab_index

        _draw_warning_if_different_active_human(context, layout)

        try:
            self.content_draw_functions[content_type][tab_idx](context, layout)
        except TypeError:
            self.content_draw_functions[content_type][tab_idx](
                context, layout, content_type
            )

        if get_prefs().show_tips:
            draw_tips_suggestions_ui(layout, context)
