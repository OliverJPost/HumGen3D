import bpy  # type:ignore

from ..old.blender_backend.preview_collections import get_hg_icon


class VIEW3D_MT_HG_Marker_Add(bpy.types.Menu):
    # Define the "Single Vert" menu
    bl_idname = "VIEW3D_MT_HG_Marker_Add"
    bl_label = "Human Generator Markers"

    def draw(self, context):
        """Menu in the 'add object' modal for the user to add markers for the
        HG batch generator
        """
        layout = self.layout
        layout.operator_context = "INVOKE_REGION_WIN"

        layout.operator(
            "wm.url_open", text="Tutorial", icon="HELP"
        ).url = "https://publish.obsidian.md/human-generator/Using+the+batch+mode/Using+the+batch+generator"

        layout.separator()

        for primitive in [
            "a_pose",
            "t_pose",
            "standing_around",
            "sitting",
            "socializing",
            "walking",
            "running",
        ]:
            primitive_name_formatted = primitive.capitalize().replace("_", " ")
            operator = layout.operator(
                "hg3d.add_batch_marker",
                text=primitive_name_formatted,
                icon_value=get_hg_icon(primitive),
            )
            operator.marker_type = primitive


def add_hg_primitive_menu(self, context):
    layout = self.layout
    layout.operator_context = "INVOKE_REGION_WIN"

    layout.separator()
    layout.menu(
        "VIEW3D_MT_HG_Marker_Add",
        text="Human Generator Markers",
        icon_value=get_hg_icon("HG_icon"),
    )
