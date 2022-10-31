# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

# type:ignore

""" # noqa D400
context.scene.HG3D.ui

Properties related to the user interface of Human Generator.
"""


import bpy
from bpy.props import BoolProperty, EnumProperty  # type:ignore
from HumGen3D import Human
from HumGen3D.user_interface.icons.icons import get_hg_icon  # type: ignore

from ..callback import hg_callback, tab_change_update


def get_hair_tab_items(_, context):
    hair_enum = [
        ("head", "Head", "", get_hg_icon("hair"), 0),
        ("eye", "Eye", "", get_hg_icon("eyes"), 2),
    ]
    human = Human.from_existing(context.object)
    if human.gender == "male":
        hair_enum.append(("face", "Face", "", 1))

    return hair_enum


def create_ui_toggles(ui_toggle_names):
    """Function for creating BoolProperties in a loop to prevent repetition."""
    prop_dict = {}

    for name in ui_toggle_names:
        display_name = name.replace("_", " ").title()
        default = name in ("hair_mat",)
        prop_dict[name] = BoolProperty(name=display_name, default=default)

    return prop_dict


def panel_update(self, context):
    active_panel = self.phase
    if active_panel in ("create", "batch", "content", "process"):
        self.active_tab = active_panel.upper()
        self.phase = "closed"
    hg_callback(self)


# As separate function so icon_id updates correctly
def active_tab_enum(self, context):
    try:
        return [
            ("CREATE", "Create", "", get_hg_icon("create"), 0),
            ("BATCH", "Batch Generator", "", get_hg_icon("batch"), 1),
            ("CONTENT", "Custom Content", "", get_hg_icon("custom_content"), 2),
            ("PROCESS", "Process", "", get_hg_icon("export"), 3),
        ]
    except IndexError:
        return []


# As separate function so icon_id updates correctly
def active_phase_enum(self, context):
    try:
        return [
            ("", "Editing", ""),
            ("closed", "All Categories", "", "COLLAPSEMENU", 0),
            ("body", "Body", "", get_hg_icon("body"), 1),
            ("face", "Face", "", get_hg_icon("face"), 3),
            ("height", "Height", "", get_hg_icon("height"), 2),
            ("skin", "Skin", "", get_hg_icon("skin"), 4),
            ("hair", "Hair", "", get_hg_icon("hair"), 6),
            ("outfit", "Outfit", "", get_hg_icon("outfit"), 7),
            ("footwear", "Footwear", "", get_hg_icon("footwear"), 8),
            ("pose", "Pose", "", get_hg_icon("pose"), 9),
            ("expression", "Expression", "", get_hg_icon("expression"), 10),
            ("", "Tabs", ""),
            ("create", "Create Humans", "", get_hg_icon("create"), 11),
            ("batch", "Batch Generator", "", get_hg_icon("batch"), 12),
            ("content", "Custom Content", "", get_hg_icon("custom_content"), 13),
            ("process", "Processing", "", get_hg_icon("export"), 14),
        ]
    except IndexError:
        return []


class UserInterfaceProps(bpy.types.PropertyGroup):
    """Subclass of HG_SETTINGS, contains user interface properties."""

    _register_priority = 4

    # UI box toggles
    __annotations__.update(  # noqa: CCE002,  CCE001
        create_ui_toggles(
            [
                "indiv_scale",
                "hair_length",
                "face_hair",
                "hair_mat",
                "hair_cards",
                "makeup",
                "beard_shadow",
                "main_skin",
                "light_dark",
                "freckles",
                "age",
                "beautyspots",
                "texture",
                "material",
                "pattern_bool",
                "decal_bool",
                "thumb_ui",
                "expression_slider",
                "content_saving",
                "other",
                "main",
                "eyes",
            ]
        )
    )

    # Face category toggles
    __annotations__.update(  # noqa: CCE002, CCE001
        create_ui_toggles(
            [
                "nose",
                "cheeks",
                "eyes",
                "l_skull",
                "u_skull",
                "chin",
                "ears",
                "mouth",
                "jaw",
                "other",
                "custom",
                "presets",
            ]
        )
    )

    phase: EnumProperty(
        name="Category",
        items=active_phase_enum,
        update=panel_update,
    )

    active_tab: EnumProperty(
        name="Tab",
        items=active_tab_enum,
        update=tab_change_update,
    )

    pose_tab_switch: EnumProperty(
        name="posing",
        items=[
            ("library", "Library", "", 0),
            ("rigify", "Rigify", "", 1),
        ],
        default="library",
    )

    expression_type: EnumProperty(
        name="Expression",
        items=[
            ("1click", "1-Click", "", 0),
            ("frig", "Face Rig", "", 1),
        ],
        default="1click",
    )

    hair_ui_tab: EnumProperty(
        name="Hair Tab",
        items=get_hair_tab_items,
    )
