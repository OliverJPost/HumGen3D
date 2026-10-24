# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import functools
from typing import Literal

import bpy
from .. import HumGenException
from ..backend.content import content_state
from ..backend.preferences.preference_func import get_prefs
from ..backend.setup import update_check
from ..backend.properties.ui_properties import active_phase_enum
from ..common import find_hg_rig, is_legacy, is_processed
from ..common.documentation import draw_docs_button
from ..human.human import Human

from ..user_interface.icons.icons import get_hg_icon
from .documentation.tips_suggestions_ui import draw_tips_suggestions_ui
from .panel_functions import draw_trial_buttons, draw_unreachable_folder
from functools import partial


def forbidden_for_lod(draw_method):
    @functools.wraps(draw_method)
    def wrapper(self, context):
        human = Human.from_existing(context.object)
        if human.process.is_lod:
            self.layout.alert = True
            self.layout.label(text="LOD was generated.")
            self.layout.label(text="Section has been disabled.")
            draw_docs_button(self.layout, "process/optimize-meshes", text="Learn more")
            self.layout.alert = False
            return
        return draw_method(self, context)


    return wrapper

def forbidden_for_baked(draw_method):
    @functools.wraps(draw_method)
    def wrapper(self, context):
        human = Human.from_existing(context.object)
        if human.process.was_baked:
            self.layout.alert = True
            self.layout.label(text="Materials were baked.")
            self.layout.label(text="Section has been disabled.")
            draw_docs_button(self.layout, "process/bake-textures", text="Learn more")
            self.layout.alert = False
            return
        return draw_method(self, context)

    return wrapper

def subpanel_draw(draw_method):
    @functools.wraps(draw_method)
    def wrapper(self: MainPanelPart, context):
        self.sett = context.scene.HG3D  # type:ignore[attr-defined]
        try:
            self.human = Human.from_existing(context.object)
        except HumGenException:  # no content: the labels below say what to do
            self.human = None
        if self.draw_info_and_warning_labels(context):
            return

        self.col_aligned = self.layout.column(align=True)

        self.draw_top_widget(self.col_aligned, self.human)
        self.draw_bold_title(
            self.col_aligned, self.phase_name.capitalize(), self.phase_name
        )

        draw_method(self, context)

        if get_prefs().show_tips:
            draw_tips_suggestions_ui(
                self.layout, context, docs_name="guide/" + self.phase_name.lower()
            )

    return wrapper


