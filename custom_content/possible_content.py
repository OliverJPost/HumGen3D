import bpy
from bpy.props import BoolProperty, EnumProperty, PointerProperty, StringProperty
from bpy.types import Object
from HumGen3D.human.human import Human
from HumGen3D.user_interface.icons.icons import get_hg_icon


class HG_UL_POSSIBLE_CONTENT(bpy.types.UIList):
    """
    UIList showing modifiers
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
        self.use_filter_show = False

        if item.is_header:
            layout.label(text=item.name)
            return

        split_50 = layout.split(factor=0.5)
        name_row = split_50.row()
        try:
            name_row.label(text=item.name, icon_value=get_hg_icon(item.category))
        except KeyError:
            name_row.label(text=item.name, icon="SHAPEKEY_DATA")

        right_row = split_50.row(align=True)
        right_row.operator(
            "hg3d.save_sk_to_library", text="", icon="ZOOM_SELECTED", depress=True
        )
        right_alert_row = right_row.row(align=True)
        right_alert_row.alert = True
        operator = right_alert_row.operator(
            "hg3d.start_saving", text="Save", icon="FILE_TICK", depress=True
        )
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
            ("clothing", "Clothing", "", 1),
            ("hair", "Hairstyle", "", 2),
            ("pose", "Pose", "", 3),
            ("human", "Human", "", 3),
        ]
    )


def find_possible_content(context):
    coll = context.scene.possible_content_col
    human = Human.from_existing(context.object)
    coll.clear()

    header = coll.add()
    header.name = "Main categories:"
    header.is_header = True

    item = coll.add()
    item.name = "Human"
    item.category = "human"

    item = coll.add()
    item.name = "Outfit"
    item.category = "clothing"
    item = coll.add()
    item.name = "Footwear"
    item.category = "clothing"

    item = coll.add()
    item.name = "Hairstyle"
    item.category = "hair"

    item = coll.add()
    item.name = "Pose"
    item.category = "pose"

    header = coll.add()
    header.name = " "
    header.is_header = True

    header = coll.add()
    header.name = "Shape keys:"
    header.is_header = True

    for key in human.keys.all_shapekeys:
        # if hash(key) != key.stored_hash:
        item = coll.add()
        item.name = key.as_bpy().name
        item.category = "key"
