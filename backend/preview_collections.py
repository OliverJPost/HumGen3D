# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Contains PreviewCollection class for managing content preview collections."""

from __future__ import annotations

import os
from typing import Dict, Optional, Union

import bpy
from HumGen3D.backend.preferences.preference_func import get_addon_root
from HumGen3D.common.type_aliases import BpyEnum, GenderStr

from ..common.exceptions import HumGenException  # type: ignore
from . import get_prefs, hg_log

preview_collections: Dict[str, PreviewCollection] = {}  # global dict of all pcolls

# fmt: off
# (extension, gender_dependent, folder, category_propname, search_term_propname, custom_icon) # noqa
PcollDict = dict[str, tuple[Union[tuple[str, ...], str], bool, Union[list[str], str], Optional[str], Optional[str], Optional[str]]] #FIXME # noqa
PREVIEW_COLLECTION_DATA: PcollDict = {
    "humans": (".json", True, "models", "humans_category", None, None),
    "pose": (".blend", False, "poses", "pose_category", "search_term_pose", None),
    "outfit": (".blend", True, "outfits", "outfit_category", "search_term_outfit", None), # noqa
    "footwear": (".blend", True, "footwear", "footwear_category", "search_term_footwear", None), # noqa
    "hair": (".json", True, ["hair", "head"], "hair_category", None, None),
    "face_hair": (".json", False, ["hair", "face_hair"], "face_hair_category", None, None), # noqa
    "expression": (".npz", False, ["shapekeys", "expressions"], "expression_category", "search_term_expression", None), # noqa
    "pattern": (".png", False, "patterns", "pattern_category", "search_term_pattern", None), # noqa
    "texture": ((".png", ".tiff", ".tga"), True, "textures", "texture_category", None, None), # noqa
    "scripts": (".py", False, "scripts", None, None, "script.png"),
    "process_templates": (".json", False, "process_templates", None, None, "template.png"), # noqa
    "shapekeys": (".npz", False, "shapekeys", None, None, "shapekey.png"),
    "livekeys": (".npz", False, "livekeys", None, None, "livekey.png"),
}
# fmt: on


def _check_for_HumGen_filepath_issues() -> None:
    """Checks if HG filepath is set and if base content is installed.

    Raises:
        HumGenException: Raised when no filepath or no base content in the filepath
    """
    pref = get_prefs()
    if not pref.filepath:
        raise HumGenException("No filepath selected in HumGen preferences.")
    base_humans_path = os.path.join(pref.filepath, "content_packs", "Base_Humans.json")

    base_content = os.path.exists(base_humans_path)

    trial_content_path = os.path.join(pref.filepath, "content_packs", "Trial_Content.json")
    trial_content = os.path.exists(trial_content_path)

    if not base_content and not trial_content:
        raise HumGenException("Filepath selected, but no humans found in path")


