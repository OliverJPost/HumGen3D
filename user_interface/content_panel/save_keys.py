from .base_draw_functions import _draw_header_box, _draw_next_button


def _draw_shapekey_selection_ui(context, layout):
    """Draws a tab with an UIList for the user to select which shapekeys to
    save in this collection

    Args:
        context (context): bl context
        layout (UILayout): layout to draw tab in
    """
    cc_sett = context.scene.HG3D.custom_content
    _draw_header_box(layout, "Select shapekeys to save", "SHAPEKEY_DATA")

    col = layout.column(align=True)

    col.operator("hg3d.ulrefresh", text="Refresh shapekeys").type = "shapekeys"
    col.template_list(
        "HG_UL_SHAPEKEYS",
        "",
        context.scene,
        "shapekeys_col",
        context.scene,
        "shapekeys_col_index",
    )

    col.separator()

    col.prop(
        cc_sett,
        "show_saved_sks",
        text="Show already saved shapekeys",
        icon=("CHECKBOX_HLT" if cc_sett.show_saved_sks else "CHECKBOX_DEHLT"),
    )

    poll = [i for i in context.scene.shapekeys_col if i.enabled]
    _draw_next_button(layout, poll=poll)
