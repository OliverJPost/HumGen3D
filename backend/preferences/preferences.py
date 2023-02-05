# type:ignore
# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""HumGen add-on preferences and associated functions."""

import json
import os
from typing import Optional

import bpy  # type: ignore
import HumGen3D.backend.updates.addon_updater_ops as addon_updater_ops
from HumGen3D import bl_info
from HumGen3D.user_interface.icons.icons import get_hg_icon  # type: ignore

from .content_pack_saving_ui import CpackEditingSystem
from .preference_props import HGPreferenceBackend

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
    bl_idname = __package__.split(".")[0]

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
        elif tuple(bl_info["version"]) < tuple(self.latest_version):
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

        row = box.row()
        row.alignment = "CENTER"
        row.label(text="*****************************************")

        col_h = box.column()
        col_h.scale_y = 3
        col_h.alert = update_statuscode == "cpack_required"

        col_h.operator(
            "wm.url_open",
            text=ALERT_DICT[update_statuscode][0],
            icon=ALERT_DICT[update_statuscode][1],
            depress=update_statuscode != "cpack_required",
        ).url = "https://humgen3d.com/support/update"

        box.operator(
            "wm.url_open", text="How to update?", icon="URL"
        ).url = "https://humgen3d.com/support/update"

        row = box.row()
        row.alignment = "CENTER"
        row.label(text="*****************************************")
        box.separator()
        boxbox = box.box()
        boxbox.prop(
            self,
            "update_info_ui",
            text="Update information:",
            icon="TRIA_RIGHT",
            emboss=False,
        )
        if not self.update_info_ui:
            return

        update_info_dict = self._build_update_info_dict(context)
        for version, update_types in update_info_dict.items():
            version_label = "Human Generator V" + str(version)[1:-1].replace(", ", ".")
            boxbox.label(text=version_label, icon_value=get_hg_icon("HG_icon"))
            col = boxbox.column(align=True)
            for update_type, lines in update_types.items():
                col.label(text=update_type)
                for line in lines:
                    col.label(text=line, icon="DOT")

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

        layout.separator()

        col = layout.column(heading="Color Profile Compatibility:")
        col.prop(self, "nc_colorspace_name", text="Non-color alternative naming")

        layout.separator()

        col = layout.column(heading="Tips and suggestions:")
        col.prop(self, "show_tips", text='Show "Tips and Suggestions" interface')
        col.prop(
            self,
            "full_height_menu",
            text="Make Tips and Suggestions full height",
        )

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
        col.prop(self, "skip_url_request", text="Skip URL request")

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
            subrow.prop(self, "filepath", text="")

        row.operator("hg3d.pathchange", text="Change" if self.filepath else "Select")

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

        box = col.box()
        box.label(text="Select packs to install:")

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
        """UI for when no base humans found, promting to install the content packs."""
        layout = self.layout

        # tutorial link section
        box = layout.box()
        box.scale_y = 1.5
        box.label(text="STEP 1: Follow the installation tutorial")

        row = box.row()
        row.alert = True
        row.operator(
            "wm.url_open",
            text="Updating tutorial [Opens browser]"
            if is_legacy
            else "Installation tutorial [Opens browser]",
            icon="HELP",
            depress=True,
        ).url = (
            "https://help.humgen3d.com/update"
            if is_legacy
            else "https://help.humgen3d.com/install"
        )

        # select path section
        box = layout.box()
        box.scale_y = 1.5
        box.label(
            text="STEP 2: Select a folder for HumGen to install content packs in. 2.5 GB free space recommended."  # noqa
        )

        if self.filepath:
            d_row = box.row()
            d_row.enabled = False
            d_row.prop(self, "filepath", text="")

        box.operator(
            "hg3d.pathchange",
            text="Change folder" if self.filepath else "Select folder",
            depress=not self.filepath,
            icon="FILEBROWSER",
        )
        box.label(
            text="If you've already installed content packs, just select that folder.",
            icon="INFO",
        )

        if not self.filepath:
            return

        # select packs section
        box = layout.box()
        box.label(text="STEP 3: Select packs to install")

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
        row.scale_y = 1.5
        row.operator(
            "hg3d.cpackselect",
            text="Select Content Packs",
            depress=not selected_packs,
            icon="PACKAGE",
        )

        box.label(
            text="Select multiple content packs by pressing Ctrl (Windows) or Cmd (Mac)",  # noqa
            icon="INFO",
        )
        box.label(
            text="Selected files with a red warning cannot be installed and will be skipped",  # noqa
            icon="INFO",
        )

        if selected_packs:
            # install button section
            box = layout.box()
            box.scale_y = 1.5
            box.label(text="STEP 4: Install all your content packs")
            box.operator(
                "hg3d.cpackinstall",
                text="Install All Content Packs",
                depress=True,
                icon="PACKAGE",
            )
            box.label(
                text="Installation time depends on your hardware and the selected packs",  # noqa
                icon="INFO",
            )


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
