# type:ignore
from typing import no_type_check

import bpy
from bpy.props import (  # type:ignore
    BoolProperty,
    EnumProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import Object  # type:ignore
from HumGen3D.human.human import Human
from HumGen3D.user_interface.icons.icons import get_hg_icon


class HG_UL_POSSIBLE_CONTENT(bpy.types.UIList):
    """UIList showing modifiers."""

    @no_type_check
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
        self.use_filter_show = False

        if item.is_header:
            if item.name == "No changes found!":
                layout.enabled = False
            layout.label(text=item.name)
            return

        split_50 = layout.split(factor=0.6)
        name_row = split_50.row()
        try:
            name_row.label(text=item.name, icon_value=get_hg_icon(item.category))
        except KeyError:
            name_row.label(text=item.name, icon="SHAPEKEY_DATA")

        right_row = split_50.row(align=True)
        right_row.alert = True
        operator = right_row.operator("hg3d.start_saving", text="Save", depress=True)
        operator.category = item.category
        if item.category == "key":
            operator.key_name = item.name


class POSSIBLE_CONTENT_ITEM(bpy.types.PropertyGroup):
    name: StringProperty()
    is_header: BoolProperty(default=False)
    obj: PointerProperty(type=Object)
    category: EnumProperty(
        items=[
            ("key", "Key", "", 0),
            ("outfit", "Outfit", "", 1),
            ("footwear", "Footwear", "", 2),
            ("hair", "Hairstyle", "", 3),
            ("pose", "Pose", "", 4),
            ("starting_human", "Human", "", 5),
        ]
    )


def find_possible_content(context: bpy.types.Context) -> None:
    coll = context.scene.possible_content_col
    human = Human.from_existing(context.object)
    coll.clear()

    show_unchanged = context.scene.HG3D.custom_content.show_unchanged

    header = coll.add()
    header.name = "Main categories:"
    header.is_header = True

    item = coll.add()
    item.name = "Human"
    item.category = "starting_human"

    hashes = human.props.hashes
    if str(hash(human.hair.regular_hair)) != hashes.get("$hair") or show_unchanged:
        item = coll.add()
        item.name = "Hairstyle"
        item.category = "hair"

    if str(hash(human.clothing.outfit)) != hashes.get("$outfit") or show_unchanged:
        item = coll.add()
        item.name = "Outfit"
        item.category = "outfit"

    if str(hash(human.clothing.footwear)) != hashes.get("$footwear") or show_unchanged:
        item = coll.add()
        item.name = "Footwear"
        item.category = "footwear"

    if str(hash(human.pose)) != hashes.get("$pose") or show_unchanged:
        item = coll.add()
        item.name = "Pose"
        item.category = "pose"

    if len(coll) == 1:
        header = coll.add()
        header.name = "No changes found!"
        header.is_header = True

    header = coll.add()
    header.name = " "
    header.is_header = True

    header = coll.add()
    header.name = "Shape keys:"
    header.is_header = True

    for key in human.keys.all_added_shapekeys:
        # if hash(key) != key.stored_hash:
        item = coll.add()
        item.name = key.as_bpy().name
        item.category = "key"
