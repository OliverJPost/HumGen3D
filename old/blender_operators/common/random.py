"""
Randomize operator for sliders and pcolls
"""

import random
from typing import Any

import bpy

from ...blender_backend.preview_collections import refresh_pcoll
from ..creation_phase.material import (
    randomize_iris_color,
    randomize_skin_shader,
)
from .common_functions import find_human


class HG_COLOR_RANDOM(bpy.types.Operator):
    """
    Sets the color slot to a random color from the color dicts from HG_COLORS

    Operator type:
        Material

    Prereq:
        Passed arguments
        Active material of active object is a HumGen clothing material

    Args:
        input_name (str): Name of HG_Control node input to randomize the color for
        color_group (str):  Name of the color groups stored in HG_COLOR to pick
            colors from
    """

    bl_idname = "hg3d.color_random"
    bl_label = "Random Color"
    bl_description = "Randomize this property"
    bl_options = {"UNDO", "INTERNAL"}

    input_name: bpy.props.StringProperty()
    color_group: bpy.props.StringProperty()

    def execute(self, context):
        from ...data.colors import (
            color_dict,
        )  # TODO make color dict into json?

        color_hex = random.choice(color_dict[self.color_group])
        color_rgba = self._hex_to_rgba(color_hex)

        nodes = context.object.active_material.node_tree.nodes
        input = nodes["HG_Control"].inputs[self.input_name]

        input.default_value = tuple(color_rgba)

        return {"FINISHED"}

    def _hex_to_rgba(self, color_hex) -> "tuple[float, float, float, 1]":
        """Build rgb color from this hex code

        Args:
            color_hex (str): Hexadecimal color code, withhout # in front

        Returns:
            tuple[float, float, float, 1]: rgba color
        """
        color_rgb = [int(color_hex[i : i + 2], 16) for i in (0, 2, 4)]
        float_color_rgb = [x / 255.0 for x in color_rgb]
        float_color_rgb.append(1)

        return float_color_rgb


def set_random_active_in_pcoll(context, sett, pcoll_name, searchterm=None):
    """Sets a random object in this preview colleciton as active

    Args:
        sett (PropertyGRoup): HumGen props
        pcoll_name (str): internal name of preview collection to pick random for
        searchterm (str): filter to only look for items in the pcoll that include this string
    """

    refresh_pcoll(None, context, pcoll_name)

    current_item = sett["pcoll_{}".format(pcoll_name)]

    pcoll_list = sett["previews_list_{}".format(pcoll_name)]
    random_item = get_random_from_list(pcoll_list, current_item, searchterm)

    if not random_item:
        setattr(sett, f"{pcoll_name}_sub", "All")
        refresh_pcoll(None, context, pcoll_name)
        pcoll_list = sett["previews_list_{}".format(pcoll_name)]
        random_item = get_random_from_list(
            pcoll_list, current_item, searchterm
        )

    setattr(sett, f"pcoll_{pcoll_name}", random_item)


def get_random_from_list(list, current_item, searchterm) -> Any:
    """Gets a random item from passed list, trying max 6 times to prevent choosing
    the currently active item

    Args:
        list (list): list to choose item from
        current_item (AnyType): currently active item
        searchterm (str): filter to only look for items in the pcoll that include this string

    Returns:
        Any: randomly chosen item
    """

    corrected_list = (
        [item for item in list if searchterm in item.lower()]
        if searchterm
        else list
    )
    if not corrected_list:
        print("ERROR: Searchterm not found in pcoll: ", searchterm)
        corrected_list = list

    try:
        random_item = random.choice(corrected_list)
    except IndexError:
        return None

    i = 0
    while random_item == current_item and i < 5:
        random_item = random.choice(corrected_list)
        i += 1

    return random_item
