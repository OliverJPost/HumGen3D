from .base_draw_functions import _draw_header_box, _draw_next_button


def _draw_pose_category_ui(context, layout):
    """Draws the tab for selecting in which category this pose should be
    saved.

    Args:
        context (context): bl context
        layout (UILayout): layout to draw tab in
    """
    _draw_header_box(
        layout,
        "What category should this \npose be saved to?",
        "ARMATURE_DATA",
    )

    col = layout.column()
    col.scale_y = 1.5

    row = col.row()
    cc_sett = context.scene.HG3D.custom_content
    row.prop(cc_sett, "pose_category_to_save_to", expand=True)

    col.separator()

    if cc_sett.pose_category_to_save_to == "existing":
        col.prop(cc_sett, "pose_chosen_existing_category", text="")
        poll = cc_sett.pose_chosen_existing_category != "All"
    else:
        col.prop(cc_sett, "pose_new_category_name", text="Name")
        poll = cc_sett.pose_new_category_name

    col.separator()

    _draw_next_button(layout, poll=poll)
