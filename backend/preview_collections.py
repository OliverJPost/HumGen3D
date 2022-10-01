# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""
Functions related to the preview_collections of human generator, including
population of them
"""

from __future__ import annotations

import os
from pathlib import Path
from re import L
from typing import Dict

import bpy
from HumGen3D.backend.preferences.preference_func import get_addon_root

from ..human.base.exceptions import HumGenException  # type: ignore
from . import get_prefs, hg_log

# from HumGen3D.human.human import Human

preview_collections: Dict[PreviewCollection] = {}  # global dict of all pcolls
# (extension, gender_dependent, folder, category_propname, search_term_propname)
PREVIEW_COLLECTION_DATA = {
    "humans": (".json", True, "models", None, None),
    "pose": (".blend", False, "poses", "pose_category", "search_term_pose"),
    "outfit": (".blend", True, "outfits", "outfit_category", "search_term_outfit"),
    "footwear": (
        ".blend",
        True,
        "footwear",
        "footwear_category",
        "search_term_footwear",
    ),
    "hair": (".json", True, ["hair", "head"], "hair_category", None),
    "face_hair": (".json", False, ["hair", "face_hair"], "face_hair_category", None),
    "expression": (
        ".npy",
        False,
        "expressions",
        "expression_category",
        "search_term_expression",
    ),
    "pattern": (
        ".png",
        False,
        "patterns",
        "pattern_category",
        "search_term_pattern",
    ),
    "texture": ((".png", ".tiff", ".tga"), True, "textures", "texture_library", None),
}


def _check_for_HumGen_filepath_issues():
    pref = get_prefs()
    if not pref.filepath:
        raise HumGenException("No filepath selected in HumGen preferences.")
    base_humans_path = os.path.join(pref.filepath, "content_packs", "Base_Humans.json")

    base_content = os.path.exists(base_humans_path)

    if not base_content:
        raise HumGenException("Filepath selected, but no humans found in path")


class PreviewCollection:
    def __init__(self, name, pcoll):
        self.name = name
        self.pcoll = pcoll
        (
            self.extension,
            self.gender_split,
            self.subfolder,
            self.category_prop,
            self.search_term_prop,
        ) = PREVIEW_COLLECTION_DATA[self.name]

        if isinstance(self.subfolder, list):
            self.subfolder = os.path.join(*self.subfolder)

    def refresh(self, context, gender=None):
        """Refresh the items of this preview

        Args:
            pcoll_name (str): name of the preview collection to refresh
        """
        sett = context.scene.HG3D
        _check_for_HumGen_filepath_issues()

        subcategory = (
            getattr(sett.pcoll, self.category_prop) if self.category_prop else None
        )
        if subcategory == "All":
            subcategory = None

        self.populate(context, gender, subcategory=subcategory, use_search_term=True)
        sett.pcoll[self.name] = "none"  # set the preview collection to
        # the 'click here to select' item

    def populate(self, context, gender, subcategory=None, use_search_term=True):
        """Populates the preview collection enum list with blend file filepaths and
        icons

        Args:
            pcoll_categ (str): name of preview collection
        """
        sett = context.scene.HG3D
        sett.load_exception = False if self.name == "pose" else True
        pref = get_prefs()

        # clear previews list
        sett["previews_list_{}".format(self.name)] = []
        self.previews_list = sett["previews_list_{}".format(self.name)]

        # find category and subcategory in order to determine the dir to search

        gender = gender if gender and self.gender_split else ""
        subcategory = subcategory if subcategory else ""
        pcoll_full_dir = os.path.join(
            pref.filepath, self.subfolder, gender, subcategory
        )

        if use_search_term and self.search_term_prop:
            search_term = getattr(sett.pcoll, self.search_term_prop)
        else:
            search_term = ""

        all_files = list_files_in_dir(pcoll_full_dir, search_term, self.extension)
        path_list = []
        if not all_files:
            empty_thumb = self.add_info_thumbnail("pcoll_empty")
            pcoll_enum = [("none", "", "", empty_thumb.icon_id, 0)]
        else:
            none_thumb = self.add_info_thumbnail("pcoll_placeholder")
            pcoll_enum = [("none", "", "", none_thumb.icon_id, 0)]
            for i, full_path in enumerate(all_files):
                short_path = os.path.relpath(full_path, pref.filepath)

                pcoll_enum.append(
                    (
                        short_path,
                        get_display_name(full_path),
                        "",
                        self.get_thumbnail_for_item(full_path).icon_id,
                        i + 1,
                    )
                )
                path_list.append(short_path)

        self.pcoll[self.name] = pcoll_enum
        sett[f"previews_list_{self.name}"] = path_list

        sett.load_exception = False

    def get_thumbnail_for_item(self, full_path):
        filepath_thumb = os.path.splitext(full_path)[0] + ".jpg"
        if not self.pcoll.get(filepath_thumb):
            thumb = self.pcoll.load(filepath_thumb, filepath_thumb, "IMAGE")
        else:
            thumb = self.pcoll[filepath_thumb]
        return thumb

    def add_info_thumbnail(self, thumb_name) -> list:
        """Loads a thumbnail for this pcoll item

        Args:
            thumb_name (str): name of the thumbnail image, excluding extension
            pcoll (list): preview collection

        Returns:
            list: icon in enumarator
        """

        filepath_thumb = os.path.join(
            get_addon_root(), "user_interface", "icons", f"{thumb_name}.jpg"
        )
        if not self.pcoll.get(filepath_thumb):
            thumb = self.pcoll.load(filepath_thumb, filepath_thumb, "IMAGE")
        else:
            thumb = self.pcoll[filepath_thumb]

        return thumb


def list_files_in_dir(dir, search_term, ext, skip_pbr_folder=False) -> list:
    """Gets a list of files in dir with certain extension. Extension depends on
    the passed pcoll_type. Also handles search terms the users entered in a
    searchbox

    Args:
        dir (dir): Directory to search in
        pcoll_type (str): name of preview collection to search items for

    Returns:
        list: list of file paths in dir of certain extension
    """

    file_paths = []
    for root, _, files in os.walk(dir):
        if skip_pbr_folder and "PBR" in root:
            continue  # don't show textures in PBR folder of texture sets
        for fn in files:
            if not fn.lower().endswith(ext):
                continue
            if not search_term.lower() in fn.lower():
                continue

            full_path = os.path.join(root, fn)
            file_paths.append(full_path)

    hg_log(f"getting files in {dir}", level="DEBUG")
    hg_log(f"found files {file_paths}", level="DEBUG")

    return file_paths


def get_display_name(full_path) -> str:
    """Transforms internal name to displayable name

    Args:
        full_path (Path): full path of item to make display name for

    Returns:
        str: display name
    """
    display_name = os.path.basename(full_path)
    for remove_string in ("HG", "Male", "Female"):
        display_name = display_name.replace(remove_string, "")
    display_name = display_name.replace("_", " ")

    return display_name
