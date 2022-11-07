from HumGen3D.user_interface.icons.icons import get_hg_icon

from .base_draw_functions import _draw_header_box, _draw_next_button
import bpy


def _draw_particle_system_selection_ui(context, layout):
    """Draws a UIList for the user to select which particle systems to save.

    Args:
        context (context): bl context
        layout (UILayout): layout to draw tab in
    """
    _draw_header_box(
        layout,
        "Select particle systems \nto be included in this style.",
        "BLANK1",
    )

    col = layout.column(align=True)
    row = col.row(align=True)

    row.operator("hg3d.ulrefresh", text="Refresh hairsystems").uilist_type = "hair"
    row.prop(
        bpy.context.window_manager.humgen3d.custom_content,
        "show_eyesystems",
        text="",
        icon_value=get_hg_icon("eyes"),
        toggle=True,
    )

    col.template_list(
        "HG_UL_SAVEHAIR",
        "",
        context.window_manager,
        "savehair_col",
        context.window_manager,
        "savehair_col_index",
    )

    poll = [i for i in context.window_manager.savehair_col if i.enabled]
    _draw_next_button(layout, poll)


def _draw_hair_gender_ui(context, layout):
    """Draws the tab for the user to select for which gender this hairstyle is meant.

    Args:
        context (context): bl context
        layout (UIlayout): layout to draw tab in
    """
    hair_sett = bpy.context.window_manager.humgen3d.custom_content.hair

    _draw_header_box(
        layout,
        "Is this style for men, women \nor all genders?",
        "COMMUNITY",
    )

    col = layout.column()
    col.scale_y = 1.5
    col.prop(hair_sett, "save_for_male", text="Male", toggle=True)
    subrow = col.row(align=True)
    subrow.enabled = hair_sett.type != "face_hair"
    subrow.prop(hair_sett, "save_for_female", text="Female", toggle=True)

    poll = any((hair_sett.save_for_male, hair_sett.save_for_female))
    _draw_next_button(layout, poll=poll)


def _draw_hairtype_ui(context, layout):
    """Draws layout for the user to select if this is facial hair or regular hair.

    Args:
        context (context):  bl context
        layout (UILayout): layout to draw tab in
    """
    hair_sett = bpy.context.window_manager.humgen3d.custom_content.hair

    _draw_header_box(layout, "Is this style facial hair?", "COMMUNITY")

    col = layout.column()
    col.scale_y = 1.5
    col.prop(hair_sett, "type", expand=True)

    _draw_next_button(layout)
