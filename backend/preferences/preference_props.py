# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

# flake8: noqa F722

import getpass
import bpy
from typing import no_type_check
from HumGen3D.backend.auto_classes import _get_bpy_classes

from bpy.props import (  # type:ignore
    BoolProperty,
    EnumProperty,
    IntProperty,
    IntVectorProperty,
    StringProperty,
)
from bpy.types import AddonPreferences  # type:ignore

from ..content.content_packs import cpacks_refresh

def update_tab_name(self, context):
    """Dynamically change category & reload some panel upon update.
    Taken from Geo-Scatter addon.
    """

    hg_classes = _get_bpy_classes()
    ui_tab_classes = [cls for cls in hg_classes if hasattr(cls, "bl_category")]

    for cls in reversed(ui_tab_classes):
        if (cls.is_registered):
            bpy.utils.unregister_class(cls)

    for cls in ui_tab_classes:
        if (not cls.is_registered):
            cls.bl_category = self.tab_name
            bpy.utils.register_class(cls)

    return None


class HGPreferenceBackend:
    auto_check_update: BoolProperty(
        name="Auto-check for Update",
        description="If enabled, auto-check for updates using an interval",
        default=False,
    )

    updater_interval_months: IntProperty(
        name="Months",
        description="Number of months between checking for updates",
        default=0,
        min=0,
    )

    updater_interval_days: IntProperty(
        name="Days",
        description="Number of days between checking for updates",
        default=7,
        min=0,
        max=31,
    )

    updater_interval_hours: IntProperty(
        name="Hours",
        description="Number of hours between checking for updates",
        default=0,
        min=0,
        max=23,
    )

    updater_interval_minutes: IntProperty(
        name="Minutes",
        description="Number of minutes between checking for updates",
        default=0,
        min=0,
        max=59,
    )

    filepath_: StringProperty(
        name="Install Filepath",
        default="",
    )

    tab_name : StringProperty(
        default="HumGen",
        update=update_tab_name,
        )

    @property
    def filepath(self) -> str:
        if self.filepath_:
            return self.filepath_
        else:
            # Return hard coded path if developing from my computer, prevents having to remove path for every release.
            if getpass.getuser() == "ole":
                return "/Users/ole/Library/Mobile Documents/com~apple~CloudDocs/Areas/Human Generator/Content/"
            else:
                return ""

    @filepath.setter
    def filepath(self, value: str) -> None:
        self.filepath_ = value

    # update props
    latest_version: IntVectorProperty(default=(0, 0, 0))
    cpack_update_available: BoolProperty(default=False)
    cpack_update_required: BoolProperty(default=False)
    update_info_ui: BoolProperty(default=True)
    # main prefs UI props
    pref_tabs: EnumProperty(
        name="tabs",
        description="",
        items=[
            ("settings", "Settings", "", "INFO", 0),
            ("cpacks", "Content Packs", "", "INFO", 1),
        ],
        default="settings",
        update=cpacks_refresh,
    )

    # cpack user preferences
    units: EnumProperty(
        name="units",
        description="",
        items=[
            ("metric", "Metric", "", 0),
            ("imperial", "Imperial", "", 1),
        ],
        default="metric",
    )
    hair_section: EnumProperty(
        name="Show hair section",
        description="",
        items=[
            ("both", "Both phases", "", 0),
            ("creation", "Creation phase only", "", 1),
            ("finalize", "Finalize phase only", "", 2),
        ],
        default="creation",
    )

    show_confirmation: BoolProperty(default=True)
    dev_tools: BoolProperty(
        name="Show Dev Tools", description="", default=False
    )  # RELEASE set to False

    auto_hide_hair_switch: BoolProperty(default=True)
    auto_hide_popup: BoolProperty(default=True)
    remove_clothes: BoolProperty(default=True)

    compact_ff_ui: BoolProperty(name="Compact face UI", default=False)
    keep_all_shapekeys: BoolProperty(
        name="Keep all shapekeys after creation phase", default=False
    )

    nc_colorspace_name: StringProperty(default="")
    debug_mode: BoolProperty(default=False)
    silence_all_console_messages: BoolProperty(default=False)

    skip_url_request: BoolProperty(default=True)

    show_tips: BoolProperty(default=True)
    compress_zip: BoolProperty(default=True)
