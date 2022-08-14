import os
from pathlib import Path
from sys import platform

import addon_utils  # type:ignore
import bpy
from HumGen3D import bl_info
from HumGen3D.backend import get_prefs

from ...backend.preview_collections import preview_collections
from ...human.human import Human  # type: ignore
from ..panel_functions import (
    draw_panel_switch_header,
    draw_spoiler_box,
    draw_sub_spoiler,
    get_flow,
    searchbox,
)
from ..tips_suggestions_ui import draw_tips_suggestions_ui  # type: ignore
from .main_panel_baseclass import MainPanelPart  # type: ignore


class HG_PT_PANEL(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_Panel"
    phase_name = "closed"
    """Main Human Generator panel, divided into creation phase and finalize
    phase. These phases are then divided into sections (i.e. hair, body, face)

    One exception is the clothing material section. If a HumGen clothing object
    is selected, this UI shows options to change the material
    """

    def draw_header(self, context):
        self.draw_panel_switch_header(self.layout, context.scene.HG3D)

    def draw(self, context):
        layout = self.layout
        self.sett = context.scene.HG3D
        self.pref = get_prefs()

        self.human = Human.from_existing(context.active_object, strict_check=False)

        found_problem = self.draw_info_and_warning_labels(context, layout)
        if found_problem:
            return

        self.draw_top_widget(self.human)

        self.col = layout.column(align=True)

        draw_spoiler_box(self, "body")
        draw_spoiler_box(self, "length")
        draw_spoiler_box(self, "face")
        draw_spoiler_box(self, "skin")
        draw_spoiler_box(self, "eyes")
        draw_spoiler_box(self, "hair")
        draw_spoiler_box(self, "outfit")
        draw_spoiler_box(self, "footwear")
        draw_spoiler_box(self, "pose")
        draw_spoiler_box(self, "expression")

        if get_prefs().show_tips:
            draw_tips_suggestions_ui(layout, context)
            if get_prefs().full_height_menu:
                layout.separator(factor=200)

    #  __    __   _______     ___       _______   _______ .______
    # |  |  |  | |   ____|   /   \     |       \ |   ____||   _  \
    # |  |__|  | |  |__     /  ^  \    |  .--.  ||  |__   |  |_)  |
    # |   __   | |   __|   /  /_\  \   |  |  |  ||   __|  |      /
    # |  |  |  | |  |____ /  _____  \  |  '--'  ||  |____ |  |\  \----.
    # |__|  |__| |_______/__/     \__\ |_______/ |_______|| _| `._____|

    def draw_info_and_warning_labels(self, context, layout) -> bool:
        """Collection of all info and warning labels of HumGen

        Args:
            context : Blender Context
            layout : HumGen main panel layout

        Returns:
            bool: True if problem was found, causing the HumGen UI to stop
            displaying anything after the warning labels
        """
        filepath_problem = self._filepath_warning(layout)
        if filepath_problem:
            return True

        base_content_found = self._base_content_warning(layout)
        if not base_content_found:
            return True

        if not self.sett.subscribed:
            self._welcome_menu(layout)
            return True

        update_problem = self._update_notification(layout)
        if update_problem:
            return True

        general_problem = self._warning_header(context, layout)
        if general_problem:
            return True

        return False  # no problems found

    def _filepath_warning(self, layout) -> bool:
        """Shows warning if no filepath is selected

        Args:
            layout (AnyType): Main HumGen panel layout

        Returns:
            Bool: True if filepath was not found, causing the UI to cancel
        """
        if self.pref.filepath:
            return False

        layout.alert = True
        layout.label(text="No filepath selected")
        layout.label(text="Select one in the preferences")
        layout.operator("hg3d.openpref", text="Open preferences", icon="PREFERENCES")

        return True

    def _base_content_warning(self, layout) -> bool:
        """Looks if base content is installed, otherwise shows warning and
        stops the rest of the UI from showing

        Args:
            layout (AnyType): Main Layout of HumGen Panel

        Returns:
            Bool: True if base content found, False causes panel to return
        """
        base_humans_path = self.pref.filepath + str(
            Path("content_packs/Base_Humans.json")
        )

        base_content = os.path.exists(base_humans_path)

        if not base_content:
            layout.alert = True

            layout.label(text="Filepath selected, but couldn't")
            layout.label(text="find any humans.")
            layout.label(text="Check if filepath is correct and")
            layout.label(text="if the content packs are installed.")

            layout.operator(
                "hg3d.openpref", text="Open preferences", icon="PREFERENCES"
            )

        return base_content

    def _update_notification(self, layout) -> bool:
        """Shows notifications for available or required updates of both the
        add-on and the content packs.

        Args:
            layout ([AnyType]): Main layout of HumGen panel

        Returns:
            bool: True if update required, causing panel to only show error message
        """
        # find out what kind of update is available
        if self.pref.cpack_update_required:
            self.update = "cpack_required"
        elif tuple(bl_info["version"]) < tuple(self.pref.latest_version):
            self.update = "addon"
        elif self.pref.cpack_update_available:
            self.update = "cpack_available"
        else:
            self.update = None

        if not self.update:
            return False

        if self.update == "cpack_required":
            layout.alert = True
            layout.label(text="One or more cpacks outdated!")
            layout.operator(
                "hg3d.openpref", text="Open preferences", icon="PREFERENCES"
            )
            return True
        else:
            addon_label = "Add-on update available!"
            cpack_label = "CPack updates available"
            label = addon_label if self.update == "addon" else cpack_label
            layout.operator(
                "hg3d.openpref",
                text=label,
                icon="PACKAGE",
                depress=True,
                emboss=True if self.update == "addon" else False,
            )
            return False

    def _welcome_menu(self, layout):
        col = layout.column()
        col.scale_y = 4
        col.operator("hg3d.showinfo", text="Welcome to Human Generator!", depress=True)

        col_h = col.column(align=True)
        col_h.scale_y = 0.5
        col_h.alert = True

        tutorial_op = col_h.operator(
            "hg3d.draw_tutorial",
            text="Get Started!",
            depress=True,
            icon="FAKE_USER_ON",
        )
        tutorial_op.first_time = True
        tutorial_op.tutorial_name = "get_started_tutorial"

    def _warning_header(self, context, layout) -> bool:
        """Checks if context is in object mode and if a body object can be
        found

        Args:
            context (AnyType): Blender context
            layout (AnyType): Main HumGen panel layout

        Returns:
            bool: returns True if problem was found, causing panel to only show
            these error messages
        """

        if not context.mode == "OBJECT":
            layout.alert = True
            layout.label(text="HumGen only works in Object Mode")
            return True

        if self.human and "no_body" in self.human.rig_obj:
            layout.alert = True
            layout.label(text="No body object found for this rig")
            return True

        return False

    def _experimental_mode_button(self, hg_rig, row_h):
        subrow = row_h.row(align=True)
        is_expr = hg_rig.HG.experimental
        if not is_expr:
            subrow.alert = True

        subrow.operator(
            "hg3d.experimental",
            text="",
            icon="GHOST_{}".format("DISABLED" if is_expr else "ENABLED"),
            depress=True,
        )

    #   ______ .______       _______     ___   .___________. _______
    #  /      ||   _  \     |   ____|   /   \  |           ||   ____|
    # |  ,----'|  |_)  |    |  |__     /  ^  \ `---|  |----`|  |__
    # |  |     |      /     |   __|   /  /_\  \    |  |     |   __|
    # |  `----.|  |\  \----.|  |____ /  _____  \   |  |     |  |____
    #  \______|| _| `._____||_______/__/     \__\  |__|     |_______|

    def make_box_flow(self, layout, name, icon):
        """creates a box with title

        Args:
            layout (UILayout): layout to draw box in
            name (str): name to show as title
            icon (str): code for icon to display next to title

        Returns:
            tuple(flow, box):
                UILayout: flow below box
                UILayout: box itself
        """
        box = layout.box()

        row = box.row()
        row.alignment = "CENTER"
        row.label(text=name, icon=icon)

        flow = get_flow(self.sett, box)
        flow.scale_y = 1.2

        return flow, box


# TODO incorrect naming per Blender scheme
class HG_PT_ROT_LOC_SCALE(bpy.types.Panel):
    """
    Popover for the rot, loc and scale of the pattern
    """

    bl_label = "Pattern RotLocScale"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    def draw(self, context):
        layout = self.layout

        mat = context.object.active_material
        mapping_node = mat.node_tree.nodes["HG_Pattern_Mapping"]

        col = layout.column()

        col.label(text="Location")
        col.prop(mapping_node.inputs["Location"], "default_value", text="")

        col.label(text="Rotation")
        col.prop(mapping_node.inputs["Rotation"], "default_value", text="")

        col.label(text="Scale")
        col.prop(mapping_node.inputs["Scale"], "default_value", text="")
