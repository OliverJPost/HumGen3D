"""
context.scene.HG3D.ui
Properties related to the user interface of Human Generator.
"""

from re import L

import bpy
from bpy.props import BoolProperty, EnumProperty
from HumGen3D.backend.preview_collections import get_hg_icon  # type: ignore

from ..callback import hg_callback, tab_change_update


def create_ui_toggles(ui_toggle_names):
    """Function for creating BoolProperties in a loop to prevent repetition."""
    prop_dict = {}

    for name in ui_toggle_names:
        display_name = name.replace("_", " ").title()
        prop_dict[name] = BoolProperty(name=display_name, default=False)

    return prop_dict


def panel_update(self, context):
    active_panel = self.phase
    if active_panel in ("create", "batch", "content", "process"):
        self.active_tab = active_panel.upper()
        self.phase = "closed"
    hg_callback(self)


class UserInterfaceProps(bpy.types.PropertyGroup):
    """Subclass of HG_SETTINGS, contains user interface properties"""

    # UI box toggles
    __annotations__.update(
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
            ]
        )
    )

    # Face category toggles
    __annotations__.update(
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
        items=[
            ("", "Editing", ""),
            ("closed", "All Categories", "", "COLLAPSEMENU", 0),
            ("body", "Body", "", get_hg_icon("body"), 1),
            ("face", "Face", "", get_hg_icon("face"), 3),
            ("height", "Height", "", get_hg_icon("height"), 2),
            ("skin", "Skin", "", get_hg_icon("skin"), 4),
            ("eyes", "Eyes", "", get_hg_icon("eyes"), 5),
            ("hair", "Hair", "", get_hg_icon("hair"), 6),
            ("outfit", "Outfit", "", get_hg_icon("outfit"), 7),
            ("footwear", "Footwear", "", get_hg_icon("footwear"), 8),
            ("pose", "Pose", "", get_hg_icon("pose"), 9),
            ("expression", "Expression", "", get_hg_icon("expression"), 10),
            ("", "Tabs", ""),
            ("create", "Create Humans", "", get_hg_icon("create"), 11),
            ("batch", "Batch Generator", "", get_hg_icon("batch"), 12),
            ("content", "Custom Content", "", get_hg_icon("custom_content"), 12),
            ("process", "Processing", "", get_hg_icon("export"), 12),
        ],
        default="body",
        update=panel_update,
    )

    active_tab: EnumProperty(
        name="Tab",
        items=[
            ("CREATE", "Create", "", get_hg_icon("create"), 0),
            ("BATCH", "Batch Generator", "", get_hg_icon("batch"), 1),
            ("CONTENT", "Custom Content", "", get_hg_icon("custom_content"), 2),
            ("PROCESS", "Process", "", get_hg_icon("export"), 3),
        ],
        default="CREATE",
        update=tab_change_update,
    )

    # pose
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