class PreviewCollection:
    """Representation of a preview collection, for showing content users can pick."""

    def __init__(self, name: str, pcoll: bpy.utils.previews.ImagePreviewCollection):
        """Create a new pcoll instance.

        Args:
            name (str): Name of preview collection
            pcoll (bpy.utils.previews.ImagePreviewCollection): Bpy preview collection
        """
        self.name = name
        self.pcoll = pcoll
        (
            self.extension,
            self.gender_split,
            self.subfolder,
            self.category_prop,
            self.search_term_prop,
            self.custom_icon,
        ) = PREVIEW_COLLECTION_DATA[self.name]

        if isinstance(self.subfolder, list):
            self.subfolder = os.path.join(*self.subfolder)

    def refresh(self, context: bpy.types.Context, gender: Optional[str] = None) -> None:
        """Refresh the items of this preview.

        Args:
            context: bpy context
            gender: Gender to find options for ("male", "female")
        """
        sett = context.scene.HG3D  # type:ignore[attr-defined]
        _check_for_HumGen_filepath_issues()

        subcategory = (
            getattr(sett.pcoll, self.category_prop) if self.category_prop else None
        )
        if subcategory == "All":
            subcategory = None

        self.populate(context, gender, subcategory=subcategory, use_search_term=True)
        if bpy.app.version >= (4,2,0):
            sett.pcoll[self.name] = 0
        else:
            sett.pcoll[self.name] = "none"  # set the preview collection to
                                            # the 'click here to select' item

    def populate(
        self,
        context: bpy.types.Context,
        gender: Optional[GenderStr],
        subcategory: Optional[str] = None,
        use_search_term: bool = True,
    ) -> None:
        """Populates the pcoll enum list with blend file filepaths and icons.

        Args:
            context: bpy context
            gender: Gender to populate the pcoll for ("male", "female")
            subcategory: Only find files inside this subcategory
            use_search_term: Filter only files that match user defined search_term
        """
        sett = context.scene.HG3D  # type:ignore[attr-defined]
        sett.load_exception = self.name != "pose"
        pref = get_prefs()

        # clear previews list
        sett["previews_list_{}".format(self.name)] = []
        self.previews_list = sett["previews_list_{}".format(self.name)]

        # find category and subcategory in order to determine the dir to search

        gender = gender if gender and self.gender_split else ""
        if not subcategory or subcategory == "All":
            subcategory = ""

        pcoll_full_dir = os.path.join(
            pref.filepath, self.subfolder, gender, subcategory  # type:ignore[arg-type]
        )

        if use_search_term and self.search_term_prop:
            search_term = getattr(sett.pcoll, self.search_term_prop)
        else:
            search_term = ""

        all_files = list_files_in_dir(pcoll_full_dir, search_term, self.extension)
        path_list = []
        if not all_files:
            empty_thumb = self._add_info_thumbnail("pcoll_empty")
            pcoll_enum = [("none", "", "", empty_thumb.icon_id, 0)]
        else:
            none_thumb = self._add_info_thumbnail("pcoll_placeholder")
            pcoll_enum = [("none", "", "", none_thumb.icon_id, 0)]
            for i, full_path in enumerate(all_files):
                # Skip expression shapekeys to prevent double items
                if self.name == "shapekeys" and "expressions" in full_path:
                    continue
                short_path = os.path.relpath(full_path, pref.filepath)

                pcoll_enum.append(
                    (
                        short_path,
                        get_display_name(full_path),
                        "",
                        self._get_thumbnail_for_item(full_path).icon_id,
                        i + 1,
                    )
                )
                path_list.append(short_path)

        # sort .trial items last
        pcoll_enum.sort(
            key=lambda pcoll_enum_item: pcoll_enum_item[0]
            .lower()
            .endswith(".trial")
        )

        self.pcoll[self.name] = pcoll_enum  # type:ignore[index]
        sett[f"previews_list_{self.name}"] = path_list

        sett.load_exception = False

    def find_folders(self, gender: GenderStr, include_all: bool = True) -> BpyEnum:
        """Gets enum of folders found in a specific directory.

        These serve as categories for that specific pcoll

        Args:
            gender (GenderStr): Gender to find folders for ("male", "female")
            include_all (bool): include "All" as first item. Defaults to True.

        Returns:
            BpyEnum: Enum of folders in format (folder_name, folder_name, "", idx)
        """
        pref = get_prefs()

        folder = PREVIEW_COLLECTION_DATA[self.name][2]
        if isinstance(folder, list):
            folder = os.path.join(*folder)

        separate_folders_for_genders = PREVIEW_COLLECTION_DATA[self.name][1]
        if separate_folders_for_genders:
            categ_folder = os.path.join(pref.filepath, folder, gender)
        else:
            categ_folder = os.path.join(pref.filepath, folder)

        if not os.path.isdir(categ_folder):
            hg_log(
                f"Can't find folder {categ_folder} for preview collection {self.name}",
                level="DEBUG",
            )
            return [("NOT INSTALLED", "NOT INSTALLED", "", i) for i in range(99)]

        dirlist = os.listdir(categ_folder)
        dirlist.sort()
        categ_list = []
        ext = (".jpg", "png", ".jpeg", ".blend")
        # FIXME
        for item in dirlist:
            if (
                not item.endswith(ext)
                and ".DS_Store" not in item
                and not item.startswith(".")
            ):  # noqa
                categ_list.append(item)

        if not categ_list:
            categ_list.append("No Category Found")

        enum_list = [("All", "All Categories", "", 0)] if include_all else []
        for i, name in enumerate(categ_list):
            idx = i if self.name == "texture" else i + 1
            enum_list.append((name, name, "", idx))

        if not enum_list:
            return [("ERROR", "ERROR", "", i) for i in range(99)]
        else:
            return enum_list

    def _get_thumbnail_for_item(self, full_path: str) -> bpy.types.ImagePreview:
        if self.custom_icon:
            filepath_thumb = os.path.join(
                get_addon_root(), "user_interface", "icons", self.custom_icon
            )
        if full_path.endswith(".trial"):
            filepath_thumb = full_path + ".jpg"
        else:
            filepath_thumb = os.path.splitext(full_path)[0] + ".jpg"
        if not self.pcoll.get(filepath_thumb):  # type:ignore[attr-defined]
            return self.pcoll.load(filepath_thumb, filepath_thumb, "IMAGE")
        else:
            return self.pcoll[filepath_thumb]  # type:ignore[index, no-any-return]

    def _add_info_thumbnail(self, thumb_name: str) -> bpy.types.ImagePreview:
        """Loads a thumbnail for this pcoll item.

        Args:
            thumb_name (str): name of the thumbnail image, excluding extension

        Returns:
            list: icon in enumarator
        """
        filepath_thumb = os.path.join(
            get_addon_root(), "user_interface", "icons", f"{thumb_name}.jpg"
        )
        if not self.pcoll.get(filepath_thumb):  # type:ignore[attr-defined]
            return self.pcoll.load(filepath_thumb, filepath_thumb, "IMAGE")
        else:
            return self.pcoll[filepath_thumb]  # type:ignore[index, no-any-return]


