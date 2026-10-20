# type:ignore
# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""HumGen add-on preferences and associated functions."""

import json
import os
from typing import Optional

import bpy  # type: ignore
from ...backend.updates import addon_updater_ops as addon_updater_ops
from ...common.documentation import docs_url
from ...package import addon_package, is_extension
from ...user_interface.icons.icons import get_hg_icon  # type: ignore

from .content_pack_saving_ui import CpackEditingSystem
from .licence import licence_row, support_url
from .preference_props import HGPreferenceBackend
from ..content import content_state
from ..setup import online, repository, update_check, user_settings
from ..setup.catalogue import version_text
from ...common.i18n import tr
from ...user_interface.panel_functions import draw_unreachable_folder
from ...user_interface.setup_overlay.operator import draw_forget_button
from ... import __version__


def pack_names(statuses) -> str:
    """"Base Humans" or "Base Humans, Base Hair" for an alert."""
    return ", ".join(s.pack.name for s in statuses)


def alert_text(update_statuscode: str, us) -> str:
    """The alert at the top of the preferences, naming the packs."""
    if update_statuscode == "cpack_required":
        if us.blocked_by_addon:
            return tr("A newer Human Generator is needed for the latest content.")
        required = us.required
        if len(required) == 1:
            return tr("{pack} needs an update.").format(pack=pack_names(required))
        if required:
            return tr("{packs} need an update.").format(packs=pack_names(required))
        return tr("Some content packs need an update.")
    if update_statuscode == "addon":
        return tr("A new version of Human Generator is available.")
    updates = us.updates
    if updates:
        return tr("Updates are available for {packs}.").format(packs=pack_names(updates))
    return tr("Content pack updates are available.")


