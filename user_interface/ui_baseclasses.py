import functools
import os
from pathlib import Path
from re import L
from tokenize import Triple

import bpy
from HumGen3D import bl_info
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.human.human import Human

from ..backend.preview_collections import get_hg_icon
from .tips_suggestions_ui import draw_tips_suggestions_ui


def subpanel_draw(draw_method):
    @functools.wraps(draw_method)
    def wrapper(self: MainPanelPart, context):
        self.human = Human.from_existing(context.object)
        self.sett = context.scene.HG3D
        if self.draw_info_and_warning_labels(context):
            return

        self.col_aligned = self.layout.column(align=True)

        self.draw_top_widget(self.col_aligned, self.human)
        self.draw_bold_title(
            self.col_aligned, self.phase_name.capitalize(), self.phase_name
        )

        draw_method(self, context)

        if get_prefs().show_tips:
            draw_tips_suggestions_ui(self.layout, context)

    return wrapper


class HGPanel:
    bl_label = "HumGen"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"

    def draw(self, context):
        raise NotImplementedError

    def draw_info_and_warning_labels(self, context) -> bool:
        """Collection of all info and warning labels of HumGen

        Args:
            context : Blender Context
            layout : HumGen main panel layout

        Returns:
            bool: True if problem was found, causing the HumGen UI to stop
            displaying anything after the warning labels
        """
        layout = self.layout
        self.pref = get_prefs()
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

    def get_flow(self, layout, animation=False) -> bpy.types.UILayout:
        """Returns a property split enabled UILayout

        Args:
            sett (PropertyGroup): HumGen props
            layout (UILayout): layout to draw flor in
            animation (bool, optional): show keyframe dot on row. Defaults to False.

        Returns:
            UILayout: flow layout
        """

        col_2 = layout.column(align=True)
        col_2.use_property_split = True
        col_2.use_property_decorate = animation

        flow = col_2.grid_flow(
            row_major=False,
            columns=1,
            even_columns=True,
            even_rows=False,
            align=True,
        )  # TODO is this even necessary now property split is used?
        return flow

    def searchbox(self, sett, name, layout):
        """draws a searchbox of the given preview collection

        Arg:
            sett (PropertyGroup): HumGen props
            name (str): name of the preview collection to search
            layout (UILayout): layout to draw search box in
        """
        row = layout.row(align=True)
        row.prop(sett.pcoll, "search_term_{}".format(name), text="", icon="VIEWZOOM")

        if hasattr(sett.pcoll, f"search_term_{name}"):
            row.operator(
                "hg3d.clear_searchbox", text="", icon="X"
            ).searchbox_name = name