class HGPanel:
    bl_label = "HumGen"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"

    @staticmethod
    def draw_subtitle(
        text,
        layout,
        icon=None,
        alignment: Literal["CENTER", "LEFT", "RIGHT", "EXPAND"] = "CENTER",
    ):
        """Draw a small title that is centered. Optional icon."""
        row = layout.row()
        row.alignment = alignment
        if icon:
            if isinstance(icon, int):
                row.label(text=text, icon_value=icon)
            else:
                row.label(text=text, icon=icon)
        else:
            row.label(text=text)

    @classmethod
    def poll(cls, context):
        filepath_error = False
        human_is_legacy = is_legacy(context.object)
        # Processed humans have a panel of their own
        human_is_processed = is_processed(context.object)
        content_saving_ui = context.scene.HG3D.custom_content.content_saving_ui
        return (
            not human_is_legacy
            and not human_is_processed
            and not filepath_error
            and not content_saving_ui
        )

    def draw(self, context):
        raise NotImplementedError

    def draw_info_and_warning_labels(self, context) -> bool:
        """Collection of all info and warning labels of HumGen.

        Args:
            context : Blender Context
            layout : HumGen main panel layout

        Returns:
            bool: True if problem was found, causing the HumGen UI to stop
            displaying anything after the warning labels. Notices about
            updates never stop it, content on disk always stays usable.
        """
        layout = self.layout
        self.pref = get_prefs()
        if not self._content_found(layout):
            return True

        if not self.sett.subscribed:
            self._welcome_menu(layout)
            return True

        self._update_notification(layout)

        general_problem = self._warning_header(context, layout)
        if general_problem:  # noqa
            return True

        return False  # no problems found

    def get_flow(self, layout, animation=False) -> bpy.types.UILayout:
        """Returns a property split enabled UILayout.

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

    def _content_found(self, layout) -> bool:
        """Shows what to do when there is no content to work with.

        Args:
            layout (AnyType): Main HumGen panel layout

        Returns:
            Bool: False when the content folder is not set, empty or can't be
            found, causing the UI to cancel
        """
        folder = self.pref.filepath
        folder_state = content_state.state(folder)
        if folder_state == "installed":
            return True
        if folder_state == "unreachable":
            draw_unreachable_folder(layout, folder)
        else:
            self._setup_prompt(layout, "No content installed yet")
        return False

    @staticmethod
    def _setup_prompt(layout, text: str) -> None:
        """Point at the setup, which installs the content and sets the folder."""
        col = layout.column(align=True)
        col.label(text=text, icon="INFO")
        row = col.row(align=True)
        row.scale_y = 1.4
        row.operator("hg3d.setup_start", text="Set up Human Generator", icon="IMPORT")
        col.operator("hg3d.openpref", text="Preferences", icon="PREFERENCES", emboss=False)

    def _update_notification(self, layout) -> None:
        """A one-line banner at the top for a needed content update, and the
        message of humgen3d.com when there is one. The rest of the panel
        draws as usual: the Setup panel above has the details."""
        us = update_check.status
        if us.notice() == "required":
            row = layout.row(align=True)
            if us.blocked_by_addon:
                row.label(text="A newer Human Generator is needed for the latest content.", icon="INFO")
            else:
                row.label(text="Content update needed", icon="INFO")
                row.operator("hg3d.setup_update", text="Update", icon="IMPORT")
                row.operator("hg3d.setup_hide_updates", text="", icon="X")
        message = getattr(us, "message", "")
        if message:
            row = layout.row(align=True)
            row.label(text=message, icon="INFO")
            url = getattr(us, "message_url", "")
            if url:
                row.operator("wm.url_open", text="", icon="URL").url = url

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
        """Checks if context is in object mode and if a body object can be found.

        Args:
            context (AnyType): Blender context
            layout (AnyType): Main HumGen panel layout

        Returns:
            bool: returns True if problem was found, causing panel to only show
            these error messages
        """
        if context.mode != "OBJECT":
            layout.alert = True
            layout.label(text="HumGen only works in Object Mode")
            return True

        if self.human and "no_body" in self.human.objects.rig:
            layout.alert = True
            layout.label(text="No body object found for this rig")
            return True

        return False


def draw_icon_title(text, row, has_icon):
    row = row.row()
    row.scale_x = 0.5
    for char in text:
        if char in (" ", "_"):
            row.label(icon="BLANK1")
            continue
        if char.islower():
            char = f"{char}_lower"
        row.label(icon_value=get_hg_icon(char))

    separators = 2 + has_icon
    for _ in range(separators):
        row.separator()

    @staticmethod
    def draw_centered_subtitle(text, layout, icon=None):
        """Draw a small title that is centered. Optional icon."""
        row = layout.row()
        row.alignment = "CENTER"
        if icon:
            row.label(text=text, icon=icon)
        else:
            row.label(text=text)


class MainPanelPart(HGPanel):
    phase_name = None

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        sett = context.scene.HG3D  # type:ignore[attr-defined]
        if (
            sett.ui.active_tab != "CREATE"
            or sett.ui.phase != cls.phase_name
            or sett.custom_content.content_saving_ui
        ):
            return False
        try:
            human = Human.from_existing(context.object, strict_check=False)
        except HumGenException:  # Error for base humans not installed
            # One panel says what to do: the creation panel, unless a human is selected
            return find_hg_rig(context.object) is not None
        if not human:
            return False
        if "cloth" in context.object or "shoe" in context.object:  # noqa
            return False
        return True

    def draw_header(self, context):
        layout = self.layout
        row = layout.row(align=True)
        subrow = row.row(align=True)
        subrow.operator(
            "hg3d.section_toggle", text="Back", depress=True, icon="BACK"
        ).section_name = "closed"

        row.prop(context.scene.HG3D.ui, "phase", text="", icon_only=True)

    def draw_bold_title(self, layout, text: str, icon=None):
        col = layout.column()
        col.separator()
        col.separator()

        # Only align for expression because it's too long to fit otherwise
        row = col.row(align=(text.lower() == "expression"))

        # Get names of panels from PropertyGroup
        sections_enum = active_phase_enum(self, None)
        section_names = [name for (name, *_, idx) in sections_enum if name and idx < 11]
        section_names.remove("closed")

        # Left button
        row_l = row.row()
        row_l.alignment = "LEFT"
        prev_idx = section_names.index(self.phase_name) - 1
        prev_section = section_names[
            prev_idx if prev_idx >= 0 else len(section_names) - 1
        ]
        row_l.operator(
            "hg3d.section_toggle", text="", icon="BACK", emboss=False
        ).section_name = prev_section

        # Center title with icon prop
        row_center = row.row()
        row_center.alignment = "CENTER"
        row_center.scale_x = 0.8
        if icon:
            row_center.prop(
                self.sett.ui, "phase", text="", emboss=False, icon_only=True
            )
        draw_icon_title(text, row_center, bool(icon))

        # Right button
        row_r = row.row()
        row_r.alignment = "RIGHT"
        next_idx = section_names.index(self.phase_name) + 1
        next_section = section_names[next_idx if next_idx < len(section_names) else 0]
        row_r.operator(
            "hg3d.section_toggle", text="", icon="FORWARD", emboss=False
        ).section_name = next_section

        col.separator()

    def draw_content_selector(self, layout=None, pcoll_name=None):
        pcoll_name = pcoll_name if pcoll_name else self.phase_name
        layout = layout if layout else self.layout

        col = layout.column(align=True)

        row = col.row(align=True)
        row.prop(
            self.sett.pcoll,
            "search_term_{}".format(pcoll_name),
            text="",
            icon="VIEWZOOM",
        )
        row.operator(
            "hg3d.clear_searchbox", text="", icon="X"
        ).searchbox_name = pcoll_name

        col.template_icon_view(
            self.sett.pcoll,
            pcoll_name,
            show_labels=True,
            scale=8.4,
            scale_popup=6,
        )
        selected_item = getattr(self.sett.pcoll, pcoll_name)
        if selected_item and selected_item.lower().endswith(".trial"):
            row = col.row(align=True)
            row.scale_y = 1.5
            draw_trial_buttons(row, "library_" + pcoll_name, text="Buy Human Generator")

        row_h = col.row(align=True)
        row_h.scale_y = 1.5
        row_h.prop(self.sett.pcoll, f"{pcoll_name}_category", text="")
        row_h.operator(
            "hg3d.random_choice", text="Random", icon="FILE_REFRESH"
        ).pcoll_name = pcoll_name

    def draw_top_widget(self, layout, human):
        col = layout
        is_trial = get_prefs().is_trial
        if is_trial:
            row = col.row(align=False)
            subrow = row.row(align=True)
            subrow.alert = True
            subrow.label(text="Trial version")
            draw_trial_buttons(row, "top_widget")

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

            row = col.row(align=True)
            row.scale_x = 2
            row.operator("hg3d.deselect", text="", icon="RESTRICT_SELECT_ON")

            hair_systems = self._get_hair_systems(human.objects.body, eyesystems=True)
            self._draw_hair_children_switch(hair_systems, row)

        if self.phase_name != "closed":
            pass  # self.draw_back_button(self.layout)

    def draw_back_button(self, layout):
        row = layout.column(align=True).row()
        row.scale_y = 1.5
        subrow = row.row()
        subrow.alert = True
        subrow.operator(
            "hg3d.section_toggle", text="", depress=True, icon="BACK"
        ).section_name = "closed"

    def draw_sub_spoiler(
        self, layout, sett_namespace, prop_name, label
    ) -> "tuple[bool, bpy.types.UILayout]":
        """Draws a ciollapsable box, with title and arrow symbol.

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
            sett_namespace,
            prop_name,
            icon="TRIA_DOWN" if getattr(sett_namespace, prop_name) else "TRIA_RIGHT",
            text=label,
            emboss=False,
            toggle=True,
        )

        spoiler_open = getattr(sett_namespace, prop_name)

        return spoiler_open, boxbox

    def _get_hair_systems(self, body_obj, eyesystems=False) -> list:
        """Get a list of hair systems on this object.

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
        """Draws a switch for turning children to render amount or back to 1.

        Args:
            hair_systems (list): List of hair particle systems
            layout (UILayout): layout to draw switch in
        """

        if not hair_systems:
            layout.label(text="No hair systems found")
            return
        hair_ishidden = self.human.hair.children_ishidden
        layout.operator(
            "hg3d.togglechildren",
            text="Hair hidden" if hair_ishidden else "Hair visible",
            icon_value=get_hg_icon("hair_hidden" if hair_ishidden else "hair"),
        )

    def _get_header_label(self, human):
        if not human:
            label = "No human selected"
        else:
            name = human.name.replace("HG_", "").replace("_RIGIFY", "")
            label = f"This is {name}"
        return label

    def _draw_hair_length_ui(self, hair_systems, layout):
        """Shows a collapsable list of hair systems, with a slider for length.

        Args:
            hair_systems (list): list of particle hair systems
            box (UILayout): layout.box of hair section
        """
        is_open, box = self.draw_sub_spoiler(
            layout, self.sett.ui, "hair_length", "📏 Hair Length"
        )

        if not is_open:
            return

        if not hair_systems:
            box.label(text="No hairstyles loaded")
            return

        col = box.column(align=True)
        col.scale_y = 1.2
        for ps in hair_systems:
            ps_name = ps.name.replace("fh_", "").replace("_", " ").title()

            row = col.row(align=True)
            row.prop(ps.settings, "child_length", text=ps_name)
            row.operator("hg3d.removehair", text="", icon="TRASH").hair_system = ps.name
