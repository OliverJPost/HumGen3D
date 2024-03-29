# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import contextlib

import bpy
from HumGen3D import Human
from HumGen3D.backend.callback import hg_callback
from HumGen3D.backend.preferences.preference_func import (
    get_prefs,
    open_preferences_as_new_window,
)

from .documentation.info_popups import HG_OT_INFO
from .documentation.tips_suggestions_ui import update_tips_from_context


class HG_SECTION_TOGGLE(bpy.types.Operator):
    """
    Button for switching to one of the sections.

    Args:
        section_name (str): name of the section to toggle
    """

    bl_idname = "hg3d.section_toggle"
    bl_label = ""
    bl_description = """
        Open this menu
        CTRL+Click to keep hair children turned on
        """

    section_name: bpy.props.StringProperty()
    children_hide_exception: bpy.props.BoolProperty(default=False)

    def invoke(self, context, event):
        self.children_hide_exception = event.ctrl
        return self.execute(context)

    def execute(self, context):
        human = Human.from_existing(context.object)
        sett = context.scene.HG3D  # type:ignore[attr-defined]
        sett.ui.phase = self.section_name

        hg_callback(self)

        pref = get_prefs()
        if (
            pref.auto_hide_hair_switch  # Turned on in preferences
            and not self.children_hide_exception  # User did not hold Ctrl
            and self.section_name not in ("hair", "eyes")  # It's not the hair tab
            and not human.hair.children_ishidden  # The children weren't already hidden
        ):
            self.hide_hair_and_show_notification(human, pref)

        return {"FINISHED"}

    def hide_hair_and_show_notification(self, human, pref):
        human.hair.children_set_hide(True)
        self.report(
            {"INFO"},
            "Hair children were hidden to improve performance.",
        )

        if pref.auto_hide_popup:
            HG_OT_INFO.ShowMessageBox(None, "autohide_hair")


class HG_OPENPREF(bpy.types.Operator):
    """Opens the preferences.

    API: False

    Operator type:
        Blender UI manipulation

    Prereq:
        None
    """

    bl_idname = "hg3d.openpref"
    bl_label = ""
    bl_description = "Opens the preferences window"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        open_preferences_as_new_window()
        return {"FINISHED"}


class HG_CLEAR_SEARCH(bpy.types.Operator):
    """Clears the passed searchfield."""

    bl_idname = "hg3d.clear_searchbox"
    bl_label = "Clear search"
    bl_description = "Clears the searchbox"

    searchbox_name: bpy.props.StringProperty()

    def execute(self, context):
        sett = context.scene.HG3D  # type:ignore[attr-defined]
        human = Human.from_existing(context.object)
        if self.searchbox_name == "cpack_creator":
            get_prefs().cpack_content_search = ""
        else:
            sett.pcoll[f"search_term_{self.searchbox_name}"] = ""
            getattr(human, self.searchbox_name).refresh_pcoll(context)

        return {"FINISHED"}


class HG_NEXTPREV_CONTENT_SAVING_TAB(bpy.types.Operator):

    bl_idname = "hg3d.nextprev_content_saving_tab"
    bl_label = "Next/previous"
    bl_description = "Next/previous tab"

    go_next: bpy.props.BoolProperty()

    def execute(self, context):
        sett = context.scene.HG3D  # type:ignore[attr-defined]
        sett.custom_content.content_saving_tab_index += 1 if self.go_next else -1

        update_tips_from_context(
            context,
            sett,
            Human.from_existing(sett.custom_content.content_saving_active_human),
        )

        return {"FINISHED"}


class HG_OT_CANCEL_CONTENT_SAVING_UI(bpy.types.Operator):
    """Takes the user our of the content saving UI, pack into the standard interface."""

    bl_idname = "hg3d.cancel_content_saving_ui"
    bl_label = "Close this menu"
    bl_description = "Close this menu"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        # confirmation checkbox
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        sett = context.scene.HG3D  # type:ignore[attr-defined]
        sett.custom_content.content_saving_ui = False

        update_tips_from_context(
            context,
            sett,
            Human.from_existing(sett.custom_content.content_saving_active_human),
        )
        return {"FINISHED"}
