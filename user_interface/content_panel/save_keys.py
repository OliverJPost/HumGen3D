from .base_draw_functions import _draw_header_box, _draw_next_button


def _draw_key_category_ui(context, layout):
    _draw_header_box(layout, "Select category", "COMMUNITY")

    cc_sett = context.scene.HG3D.custom_content
    col = layout.column()
    row = col.row()
    row.scale_y = 1.5
    row.prop(cc_sett.key, "category_to_save_to", text="")

    col.separator()

    row = col.row()
    row.alignment = "CENTER"
    row.label(text="Subcategory:")

    row = col.row()
    row.scale_y = 1.5
    row.prop(cc_sett.key, "existing_or_new_subcategory", expand=True)

    row = col.row()
    row.scale_y = 1.5
    if cc_sett.key.existing_or_new_subcategory == "existing":
        row.prop(cc_sett.key, "subcategory", text="")
    else:
        row.prop(cc_sett.key, "new_category_name", text="Name")

    poll = cc_sett.key.category_to_save_to and cc_sett.key.subcategory
    _draw_next_button(layout, poll)


def _draw_key_type_ui(context, layout):
    _draw_header_box(layout, "Select type", "COMMUNITY")

    cc_sett = context.scene.HG3D.custom_content
    col = layout.column()
    subcol = col.column()
    subcol.scale_y = 1.5
    subcol.prop(cc_sett.key, "save_as", text="")

    if cc_sett.key.save_as == "livekey":
        col.prop(cc_sett.key, "delete_original", text="Delete original shape key")

    _draw_next_button(layout, True)
