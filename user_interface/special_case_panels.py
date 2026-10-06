import bpy
from HumGen3D.common import find_original_rig, is_legacy, is_processed
from HumGen3D.user_interface.panel_functions import draw_paragraph


class HG_PT_LEGACYINSTALL(bpy.types.Panel):
    bl_idname = "HG_PT_LEGACYINSTALL"
    bl_label = "HumGen"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"

    @classmethod
    def poll(cls, context):
        human_is_legacy = is_legacy(context.object)
        legacy_addon_not_installed = not context.preferences.addons.get(
            "HumGen3D-Legacy"
        )

        return human_is_legacy and legacy_addon_not_installed

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


class HG_PT_PROCESSED(bpy.types.Panel):
    bl_idname = "HG_PT_PROCESSED"
    bl_label = "HumGen"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"

    @classmethod
    def poll(cls, context):
        return is_processed(context.object)

    def draw(self, context):
        col = self.layout.column()

        message = (
            "This is a processed human. It is a frozen result that can't be edited "
            + "with Human Generator. To change it, edit the original human and "
            + "process it again."
        )
        draw_paragraph(col, message)

        col.separator()

        if find_original_rig(context.object, context.view_layer.objects):
            row = col.row()
            row.scale_y = 1.5
            row.operator(
                "hg3d.select_original_human",
                text="Go to original human",
                icon="RESTRICT_SELECT_OFF",
            )
        else:
            draw_paragraph(
                col,
                "The original human is not in this scene anymore.",
                enabled=False,
            )
