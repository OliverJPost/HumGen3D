# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""This file is currently inactive."""

import os

import bpy
from HumGen3D.backend import preview_collections  # type: ignore
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.backend.preview_collections import PREVIEW_COLLECTION_DATA
from HumGen3D.common.type_aliases import GenderStr
from HumGen3D.user_interface.icons.icons import get_hg_icon


class HG_UL_BATCH_CLOTHING(bpy.types.UIList):
    """UIList showing clothing libraries."""

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        uilist_layout(layout, context, item)


class HG_UL_BATCH_EXPRESSIONS(bpy.types.UIList):
    """UIList showing clothing libraries."""

    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        uilist_layout(layout, context, item)


def uilist_layout(layout, context, item):
    enabledicon = "CHECKBOX_HLT" if item.enabled else "CHECKBOX_DEHLT"

    row = layout.row(align=True)
    row.prop(item, "enabled", text="", icon=enabledicon, emboss=False)

    row.label(text=item.library_name)

    subrow = row.row(align=True)
    try:
        subrow.scale_x = 0.7
        subrow.label(
            text=str(item.male_items),
            icon_value=(
                get_hg_icon("male_true")
                if item.male_items != 0
                else get_hg_icon("male_false")
            ),
        )

        subrow.label(
            text=str(item.female_items),
            icon_value=(
                get_hg_icon("female_true")
                if item.female_items != 0
                else get_hg_icon("female_false")
            ),
        )
    except AttributeError:
        # If the item doesn't have (fe)male_items attribute. Bad design
        subrow.alignment = "RIGHT"
        subrow.label(text=str(item.count))


class BATCH_CLOTHING_ITEM(bpy.types.PropertyGroup):
    """Properties of the items in the uilist."""

    library_name: bpy.props.StringProperty(
        name="Library Name",
        description="",
        default="",
    )
    enabled: bpy.props.BoolProperty(default=True)
    male_items: bpy.props.IntProperty(default=0)
    female_items: bpy.props.IntProperty(default=0)


class BATCH_EXPRESSION_ITEM(bpy.types.PropertyGroup):
    """Properties of the items in the uilist."""

    library_name: bpy.props.StringProperty(
        name="Library Name",
        description="",
        default="",
    )
    enabled: bpy.props.BoolProperty(default=True)
    count: bpy.props.IntProperty(default=0)


def find_item_amount(gender: GenderStr, folder: str) -> int:
    ext = ".blend"
    pcoll_folder = PREVIEW_COLLECTION_DATA["outfit"][2]
    directory = os.path.join(get_prefs().filepath, pcoll_folder, gender, folder)
    if not os.path.isdir(directory):
        return 0
    return len([name for name in os.listdir(directory) if name.endswith(ext)])


def batch_clothing_uilist_refresh(self, context):
    """Refreshes uilist."""
    scene = context.scene
    collection = scene.batch_clothing_col

    enabled_dict = {i.name: i.enabled for i in collection}
    collection.clear()

    found_folders_male = preview_collections["outfit"].find_folders(
        "male", include_all=False
    )
    found_folders_female = preview_collections["outfit"].find_folders(
        "female", include_all=False
    )

    for folder_name, *_ in set(found_folders_male + found_folders_female):
        item = collection.add()
        item.name = folder_name
        item.library_name = folder_name
        if folder_name in list(enabled_dict):
            item.enabled = enabled_dict[folder_name]
        item.male_items = find_item_amount("male", folder_name)
        item.female_items = find_item_amount("female", folder_name)


class HG_REFRESH_UILISTS(bpy.types.Operator):
    """Clears searchfield."""

    bl_idname = "hg3d.refresh_batch_uilists"
    bl_label = "Refresh"
    bl_description = "Refresh the library list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        batch_clothing_uilist_refresh(self, context)
        return {"FINISHED"}