class MainPanelPart(HGPanel):
    phase_name = None

    def draw_header(self, context):
        layout = self.layout
        row = layout.row()
        row.alert = True
        row.operator(
            "hg3d.section_toggle", text="Back", depress=True, icon="BACK"
        ).section_name = "closed"

    def draw_bold_title(self, layout, text: str, icon=None):
        box = layout.column()
        box.separator()
        box.separator()
        row = box.row()
        row.alignment = "CENTER"
        row.scale_x = 0.7
        if icon:
            row.prop(self.sett.ui, "phase", text="", emboss=False, icon_only=True)
        row = row.row()
        row.scale_x = 0.5
        for char in text:
            if char in (" ", "_"):
                row.label(icon="BLANK1")
                continue
            if char.islower():
                char = f"{char}_lower"
            row.label(icon_value=get_hg_icon(char))

        separators = 2 + bool(icon)
        for _ in range(separators):
            row.separator()

        box.separator()

    def draw_top_widget(self, layout, human):
        col = layout

        row = col.row(align=True)
        row.scale_y = 1.5
        row.scale_x = 0.9
        row.operator(
            "hg3d.next_prev_human", text="", icon="TRIA_LEFT", depress=True
        ).forward = False
        row.operator(
            "hg3d.next_prev_human", text="", icon="TRIA_RIGHT", depress=True
        ).forward = True
        # button showing name and gender of human
        row.operator(
            "view3d.view_selected",
            text=self._get_header_label(human),
            depress=bool(human),
        )
        if human:
            subrow = row.row(align=True)
            subrow.alert = True
            subrow.scale_x = 1.2
            subrow.operator("hg3d.delete", text="", icon="TRASH")  # , depress=True)

            box = col.box()
            hair_systems = self._get_hair_systems(human.body_obj, eyesystems=True)
            self._draw_hair_children_switch(hair_systems, box)

        if self.phase_name != "closed":
            pass  # self.draw_back_button(self.layout)

    @classmethod
    def poll(cls, context):
        sett = context.scene.HG3D
        if not sett.ui.active_tab == "CREATE":
            return False
        elif not sett.ui.phase == cls.phase_name:
            return False
        elif sett.custom_content.content_saving_ui:
            return False
        human = Human.from_existing(context.object, strict_check=False)
        if not human:
            return False
        if human.is_batch_result[0]:
            return False
        return True

    def draw_back_button(self, layout):
        row = layout.column(align=True).row()
        row.scale_y = 1.5
        subrow = row.row()
        subrow.alert = True
        subrow.operator(
            "hg3d.section_toggle", text="", depress=True, icon="BACK"
        ).section_name = "closed"

    def draw_sub_spoiler(
        self, layout, sett, prop_name, label
    ) -> "tuple[bool, bpy.types.UILayout]":
        """Draws a ciollapsable box, with title and arrow symbol

        Args:
            layout (UILayout): Layout to draw spoiler in
            sett (PropertyGroup): HumGen Props
            prop_name (str): Name of the BoolProperty that opens/closes spoiler
            label (str): Label to display in the ui

        Returns:
            tuple[bool, bpy.types.UILayout]:
                bool: True means the box will open in the UI
                UILayout: layout.box to draw items inside the openable box
        """
        boxbox = layout.box()
        boxbox.prop(
            sett.ui,
            prop_name,
            icon="TRIA_DOWN" if getattr(sett.ui, prop_name) else "TRIA_RIGHT",
            text=label,
            emboss=False,
            toggle=True,
        )

        spoiler_open = getattr(sett.ui, prop_name)

        return spoiler_open, boxbox

    def _get_hair_systems(self, body_obj, eyesystems=False) -> list:
        """get a list of hair systems on this object

        Args:
            body_obj (Object): HumGen body object, can be any mesh object

        Returns:
            list: list of hair particle systems
        """

        hair_systems = []
        for mod in body_obj.modifiers:
            if mod.type == "PARTICLE_SYSTEM" and (
                eyesystems
                or not mod.particle_system.name.startswith(("Eyebrows", "Eyelashes"))
            ):
                hair_systems.append(mod.particle_system)

        return hair_systems

    def _draw_hair_children_switch(self, hair_systems, layout):
        """Draws a switch for turning children to render amount or back to 1

        Args:
            hair_systems (list): List of hair particle systems
            layout (UILayout): layout to draw switch in
        """

        row = layout.row(align=True)
        if not hair_systems:
            row.label(text="No hair systems found")
            return

        row.label(
            text=(
                "Hair children are hidden"
                if self.human.hair.children_ishidden
                else "Hair children are visible"
            )
        )
        row.operator(
            "hg3d.togglechildren",
            text="",
            icon=("HIDE_ON" if hair_systems[0].settings.child_nbr <= 1 else "HIDE_OFF"),
        )

    def _get_header_label(self, human):
        if not human:
            label = "No human selected"
        else:
            name = human.name.replace("HG_", "").replace("_RIGIFY", "")
            gender = human.gender.capitalize()
            label = f"This is {name}"
        return label

    def _draw_hair_length_ui(self, hair_systems, box):
        """shows a collapsable list of hair systems, with a slider for length

        Args:
            hair_systems (list): list of particle hair systems
            box (UILayout): layout.box of hair section
        """
        boxbox = box.box()
        boxbox.prop(
            self.sett.ui,
            "hair_length",
            icon="TRIA_DOWN" if self.sett.ui.hair_length else "TRIA_RIGHT",
            emboss=False,
            toggle=True,
        )
        if not self.sett.ui.hair_length:
            return

        if not hair_systems:
            box.label(text="No hairstyles loaded")
            return

        flow = self.get_flow(box)
        for ps in hair_systems:
            ps_name = ps.name.replace("fh_", "").replace("_", " ").title()

            row = flow.row()
            row.prop(ps.settings, "child_length", text=ps_name)
            row.operator("hg3d.removehair", text="", icon="TRASH").hair_system = ps.name

    @staticmethod
    def draw_centered_subtitle(text, layout, icon=None):
        """Draw a small title that is centered. Optional icon."""
        row = layout.row()
        row.alignment = "CENTER"
        if icon:
            row.label(text=text, icon=icon)
        else:
            row.label(text=text)
