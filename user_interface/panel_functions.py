# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy

from ..backend import preview_collections
from .icons.icons import get_hg_icon  # type: ignore

CHAR_WIDTH_DICT = {
    "c": 3.66,
    "E": 3.96,
    "f": 2.07,
    "F": 3.66,
    "G": 5.29,
    "i": 1.83,
    "I": 2.38,
    "j": 1.83,
    "J": 2.83,
    "k": 3.66,
    "l": 1.83,
    "m": 6.80,
    "M": 5.95,
    "O": 5.29,
    "r": 2.80,
    "s": 3.40,
    "S": 3.96,
    "t": 2.83,
    "T": 4.32,
    "w": 5.60,
    "W": 6.80,
    "z": 3.40,
}


def char_width(char: str):
    if char in CHAR_WIDTH_DICT:
        return CHAR_WIDTH_DICT[char]
    else:
        if char.isupper():
            return 4.76
        else:
            return 3.97


def draw_paragraph(
    layout, text, max_width_percentage=100, enabled=True, alignment="LEFT"
):
    words = text.split(" ")
    length = 0
    lines = [
        list(),
    ]
    for word in words:
        if "\n" in word:
            length = 0
            lines[-1].append(word)
            lines.append("WHITESPACE")
            lines.append(list())
            continue
        length += sum([char_width(char) for char in word]) + 3
        if length >= max_width_percentage:
            length = 0
            lines.append(list())

        lines[-1].append(word)

    col = layout.column(align=True)
    for line in lines:
        row = col.row()
        if line == "WHITESPACE":
            row.scale_y = 0.3
            row.label(text="")
        else:
            row.scale_y = 0.7
            row.alignment = alignment
            row.enabled = enabled
            row.label(text=" ".join(line))


def prettify(string: str) -> str:
    return string.replace("_", " ").title()


def draw_sub_spoiler(
    layout, sett, prop_name, label
) -> "tuple[bool, bpy.types.UILayout]":
    """Draws a ciollapsable box, with title and arrow symbol

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
        sett.ui,
        prop_name,
        icon="TRIA_DOWN" if getattr(sett.ui, prop_name) else "TRIA_RIGHT",
        text=label,
        emboss=False,
        toggle=True,
    )

    spoiler_open = getattr(sett.ui, prop_name)

    return spoiler_open, boxbox


def draw_panel_switch_header(layout, sett):
    """Draws a enum prop that switches between main humgen panel and extras panel

    Args:
        layout (UILayout): header layout to draw the switch in
        sett (PropertyGroup): HumGen props
    """
    row = layout.row()
    row.scale_x = 1.2
    # row.alignment = "EXPAND"
    row.prop(sett.ui, "active_tab", expand=True, icon_only=True)


def get_flow(sett, layout, animation=False) -> bpy.types.UILayout:
    """Returns a property split enabled UILayout

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
    )  # is this even necessary now property split is used?
    return flow


def draw_spoiler_box(self, layout, ui_name) -> "tuple[bool, bpy.types.UILayout]":
    """Draws the spoiler box of the main sections (i.e. body, hair, face)

    Args:
        ui_name (str): name of the category to draw spoiler for

    Returns:
        tuple[bool, bpy.types.UILayout]:
            bool: True if spoiler is open
            box: layout.box to draw the category UI in
    """

    # fallback icons for when custom ones don't load
    icon_dict = {
        "body": "COMMUNITY",
        "face": "COMMUNITY",
        "skin": "COMMUNITY",
        "hair": "OUTLINER_OB_HAIR",
        "length": "EMPTY_SINGLE_ARROW",
        "creation_phase": "COMMUNITY",
        "outfit": "MATCLOTH",
        "footwear": "MATCLOTH",
        "pose": "ARMATURE_DATA",
        "expression": "GHOST_ENABLED",
        "simulation": "NETWORK_DRIVE",
        "compression": "FOLDER_REDIRECT",
        "baking": "RENDERLAYERS",
        "apply": "MOD_SUBSURF",
    }

    long_name_dict = {"baking": "Texture Baking", "apply": "Apply Modifiers"}

    box = layout.box()

    row = box.row(align=True)
    row.scale_y = 1.0
    row.alignment = "LEFT"

    if ui_name in long_name_dict:
        label = long_name_dict[ui_name]
    else:
        label = ui_name.capitalize().replace("_", " ")

    try:
        row.operator(
            "hg3d.section_toggle",
            text=label,
            icon_value=get_hg_icon(ui_name),
            emboss=False,
        ).section_name = ui_name
    except:
        icon = icon_dict[ui_name]
        row.operator(
            "hg3d.section_toggle", text=label, icon=icon, emboss=False
        ).section_name = ui_name

    is_open = True if self.sett.ui.phase == ui_name else False
    return is_open, box


def searchbox(sett, name, layout):
    """draws a searchbox of the given preview collection

    Args:
        sett (PropertyGroup): HumGen props
        name (str): name of the preview collection to search
        layout (UILayout): layout to draw search box in
    """
    row = layout.row(align=True)
    row.prop(sett.pcoll, "search_term_{}".format(name), text="", icon="VIEWZOOM")

    if hasattr(sett.pcoll, f"search_term_{name}"):
        row.operator("hg3d.clear_searchbox", text="", icon="X").searchbox_name = name
