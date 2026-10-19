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
from .preference_props import HGPreferenceBackend
from ..setup import online, repository, update_check
from ..setup.catalogue import version_text
from ... import __version__

ALERT_DICT = {
    "cpack_required": [
        "One or more Content Packs are incompatible and need to be updated!",
        "ERROR",
    ],
    "addon": [
        "A new update of the Human Generator add-on is available!",
        "INFO",
    ],
    "cpack_available": [
        "One or more Content Packs can be updated!",
        "INFO",
    ],
}


class HG_PREF(CpackEditingSystem, HGPreferenceBackend, bpy.types.AddonPreferences):
    """HumGen user preferences."""

    _register_priority = 1
    # The package name differs between the legacy add-on and the extension
    bl_idname = addon_package()

    def draw(self, context):
        # check if base content is installed, otherwise show installation ui
        base_content_found, is_legacy = self._check_if_basecontent_is_installed()
        if not base_content_found:
            self._draw_first_time_ui(context)
            return

        if is_legacy:
            legacy_text = [
                "Folder selected, but contains legacy content.",
                "To prevent textures dissapearing from old humans, select a new folder!",
                "Follow the update instructions from the button below.",
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
            with open(base_humans_path, "r") as f:
                base_content = json.load(f)
            if base_content["config"]["pack_version"][0] < 4:
                return True, True

        return base_content_found, False  # noqa

    def _get_update_statuscode(self) -> Optional[str]:
        """Gets update code from check that was done when Blender was opened.

        Returns:
            str: Code determining what kind of update is available, if any
        """
        if self.cpack_update_required:
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
        box = col.box().column(align=True)
        box.alert = update_statuscode == "cpack_required"
        box.label(text=ALERT_DICT[update_statuscode][0], icon=ALERT_DICT[update_statuscode][1])
        box.alert = False
        row = box.row(align=True)
        row.scale_y = 1.5
        if update_statuscode in ("cpack_required", "cpack_available"):
            us = update_check.status
            if us.blocked_by_addon:
                row.label(text="Update the add-on first, then the content packs.", icon="INFO")
            else:
                row.operator("hg3d.setup_update", text="Update content packs", icon="IMPORT", depress=True)
        else:
            self._draw_addon_update_row(row)
        box.operator("wm.url_open", text="How to update?", icon="URL").url = docs_url("guide/installation")

    def _draw_addon_update_row(self, row):
        """Where the add-on update comes from depends on how it was installed."""
        if is_extension():
            if repository.installed_from_site():
                row.label(text="Update it in Blender's extension list (Get Extensions).", icon="INFO")
            else:
                row.operator("hg3d.add_extension_repo", text="Enable add-on updates", icon="URL", depress=True)
        else:
            row.label(text="Use the updater below, or the extension on Blender 4.2 and later.", icon="INFO")

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
        row.label(text="Install path:")

        if self.filepath:
            subrow = row.row()
            subrow.enabled = False
            subrow.prop(self, "filepath_", text="")

        row.operator("hg3d.pathchange", text="Change" if self.filepath else "Select")

        self._draw_update_check_row(col)
        us = update_check.status
        if us.updates and not us.blocked_by_addon:
            row = col.row()
            row.scale_y = 1.3
            names = ", ".join(f"{u.pack.name} {version_text(u.target.version)}" for u in us.updates if u.target)
            row.operator("hg3d.setup_update", text=f"Update {len(us.updates)} pack(s): {names}", icon="IMPORT", depress=True)

        trial_pack_installed = "Trial Content" in [f.name for f in context.scene.contentpacks_col]

        if trial_pack_installed:
            row = col.row()
            row.alert = True
            row.label(text="Are you upgrading from the trial to full HG? First delete the Trial Content Pack below", icon="ERROR")

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
        row.operator("hg3d.setup_start", text="Install or add content packs", icon="IMPORT")

        box = col.box()
        box.label(text="Install from file (packs downloaded from Superhive, or made by someone else):")

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

        row = box.row()
        row.scale_y = 1.5
        row.operator(
            "hg3d.cpackselect",
            text="Select Content Packs",
            depress=not selected_packs,
            icon="PACKAGE",
        )

        if selected_packs:
            box = col.box()
            box.label(text="Install selected packs")

            row = box.row()
            row.scale_y = 1.5
            row.operator(
                "hg3d.cpackinstall",
                text="Install Selected Content Packs",
                depress=True,
                icon="PACKAGE",
            )

        box = layout.box()
        box.scale_y = 1.5
        box.label(text="Create your own content pack:")
        row = box.row()
        row.prop(self, "cpack_name", text="Pack name")
        row.operator("hg3d.create_cpack", text="Create pack", depress=True)

    def _draw_warning(self, layout, message):
        """Draw a warrning label that's right aligned."""
        row = layout.row()
        row.alignment = "RIGHT"
        row.label(text=message, icon="ERROR")

    def _draw_first_time_ui(self, context, is_legacy=False):
        """UI for when no base humans found: the setup, and the file-based install as the way around it."""
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

        box = layout.box()
        box.label(text="Install from file (packs downloaded from Superhive, or made by someone else)")
        if not self.filepath:
            box.label(text="Select a content folder first.", icon="INFO")
            return
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
        selected_packs = bool(context.scene.installpacks_col)
        row = box.row()
        row.operator("hg3d.cpackselect", text="Select content pack files", icon="PACKAGE")
        if selected_packs:
            row.operator("hg3d.cpackinstall", text="Install selected packs", depress=True, icon="PACKAGE")


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
