# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""
This file is currently inactive
"""

import bpy
from HumGen3D.batch_generator.batch_functions import find_folders, find_item_amount
from HumGen3D.user_interface.icons.icons import get_hg_icon  # type: ignore


class HG_UL_BATCH_CLOTHING(bpy.types.UIList):
    """
    UIList showing clothing libraries
    """

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
    """
    UIList showing clothing libraries
    """

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

    # islockedicon = "LOCKED" if item.islocked else "BLANK1"

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
    """Properties of the items in the uilist"""

    library_name: bpy.props.StringProperty(
        name="Library Name",
        description="",
        default="",
    )
    enabled: bpy.props.BoolProperty(default=True)
    male_items: bpy.props.IntProperty(default=0)
    female_items: bpy.props.IntProperty(default=0)


class BATCH_EXPRESSION_ITEM(bpy.types.PropertyGroup):
    """Properties of the items in the uilist"""

    library_name: bpy.props.StringProperty(
        name="Library Name",
        description="",
        default="",
    )
    enabled: bpy.props.BoolProperty(default=True)
    count: bpy.props.IntProperty(default=0)


def batch_uilist_refresh(self, context, categ):
    """
    Refreshes uilist
    """
    scene = context.scene
    if categ == "outfit":
        collection = scene.batch_clothing_col
    elif categ == "pose":
        collection = scene.batch_pose_col
    else:
        collection = scene.batch_expressions_col

    enabled_dict = {i.name: i.enabled for i in collection}
    collection.clear()

    gender = categ == "outfit"
    found_folders_male = find_folders(
        self, context, categ, gender, include_all=False, gender_override="male"
    )

    for folder in found_folders_male:
        item = collection.add()
        item.name = folder[0]
        item.library_name = folder[0]
        if folder[0] in [n for n in enabled_dict]:
            item.enabled = enabled_dict[folder[0]]
        if gender:
            item.male_items = find_item_amount(context, categ, "male", folder[0])
        else:
            item.count = find_item_amount(context, categ, False, folder[0])

    if not gender:
        return

    found_folders_female = find_folders(
        self,
        context,
        categ,
        gender,
        include_all=False,
        gender_override="female",
    )

    for folder in found_folders_female:
        if folder[0] in [item.library_name for item in collection]:
            item = collection[folder[0]]
        else:
            item = collection.add()
            item.name = folder[0]
            item.library_name = folder[0]
        item.female_items = find_item_amount(context, categ, "female", folder[0])


class HG_REFRESH_UILISTS(bpy.types.Operator):
    """
    clears searchfield
    """

    bl_idname = "hg3d.refresh_batch_uilists"
    bl_label = "Refresh"
    bl_description = "Refresh the library list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        batch_uilist_refresh(self, context, "outfits")
        batch_uilist_refresh(self, context, "expressions")

        return {"FINISHED"}
