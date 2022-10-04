from HumGen3D.user_interface.icons.icons import get_hg_icon

from .base_draw_functions import _draw_header_box, _draw_next_button


def _draw_particle_system_selection_ui(context, layout):
    """Draws a UIList for the user to select which particle systems to save
    for this hairstyle

    Args:
        context (context): bl context
        layout (UILayout): layout to draw tab in
    """

    _draw_header_box(
        layout,
        "Select particle systems \nto be included in this style.",
        "OUTLINER_OB_HAIR",
    )

    col = layout.column(align=True)
    row = col.row(align=True)

    row.operator("hg3d.ulrefresh", text="Refresh hairsystems").type = "hair"
    row.prop(
        context.scene.HG3D.custom_content,
        "show_eyesystems",
        text="",
        icon_value=get_hg_icon("eyes"),
        toggle=True,
    )

    col.template_list(
        "HG_UL_SAVEHAIR",
        "",
        context.scene,
        "savehair_col",
        context.scene,
        "savehair_col_index",
    )

    poll = [i for i in context.scene.savehair_col if i.enabled]
    _draw_next_button(layout, poll)


def _draw_hair_gender_ui(context, layout):
    """Draws the tab for the user to select for which gender this hairstyle
    is meant.

    Args:
        context (context): bl context
        layout (UIlayout): layout to draw tab in
    """
    sett = context.scene.HG3D.custom_content

    _draw_header_box(
        layout,
        "Is this style for men, women \nor all genders?",
        "COMMUNITY",
    )

    col = layout.column()
    col.scale_y = 1.5
    col.prop(sett, "savehair_male", text="Male", toggle=True)
    subrow = col.row(align=True)
    subrow.enabled = False if sett.save_hairtype == "face_hair" else True
    subrow.prop(sett, "savehair_female", text="Female", toggle=True)

    poll = any((sett.savehair_male, sett.savehair_female))
    _draw_next_button(layout, poll=poll)


def _draw_hairtype_ui(context, layout):
    """Draws layout for the user to select if this is facial hair or regular
    hair.

    Args:
        context (context):  bl context
        layout (UILayout): layout to draw tab in
    """
    sett = context.scene.HG3D.custom_content

    _draw_header_box(layout, "Is this style facial hair?", "COMMUNITY")

    col = layout.column()
    col.scale_y = 1.5
    col.prop(sett, "save_hairtype", expand=True)

    _draw_next_button(layout)