class HG_PREF(CpackEditingSystem, HGPreferenceBackend, bpy.types.AddonPreferences):
    """HumGen user preferences."""

    _register_priority = 1
    # The package name differs between the legacy add-on and the extension
    bl_idname = addon_package()

    def draw(self, context):
        if content_state.state(self.filepath) == "unreachable":
            draw_unreachable_folder(self.layout, self.filepath)
            if not is_extension():
                addon_updater_ops.update_settings_ui(self, context)
            return
        # check if base content is installed, otherwise show installation ui
        base_content_found, is_legacy = self._check_if_basecontent_is_installed()
        if not base_content_found:
            self._draw_first_time_ui(context)
            return

        if is_legacy:
            legacy_text = [
                "This folder has content of an older Human Generator.",
                "Choose a new folder, so older humans keep their textures.",
                "The button below explains how to update.",
            ]
            for line in legacy_text:
                row = self.layout.box().row()
                row.alignment = "CENTER"
                row.alert = True
                row.label(text=line)
            self._draw_first_time_ui(context, is_legacy=True)
            return

        layout = self.layout
        col = layout.column()

        if self.editing_cpack:
            self._draw_cpack_editing_ui(layout, context)
            return
        elif self.show_content_overview:
            self._draw_content_overview_ui(layout, context)
            return

        update_statuscode = self._get_update_statuscode()

        if update_statuscode:
            self._draw_update_notification(context, col, update_statuscode)

        row = col.box().row(align=True)
        row.scale_y = 2
        row.prop(self, "pref_tabs", expand=True)

        if self.pref_tabs == "settings":
            self._draw_settings_ui()
        elif self.pref_tabs == "cpacks":
            self._draw_cpack_ui(context)

        # As an extension, Blender's repository handles updates
        if not is_extension():
            addon_updater_ops.update_settings_ui(self, context)

    def _check_if_basecontent_is_installed(self) -> tuple[bool, bool]:
        """Determines if this is the first time loading Human Generator.

        Checks if the base content is installed

        Returns:
            bool: True if base content is installed
        """
        base_humans_path = os.path.join(
            self.filepath, "content_packs", "Base_Humans.json"
        )
        base_content_found = (
            os.path.exists(base_humans_path) if self.filepath else False
        )

        trial_humans_path = os.path.join(
            self.filepath, "content_packs", "Trial_Content.json"
        )
        trial_content_found = (
            os.path.exists(trial_humans_path) if self.filepath else False
        )
        if trial_content_found:
            return True, False

        # Check if base content is legacy
        if base_content_found:
            try:
                with open(base_humans_path, "r", encoding="utf-8") as f:
                    base_content = json.load(f)
                if base_content["config"]["pack_version"][0] < 4:
                    return True, True
            except (OSError, ValueError, KeyError, TypeError, IndexError):
                pass

        return base_content_found, False  # noqa

    def _get_update_statuscode(self) -> Optional[str]:
        """Gets update code from check that was done when Blender was opened.

        Returns:
            str: Code determining what kind of update is available, if any
        """
        notice = update_check.status.notice()
        if not notice:
            # Turned off by humgen3d.com, or a catalogue this version can't read
            return None
        if notice == "required" or self.cpack_update_required:
            return "cpack_required"
        elif tuple(__version__) < tuple(self.latest_version):
            return "addon"
        elif self.cpack_update_available:
            return "cpack_available"
        else:
            return None

    def _draw_update_notification(self, context, col, update_statuscode):
        """Draws notification if there is an update available.

        Args:
            col (UILayout): draw in this
            update_statuscode (str): code showing what kind of update is available
        """
        us = update_check.status
        box = col.box().column(align=True)
        box.label(text=alert_text(update_statuscode, us), icon="INFO")
        row = box.row(align=True)
        row.scale_y = 1.5
        if update_statuscode in ("cpack_required", "cpack_available") and not us.blocked_by_addon:
            row.operator("hg3d.setup_update", text=tr("Update content packs"), icon="IMPORT", depress=True)
        else:
            self._draw_addon_update_row(row)
        box.operator("wm.url_open", text=tr("How to update"), icon="URL").url = docs_url("guide/installation")

    def _draw_addon_update_row(self, row):
        """Where the add-on update comes from depends on how it was installed."""
        if is_extension():
            if repository.installed_from_site():
                row.label(text="Update it in Blender's extension list (Get Extensions).", icon="INFO")
            else:
                row.operator("hg3d.add_extension_repo", text="Enable add-on updates", icon="URL", depress=True)
        else:
            row.label(text=tr("Updates come through the updater below."), icon="INFO")

    def _draw_update_check_row(self, layout):
        """Check for updates by hand, with the state of Blender's online access."""
        us = update_check.status
        row = layout.row(align=True)
        if us.checking:
            row.label(text="Checking for updates…", icon="TIME")
        else:
            row.operator("hg3d.setup_check_updates", text="Check for updates", icon="FILE_REFRESH")
        if not online.allowed():
            if online.locked():
                row.label(text="Offline mode", icon="ERROR")
            else:
                row.operator("hg3d.setup_allow_online", text="Allow online access", icon="URL")
        elif us.checked_at:
            import time

            row.label(text=time.strftime("Last check %Y-%m-%d %H:%M", time.localtime(us.checked_at)))
        if us.error and us.error != "offline_mode":
            layout.label(text=us.error, icon="ERROR")
        if getattr(us, "message", ""):
            row = layout.row(align=True)
            row.label(text=us.message, icon="INFO")
            if getattr(us, "message_url", ""):
                row.operator("wm.url_open", text="", icon="URL").url = us.message_url

    def _draw_licence_row(self, layout):
        """The order or licence key this computer downloads with, if any."""
        credential = user_settings.credential()
        row_data = licence_row(credential)
        if row_data is None:
            return
        box = layout.box()
        if row_data.rejected:
            col = box.column(align=True)
            col.alert = True
            col.label(text=tr("Your order or licence key was not accepted."), icon="ERROR")
            col.alert = False
            sub = col.column(align=True)
            sub.enabled = False
            sub.label(text=row_data.message)
            row = box.row(align=True)
            row.operator("hg3d.setup_change_licence", text=tr("Enter again…"), icon="GREASEPENCIL")
            row.operator("wm.url_open", text=tr("Contact support"), icon="URL").url = support_url(credential.error_code)
            return
        row = box.row(align=True)
        row.label(text=row_data.tier or tr("Licence"), icon="CHECKMARK")
        sub = row.row(align=True)
        sub.enabled = False
        sub.label(text=row_data.summary)
        row = box.row(align=True)
        if row_data.upgrade:
            row.operator("hg3d.setup_open_upgrade", text=tr("Upgrade to Commercial"), icon="URL")
        row.operator("hg3d.setup_change_licence", text=tr("Change…"))
        # With its confirmation: "Forget only removes it from this computer"
        draw_forget_button(row)

    def _build_update_info_dict(self, context) -> dict:
        update_col = context.scene.hg_update_col
        update_info_dict = {}

        update_info_dict = {
            tuple(i.version): {"Features": [], "Bugfixes": []} for i in update_col
        }
        for i in update_col:
            update_info_dict[tuple(i.version)][i.categ].append(i.line)

        return update_info_dict

    def _draw_settings_ui(self):
        """UI with checkboxes and enums for changing HumGen's preferences."""
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        col = layout.column(heading="UI:")

        col.prop(self, "show_confirmation", text="Show confirmation popups")
        col.prop(
            self,
            "auto_hide_hair_switch",
            text="Auto hide hair children when switching tabs",
        )

        if not self.auto_hide_hair_switch:
            self._draw_warning(
                col, "Having auto-hide enabled improves viewport performance"
            )

        col.prop(self, "auto_hide_popup", text="Show popup when auto-hiding hair")
        col.prop(self, "compact_ff_ui")

        layout.separator()

        col = layout.column(heading="Default behaviour:")
        col.prop(
            self,
            "remove_clothes",
            text="Remove old clothes when adding new ones",
        )
        col.prop(
            self,
            "sss_by_default",
        )

        layout.separator()

        col = layout.column(heading="Color Profile Compatibility:")
        col.prop(self, "nc_colorspace_name", text="Non-color alternative naming")

        layout.separator()

        col = layout.column(heading="Tips and suggestions:")
        col.prop(self, "show_tips", text='Show "Tips and Suggestions" interface')

        layout.separator()

        col = layout.column(heading="Saving custom content:")
        col.prop(
            self,
            "compress_zip",
            text="Compress cpack .zip on export (EXPERIMENTAL)",
        )

        layout.separator()

        col = layout.column(heading="Advanced options:")
        col.prop(self, "debug_mode", text="Debug Mode")
        col.prop(
            self,
            "silence_all_console_messages",
            text="Silence all console messages",
        )
        col.prop(self, "dev_tools")
        if self.dev_tools:
            col.prop(self, "fake_setup")
        col.prop(self, "experimental_features")
        col.prop(self, "tab_name", text="N-panel tab name")

    def _draw_cpack_ui(self, context):
        """UI displaying installed content packs.

        For the user to check which cpacks are installed, who made them,
        what version they are, what is inside them and a button to delete them
        """
        layout = self.layout
        col = layout.column()

        row = col.row()
        row.label(text="Content folder:")

        if self.filepath:
            subrow = row.row()
            subrow.enabled = False
            subrow.prop(self, "filepath_", text="")

        row.operator("hg3d.pathchange", text="Change folder…" if self.filepath else "Select folder…")

        self._draw_update_check_row(col)
        self._draw_licence_row(col)
        us = update_check.status
        if us.updates and not us.blocked_by_addon:
            row = col.row()
            row.scale_y = 1.3
            names = ", ".join(f"{u.pack.name} {version_text(u.target.version)}" for u in us.updates if u.target)
            text = tr("Update {count} packs: {names}") if len(us.updates) > 1 else tr("Update {names}")
            row.operator("hg3d.setup_update", text=text.format(count=len(us.updates), names=names), icon="IMPORT", depress=True)

        row = col.row(align=False)
        row.template_list(
            "HG_UL_CONTENTPACKS",
            "",
            context.scene,
            "contentpacks_col",
            context.scene,
            "contentpacks_col_index",
            rows=10,
        )

        col_side = row.column(align=False)
        col_side.operator("hg3d.cpacksrefresh", icon="FILE_REFRESH", text="")
        col_side.popover(panel="HG_PT_ICON_LEGEND", text="", icon="PRESET")

        row = col.row()
        row.scale_y = 1.3
        # An owner adding packs goes straight to the pack list
        setup_operator = "hg3d.setup_add_packs" if self._content_installed() else "hg3d.setup_start"
        row.operator(setup_operator, text=tr("Install or add content packs"), icon="IMPORT")

        self._draw_other_creators_packs(col, context)

        box = layout.box()
        box.scale_y = 1.5
        box.label(text="Create your own content pack:")
        row = box.row()
        row.prop(self, "cpack_name", text="Pack name")
        row.operator("hg3d.create_cpack", text="Create pack", depress=True)

    def _content_installed(self) -> bool:
        return content_state.state(self.filepath) == "installed"

    def _draw_other_creators_packs(self, layout, context):
        """Packs made by other creators, installed from their files. Closed by default."""
        box = layout.box()
        box.prop(
            self,
            "show_other_packs",
            icon="TRIA_DOWN" if self.show_other_packs else "TRIA_RIGHT",
            emboss=False,
        )
        if not self.show_other_packs:
            return

        selected_packs = bool(context.scene.installpacks_col)
        if selected_packs:
            row = box.row()
            row.template_list(
                "HG_UL_INSTALLPACKS",
                "",
                context.scene,
                "installpacks_col",
                context.scene,
                "installpacks_col_index",
            )
            row.operator("hg3d.removeipack", icon="TRASH")

        row = box.row(align=True)
        row.operator("hg3d.cpackselect", text=tr("Select pack files"), icon="PACKAGE")
        if selected_packs:
            row.operator("hg3d.cpackinstall", text=tr("Install selected packs"), depress=True, icon="PACKAGE")

    def _draw_warning(self, layout, message):
        """Draw a warrning label that's right aligned."""
        row = layout.row()
        row.alignment = "RIGHT"
        row.label(text=message, icon="ERROR")

    def _draw_first_time_ui(self, context, is_legacy=False):
        """UI for when no base humans found: the setup, or a folder that has them."""
        layout = self.layout

        box = layout.box()
        box.scale_y = 1.5
        if is_legacy:
            box.label(text="Your content packs are from an older version. Update them to use this add-on.", icon="ERROR")
        else:
            box.label(text="Human Generator needs its content packs. The setup downloads them for you.")
        row = box.row()
        row.operator("hg3d.setup_start", text="Set up Human Generator", icon="IMPORT", depress=True)
        row.operator("wm.url_open", text="Installation guide", icon="HELP").url = docs_url("guide/installation")

        box = layout.box()
        box.label(text="Content folder")
        row = box.row()
        if self.filepath:
            d_row = row.row()
            d_row.enabled = False
            d_row.prop(self, "filepath", text="")
        row.operator("hg3d.pathchange", text="Change folder" if self.filepath else "Select folder", icon="FILEBROWSER")
        box.label(text="Already have the packs on this computer? Select that folder.", icon="INFO")


class HG_PT_ICON_LEGEND(bpy.types.Panel):
    """Legend popover for the icons used in the ui_list."""

    bl_label = "Icon legend"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"
    bl_ui_units_x = 8

    def draw(self, context):
        layout = self.layout

        icon_dict = {
            "Human Meshes": "humans",
            "Human Textures": "textures",
            "Shapekeys": "body",
            "Hairstyles": "hair",
            "Poses": "pose",
            "Outfits": "outfit",
            "Footwear": "footwear",
            "Expressions": "expression",
        }

        for icon_desc, icon in icon_dict.items():
            layout.label(text=icon_desc, icon_value=get_hg_icon(icon))
