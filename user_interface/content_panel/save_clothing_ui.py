from HumGen3D.user_interface.content_panel.base_draw_functions import (
    _draw_header_box,
    _draw_next_button,
)


def _draw_clothing_gender_ui(context, layout, content_type):
    """Draws a tab for the user to select for which gender(s) this clothing
    item is meant.

    Args:
        context (context): bl context
        layout (UILayout): layout to draw this tab in
    """
    _draw_header_box(
        layout,
        "Is this clothing for men \nwomen or all genders?",
        "MOD_CLOTH",
    )

    col = layout.column(align=True)
    col.scale_y = 1.5
    clothing_type_sett = getattr(context.scene.HG3D.custom_content, content_type)

    col.prop(clothing_type_sett, "save_for_male", text="Male", toggle=True)
    col.prop(clothing_type_sett, "save_for_female", text="Female", toggle=True)

    poll = any((clothing_type_sett.save_for_male, clothing_type_sett.save_for_female))
    _draw_next_button(layout, poll=poll)


def _draw_clothing_uilist_ui(context, layout):
    """Draws a UIList tab for selecting which clothing items should be saved
    for this outfit/footwear

    Args:
        context (context): bl context
        layout (UIlayout): layout to draw tab in
    """
    _draw_header_box(
        layout,
        "Select which objects are \npart of this outfit.",
        "MOD_CLOTH",
    )

    col = layout.column(align=True)
    row = col.row(align=True)
    row.operator("hg3d.ulrefresh", text="Refresh objects").uilist_type = "outfit"
    col.template_list(
        "HG_UL_SAVEOUTFIT",
        "",
        context.scene,
        "saveoutfit_col",
        context.scene,
        "saveoutfit_col_index",
    )

    poll = [i for i in context.scene.saveoutfit_col if i.enabled]
    _draw_next_button(layout, poll=poll)


def _draw_outfit_type_selector(context, layout):
    """Draws a tab for the user to select if this is an outfit or footwear

    Args:
        context (context): bl context
        layout (UILayout): layout to draw tab in
    """
    _draw_header_box(layout, "Are you saving an outfit \nor footwear?", "MOD_CLOTH")

    col = layout.column()
    col.scale_y = 1.5
    col.prop(context.scene.HG3D.custom_content, "saveoutfit_categ", expand=True)

    _draw_next_button(layout)
