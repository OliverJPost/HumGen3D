import bpy
from bpy.props import (  # type: ignore
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from ..callback import tab_change_update


def create_ui_toggles(ui_toggle_names):
    prop_dict = {}

    for name in ui_toggle_names:
        display_name = name.replace("_", " ").title()
        prop_dict[name] = BoolProperty(name=display_name, default=False)

    return prop_dict


class UserInterfaceProps(bpy.types.PropertyGroup):
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
        name="phase",
        items=[
            ("body", "body", "", 0),
            ("face", "face", "", 1),
            ("skin", "skin", "", 2),
            ("hair", "hair", "", 3),
            ("length", "length", "", 4),
            ("creation_phase", "Creation Phase", "", 5),
            ("clothing", "clothing", "", 6),
            ("footwear", "footwear", "", 7),
            ("pose", "pose", "", 8),
            ("expression", "expression", "", 9),
            ("simulation", "simulation", "", 10),
            ("compression", "compression", "", 11),
            ("closed", "closed", "", 12),
            ("hair2", "Hair Length", "", 13),
            ("eyes", "Eyes", "", 14),
        ],
        default="body",
    )

    active_tab: EnumProperty(
        name="ui_tab",
        items=[
            ("CREATE", "Create", "", "OUTLINER_OB_ARMATURE", 0),
            ("BATCH", "Batch", "", "COMMUNITY", 1),
            ("TOOLS", "Tools", "", "SETTINGS", 2),
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
