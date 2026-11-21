# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""
Operators and functions used for managing HumGen's content packs.

Packs are installed by the setup (`backend/setup`, `user_interface/setup_overlay`):
the trial is downloaded, every other pack comes from an `.hgpack` file.

Nomenclature:
cpack = Abbreviation of content pack. Represents a collection of items
    downloaded together and extracted in the HumGen file strucure, forming
    content to be used in the add-on. Settings and properties stored in a
    .json file
"""

import json
import os
from typing import Any, no_type_check

import bpy
from ...backend import get_prefs, hg_log
from ...user_interface.icons.icons import get_hg_icon

from ..setup import downloader
from ..updates.update import check_update

CPACK_FOLDER = "content_packs"

ICON_DICT = {
    "humans": "humans",
    "human_textures": "textures",
    "shapekeys": "body",
    "hair": "hair",
    "poses": "pose",
    "clothes": "clothing",
    "footwear": "footwear",
    "expression": "expression",
}


class HG_UL_CONTENTPACKS(bpy.types.UIList):
    """UIList showing content packs.

    Including icons on who made the pack, what version it is, what items are included,
    a weblink and a delete button
    """

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

        header = item.name == "header"
        # header is true only for the first item in the list.
        # This fakes a header for the items in the ui_list

        row = layout.row(align=True)
        row.label(text="Name:" if header else item.pack_name)

        subrow = row
        self._draw_creator_column(item, header, subrow)

        subrow.label(text="Version:" if header else "%s.%s" % tuple(item.pack_version))
        subrow.alignment = "LEFT"

        self._draw_update_label(item, subrow, header)
        self._draw_category_dots(item, header, subrow)

        subrow.separator()

        self._draw_operator_buttons(item, header, subrow)

    @no_type_check
    def _draw_operator_buttons(self, item, header, subrow):
        """Draws buttons to go to edit cpack, to cpack weblink and to delete cpack."""
        if header:
            for _ in range(3):
                subrow.label(text="", icon="BLANK1")
            return

        # weblink button
        subrow.operator("wm.url_open", text="", icon="URL").url = item.weblink
        # delete button
        subrow.operator("hg3d.cpackdel", text="", icon="TRASH").item_name = item.name

        # Edit pack button
        if item.creator != "HumGen" or get_prefs().dev_tools:
            subrow.operator(
                "hg3d.edit_cpack", text="", icon="GREASEPENCIL", emboss=False
            ).item_name = item.name
        else:
            subrow.label(text="", icon="BLANK1")

    @no_type_check
    def _draw_category_dots(self, item, header, subrow):
        """Draws grid of dots to show what kind of content is in this cpack."""
        for categ, icon in ICON_DICT.items():
            if header:
                subrow.label(text="", icon_value=get_hg_icon(icon))
            else:
                if categ not in item:
                    subrow.label(text="", icon="LAYER_USED")
                    continue

                subrow.label(
                    text="",
                    icon="LAYER_ACTIVE" if item[categ] else "LAYER_USED",
                )

    @no_type_check
    def _draw_creator_column(self, item, header, subrow):
        """Draws a column with info about the creator of this cpack."""
        if header:
            subrow.label(text="Creator:")
        elif item.creator == "HumGen":
            subrow.label(text=item.creator, icon_value=get_hg_icon("HG_icon"))
        else:
            subrow.label(text=item.creator, icon=item.icon_name)

    @no_type_check
    def _draw_update_label(self, item, subrow, header):
        """Draws a column with info if the cpack is up to date."""
        if header:
            subrow.label(text="Update info:    ")
            return

        pack_version = tuple(item.pack_version)
        req_version = tuple(item.required_version)
        latest_version = tuple(item.latest_version)

        upd = (
            "uptodate"
            if pack_version >= req_version and pack_version >= latest_version
            else "required"
            if pack_version < req_version
            else "available"
        )

        subrow.alert = upd == "required"
        # format version number to string
        vnum = "%s.%s" % tuple(
            item.latest_version if upd == "available" else item.required_version
        )

        subrow.label(
            text=(
                "Up to date     "
                if upd == "uptodate"
                else f"{vnum} available"
                if upd == "available"
                else f"{vnum} required! "
            ),
            icon=(
                "CHECKMARK"
                if upd == "uptodate"
                else "INFO"
                if upd == "available"
                else "ERROR"
            ),
        )
        subrow.alert = False


class HG_CONTENT_PACK(bpy.types.PropertyGroup):
    """Properties of the content pack."""

    pack_name: bpy.props.StringProperty(
        name="Content Pack Name",
        description="",
        default="",
    )

    creator: bpy.props.StringProperty()
    pack_version: bpy.props.IntVectorProperty(default=(0, 0), size=2)
    weblink: bpy.props.StringProperty()
    icon_name: bpy.props.StringProperty(default="COMMUNITY")  # noqa F821

    # booleans for showing in the UI what capassalse)
    human_textures: bpy.props.BoolProperty(default=False)
    shapekeys: bpy.props.BoolProperty(default=False)
    hair: bpy.props.BoolProperty(default=False)
    poses: bpy.props.BoolProperty(default=False)
    clothes: bpy.props.BoolProperty(default=False)
    footwear: bpy.props.BoolProperty(default=False)
    expressions: bpy.props.BoolProperty(default=False)

    json_path: bpy.props.StringProperty()
    required_version: bpy.props.IntVectorProperty(default=(0, 0), size=2)
    latest_version: bpy.props.IntVectorProperty(default=(0, 0), size=2)


class HG_REFRESH_CPACKS(bpy.types.Operator):
    """Operator for the refresh cpacks button.

    Refresh function is outside class because it is called as an update for certain
    props
    """

    bl_idname = "hg3d.cpacksrefresh"
    bl_label = "Refresh"
    bl_description = "Refresh the content pack list"

    @no_type_check
    def execute(self, context):
        cpacks_refresh(self, context)
        return {"FINISHED"}


def cpack_folder(content_folder: str, path_module: Any = os.path) -> str:
    """`<content folder>/content_packs`, "" when no content folder is set.

    Joined, not concatenated, so a UNC path (\\\\nas\\share) keeps its two
    backslashes and an empty folder never becomes "/content_packs".
    `path_module` is for tests of Windows paths (ntpath).
    """
    if not content_folder:
        return ""
    return path_module.join(content_folder, CPACK_FOLDER)


def cpack_json_files(content_folder: str) -> "list[str]":
    """Paths of the pack JSONs in the content folder. Creates nothing: an
    unplugged drive or a missing folder simply has no packs."""
    json_folder = cpack_folder(content_folder)
    if not json_folder:
        return []
    try:
        names = sorted(os.listdir(json_folder))
    except OSError:
        return []
    return [os.path.join(json_folder, fn) for fn in names if os.path.splitext(fn)[1] == ".json"]


# TODO slow switch between preferences tabs
def cpacks_refresh(self: Any, context: bpy.types.Context) -> None:
    """Refreshes the content pack ui list.

    Does this by scanning the content_packs folder in the file structure
    """
    coll = context.scene.contentpacks_col  # type:ignore[attr-defined]
    pref = get_prefs()

    coll.clear()

    # add the fake header as an item to the collection,
    header = coll.add()
    header.name = "header"

    for json_path in cpack_json_files(str(pref.filepath)):
        count = len(coll)
        try:
            _add_cpack_to_coll(coll, json_path)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            hg_log("Skipping unreadable content pack", json_path, repr(e), level="WARNING")
            # One broken pack never hides the others, nor shows as an empty row
            while len(coll) > count:
                coll.remove(len(coll) - 1)

    check_update()


def _add_cpack_to_coll(coll: bpy.types.CollectionProperty, filepath: str) -> None:
    """Adds this cpack to the content pack collection.

    Args:
        coll (CollectionProperty): cpack collection
        filepath (str): path of the json file of this cpack
    """
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    config = data["config"]
    item = coll.add()  # type:ignore[attr-defined]

    item.name = config["pack_name"]

    prop_names = (
        "pack_name",
        "creator",
        "weblink",
        "description",
        "icon_name",
    )
    for prop_name in prop_names:
        item[prop_name] = config[prop_name] if prop_name in config else None

    pack_version = config["pack_version"]
    item["pack_version"] = pack_version

    item.json_path = filepath

    if "categs" not in data:
        return

    categs = data["categs"]
    for categ_name, includes_items_from_categ in categs.items():
        item[categ_name] = includes_items_from_categ  # bool


class HG_DELETE_CPACK(bpy.types.Operator):
    """Deletes the cpack from the content pack collection.

    Removes the files listed in the .json of the cpack, except those another
    installed pack lists too (see `downloader.remove`)
    """

    bl_idname = "hg3d.cpackdel"
    bl_label = "Delete content pack"
    bl_description = "Delete this content pack"

    item_name: bpy.props.StringProperty()

    @no_type_check
    def invoke(self, context, event):
        # confirmation checkbox
        return context.window_manager.invoke_confirm(self, event)

    @no_type_check
    def execute(self, context):
        pref = get_prefs()
        col = context.scene.contentpacks_col
        item = col[self.item_name]

        key = os.path.splitext(os.path.basename(item.json_path))[0]
        if not downloader.remove(pref.filepath, key):
            self.report({"WARNING"}, f"Could not remove {item.pack_name}")

        cpacks_refresh(self, context)
        context.scene.contentpacks_col_index = min(context.scene.contentpacks_col_index, len(col) - 1)

        return {"FINISHED"}
