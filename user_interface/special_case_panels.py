import bpy
from HumGen3D.human.human import Human
from HumGen3D.user_interface.panel_functions import draw_paragraph


class HG_PT_LEGACYINSTALL(bpy.types.Panel):
    bl_idname = "HG_PT_LEGACYINSTALL"
    bl_label = "HumGen"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"

    @classmethod
    def poll(cls, context):
        is_legacy = Human.is_legacy(context.object)
        legacy_addon_not_installed = not context.preferences.addons.get(
            "HumGen3D-Legacy"
        )

        return is_legacy and legacy_addon_not_installed

    def draw(self, context):
        col = self.layout.column()
        col.alert = True

        message = (
            "This human was created before HG V4. To edit it you need the Legacy "
            + "version of the Human Generator add-on."
        )

        draw_paragraph(col, message)

        col.separator()

        row = col.row()
        row.scale_y = 1.5
        row.operator(
            "wm.url_open", text="Download here", icon="URL"
        ).url = "https://github.com/OliverJPost/HumGen3D-Legacy"
