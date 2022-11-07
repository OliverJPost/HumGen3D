import bpy

from .base_draw_functions import _draw_header_box, _draw_next_button


def _draw_key_type_ui(context, layout):
    _draw_header_box(layout, "Select type", "COMMUNITY")

    cc_sett = bpy.context.window_manager.humgen3d.custom_content
    col = layout.column()
    subcol = col.column()
    subcol.scale_y = 1.5
    subcol.prop(cc_sett.key, "save_as", text="")

    if cc_sett.key.save_as == "livekey":
        col.prop(cc_sett.key, "delete_original", text="Delete original shape key")

    _draw_next_button(layout, True)
