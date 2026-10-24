# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

# flake8: noqa F722

import os

import bpy
from typing import no_type_check
from ...backend.auto_classes import _get_bpy_classes

from bpy.props import (  # type:ignore
    BoolProperty,
    EnumProperty,
    IntProperty,
    IntVectorProperty,
    StringProperty,
)
from bpy.types import AddonPreferences  # type:ignore

from ..content import content_state
from ..content.content_packs import cpacks_refresh

# A content folder to use while the preferences have none, for developing
# and running the tests without setting the folder in every Blender profile
DEV_CONTENT_ENV = "HUMGEN_DEV_CONTENT"

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

    sss_by_default: BoolProperty(
        default=True,
        description="Enabled subsurface scattering on the skin material by default. Looks more realistic at the cost of render time.",
        name="Subsurface Scattering by default",
    )

    @property
    def filepath(self) -> str:
        if self.filepath_:
            return self.filepath_
        return os.environ.get(DEV_CONTENT_ENV, "")

    @filepath.setter
    def filepath(self, value: str) -> None:
        self.filepath_ = value

    @property
    def is_trial(self) -> bool:
        """The trial pack without the full one, see `catalogue.is_trial_install`."""
        return content_state.is_trial(self.filepath)

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
    experimental_features: BoolProperty(
        name="Show experimental features",
        description=(
            "Show features that are still being tested: the animation library"
            " in the Pose section and the Animations section of the Process tab."
            " They can change or break between versions"
        ),
        default=False,
    )

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

    # Obsolete, Blender's online access setting decides now. Kept so stored
    # preferences still load
    skip_url_request: BoolProperty(default=True, options={"HIDDEN"})
    fake_setup: BoolProperty(
        name="Fake setup downloads",
        description="Dev tools: run the setup against a fake server, counting bytes instead of downloading",
        default=False,
    )

    show_tips: BoolProperty(default=True)
    show_other_packs: BoolProperty(
        name="Packs from other creators",
        description="Install content packs made by other creators from their files",
        default=False,
    )
    compress_zip: BoolProperty(default=True)