def list_files_in_dir(
    search_dir: str,
    search_term: str,
    ext: Union[str, tuple[str, ...]],
    skip_pbr_folder: bool = False,
) -> list[str]:
    """Gets a list of files in dir with certain extension.

    Extension depends on the passed pcoll_type. Also handles search terms the users
    entered in a searchbox

    Args:
        search_dir (str): Directory to search in
        search_term: Only return files with this in their name
        ext: Extension of files, optionally including period
        skip_pbr_folder: Skips folders that have PBR in their name (internal use)

    Returns:
        list: list of file paths in dir of certain extension
    """
    file_paths = []
    for root, _, files in os.walk(search_dir):
        if skip_pbr_folder and "PBR" in root:
            continue  # don't show textures in PBR folder of texture sets``
        for fn in files:
            if fn.lower().endswith(".trial.jpg"):
                file_paths.append(os.path.join(root, fn.replace(".jpg", "")))
            if not fn.lower().endswith(ext):
                continue
            if search_term.lower() not in fn.lower():
                continue
            if fn.startswith("."):
                continue

            full_path = os.path.join(root, fn)
            file_paths.append(full_path)

    hg_log(f"getting files in {search_dir}", level="DEBUG")
    hg_log(f"found files {file_paths}", level="DEBUG")

    return file_paths


def get_display_name(full_path: str) -> str:
    """Transforms internal name to displayable name.

    Args:
        full_path (str): full path of item to make display name for

    Returns:
        str: display name
    """
    display_name: str = os.path.splitext(os.path.basename(full_path))[0]
    for remove_string in ("HG", "Male", "Female"):
        display_name = display_name.replace(remove_string, "")
    return display_name.replace("_", " ")
