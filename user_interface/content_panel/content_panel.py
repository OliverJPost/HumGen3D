import bpy
from HumGen3D.backend import get_prefs
from HumGen3D.human.human import Human
from HumGen3D.user_interface.ui_baseclasses import draw_icon_title

from ...backend.preview_collections import get_hg_icon, preview_collections
from ..documentation.tips_suggestions_ui import draw_tips_suggestions_ui  # type: ignore
from ..panel_functions import draw_panel_switch_header, draw_paragraph, get_flow


class Tools_PT_Base:
    """Bl_info and commonly used tools for Utility panels"""

    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"

    def Header(self, context):
        return True

    def warning_if_not_creation_phase(self, hg_rig, layout) -> bool:
        """Show a warning if the human is not in creation phase

        Args:
            hg_rig (Object): rig of HumGen human
            layout (UILayout): layout to draw the warning in

        Returns:
            bool: returns True if warning raised, causing the layout this method
            is called in to not draw the rest of the section
        """
        if not hg_rig.HG.phase in ["body", "face", "skin", "hair", "length"]:
            layout.alert = True
            layout.label(text="Human not in creation phase")
            return True
        else:
            return False


class HG_PT_CONTENT(Tools_PT_Base, bpy.types.Panel):
    """Panel with extra functionality for HumGen that is not suitable for the
    main panel. Things like content pack creation, texture baking etc.

    Args:
        Tools_PT_Base (class): Adds bl_info and commonly used tools
    """

    bl_idname = "HG_PT_CONTENT"
    bl_label = "Content"

    @classmethod
    def poll(cls, context):
        sett = context.scene.HG3D
        return sett.ui.active_tab == "CONTENT" and not sett.ui.content_saving

    def draw_header(self, context):
        draw_panel_switch_header(self.layout, context.scene.HG3D)

    def draw(self, context):
        layout = self.layout

        row = self.layout.row(align=True)
        row.scale_x = 0.7
        row.alignment = "CENTER"
        draw_icon_title("Custom Content", row, True)
        draw_paragraph(
            self.layout,
            "Save and share your custom content.",
            alignment="CENTER",
            enabled=False,
        )
        if not get_prefs().filepath:
            layout.alert = True
            layout.label(text="No filepath selected", icon="ERROR")
            return

        human = Human.from_existing(context.object, strict_check=False)
        if not human:
            col = layout.column()
            col.scale_y = 0.8
            col.label(text="No human selected, select a human")
            col.label(text="to see all options.")
            col.separator()


class HG_PT_CUSTOM_CONTENT(Tools_PT_Base, bpy.types.Panel):
    """Shows options for adding preset/starting humans

    Args:
        Tools_PT_Base (class): bl_info and common tools
        Tools_PT_Poll (class): poll for checking if object is HumGen human
    """

    bl_parent_id = "HG_PT_CONTENT"
    bl_label = "Save custom content"

    @classmethod
    def poll(cls, context):
        human = Human.from_existing(context.object, strict_check=False)
        return human

    def draw_header(self, context):
        self.layout.label(text="", icon="OUTLINER_OB_ARMATURE")

    def draw(self, context):
        layout = self.layout
        hg_icons = preview_collections["hg_icons"]

        layout.label(text="Only during creation phase:", icon="RADIOBUT_OFF")
        col = layout.column()
        col.scale_y = 1.5
        # col.enabled = in_creation_phase(hg_rig)

        col.operator(
            "hg3d.open_content_saving_tab",
            text="Save as starting human",
            icon_value=hg_icons["face"].icon_id,
        ).content_type = "starting_human"

        layout.label(text="Always possible:", icon="RADIOBUT_OFF")
        col = layout.column()
        col.scale_y = 1.5

        col.operator(
            "hg3d.open_content_saving_tab",
            text="Save hairstyle",
            icon_value=hg_icons["hair"].icon_id,
        ).content_type = "hair"

        col.operator(
            "hg3d.open_content_saving_tab",
            text="Save custom shapekeys",
            icon_value=hg_icons["body"].icon_id,
        ).content_type = "shapekeys"

        layout.label(text="Only after creation phase:", icon="RADIOBUT_OFF")
        col = layout.column()
        col.scale_y = 1.5
        # col.enabled = not in_creation_phase(hg_rig)

        col.operator(
            "hg3d.open_content_saving_tab",
            text="Save outfit/footwear",
            icon_value=hg_icons["clothing"].icon_id,
        ).content_type = "clothing"

        col.operator(
            "hg3d.open_content_saving_tab",
            text="Save pose",
            icon_value=hg_icons["pose"].icon_id,
        ).content_type = "pose"


class HG_PT_T_CLOTH(Tools_PT_Base, bpy.types.Panel):
    """Subpanel for making cloth objects from normal mesh objects

    Args:
        Tools_PT_Base (class): bl_info and common tools
    """

    bl_parent_id = "HG_PT_CONTENT"
    bl_label = "Mesh --> Clothing"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.object

    def draw_header(self, context):
        hg_icons = preview_collections["hg_icons"]
        self.layout.label(text="", icon_value=hg_icons["outfit"].icon_id)

    def draw(self, context):
        layout = self.layout

        col = layout.column()
        col.scale_y = 0.8
        col.enabled = False
        col.label(text="Select the object you want to add")
        col.label(text="to your human as clothing. ")
        col.separator()
        col.label(text="Then press:")

        col = layout.column()
        col.scale_y = 1.5
        col.operator(
            "hg3d.open_content_saving_tab",
            text="Make mesh into clothing",
            icon_value=get_hg_icon("outfit"),
        ).content_type = "mesh_to_cloth"


class HG_PT_EXTRAS_TIPS(Tools_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_CONTENT"
    bl_label = "Tips and suggestions!"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return get_prefs().show_tips

    def draw(self, context):
        layout = self.layout

        draw_tips_suggestions_ui(layout, context)
        if get_prefs().full_height_menu:
            layout.separator(factor=200)
