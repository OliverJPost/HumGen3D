# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import os
import random
from pathlib import Path
from re import L
from typing import List, Tuple

from HumGen3D.backend import PREVIEW_COLLECTION_DATA, get_prefs, preview_collections
from HumGen3D.backend.logging import hg_log
from HumGen3D.human.base.decorators import injected_context
from HumGen3D.human.base.exceptions import HumGenException


class PreviewCollectionContent:
    _pcoll_name: str
    _pcoll_gender_split: bool

    def set(self, preset, context=None):
        raise NotImplementedError

    def _set(self, context):
        """Internal way of setting content, only used by enum properties"""
        sett = context.scene.HG3D
        if sett.update_exception:
            return

        active_item = getattr(sett.pcoll, self._pcoll_name)
        try:
            self.set(active_item, context)
        except TypeError:
            self.set(active_item)

    @injected_context
    def set_random(self, context=None, update_ui=False):
        options = self.get_options(context)
        chosen = random.choice(options)

        # TODO make sure random is not the same as previous
        # TODO add catch for empty pcoll

        try:
            self.set(chosen, context)
        except TypeError:
            self.set(chosen)

        if update_ui:
            # Use indirect way so the UI reflects the chosen item
            sett = context.scene.HG3D
            sett.update_exception = True
            setattr(context.HG3D.pcoll, self.pcoll_name, chosen)
            sett.update_exception = False

    @injected_context
    def get_options(self, context=None) -> List[str]:
        # Return only the name from the enum. Skip the first one
        # FIXME check all pcolls if 0 is always skipped
        self.refresh_pcoll(context, ignore_category_and_searchterm=True)
        options = [option[0] for option in self._get_full_options()[1:]]
        if not options:
            raise HumGenException(
                "No options found, did you install the content packs?"
            )

        return options

    def _get_full_options(self):
        """Internal way of getting content, only used by enum properties"""
        pcoll = preview_collections.get(self._pcoll_name).pcoll
        if not pcoll:
            return [
                ("none", "Reload category below", "", 0),
            ]

        return pcoll[self._pcoll_name]

    def get_categories(self):
        if not self._human:
            return [("ERROR", "ERROR", "", i) for i in range(99)]

        return self._find_folders(
            self._pcoll_name, self._pcoll_gender_split, self._human.gender
        )

    def refresh_pcoll(self, context, ignore_category_and_searchterm=False):
        """Refresh the items of this preview collection"""
        sett = context.scene.HG3D
        self._check_for_HumGen_filepath_issues()
        pcoll_name = self._pcoll_name

        if ignore_category_and_searchterm:
            preview_collections[self._pcoll_name].populate(
                context, self._human.gender, use_search_term=False
            )
        else:
            preview_collections[self._pcoll_name].refresh(context, self._human.gender)

        sett.pcoll[pcoll_name] = "none"  # set the preview collection to
        # the 'click here to select' item

    def _check_for_HumGen_filepath_issues(self):
        pref = get_prefs()
        if not pref.filepath:
            raise HumGenException("No filepath selected in HumGen preferences.")
        base_humans_path = pref.filepath + str(Path("content_packs/Base_Humans.json"))

        base_content = os.path.exists(base_humans_path)

        if not base_content:
            raise HumGenException("Filepath selected, but no humans found in path")

    @staticmethod
    def _find_folders(pcoll_name, gender_toggle, gender, include_all=True) -> list:
        """Gets enum of folders found in a specific directory. T
        hese serve as categories for that specific pcoll

        Args:
            context (bpy.context): blender context
            pcoll_name (str): preview collection name
            gender_toggle (bool): Search for folders that are in respective male/female
                folders.
            include_all (bool, optional): include "All" as first item.
                Defaults to True.
            gender_override (str): Used by operations that are not linked to a single
                human. Instead of getting the gender from hg_rig this allows for the
                manual passing of the gender ('male' or 'female')

        Returns:
            list: enum of folders
        """

        pref = get_prefs()

        folder = PREVIEW_COLLECTION_DATA[pcoll_name][2]
        if isinstance(folder, list):
            folder = os.path.join(*folder)

        if gender_toggle:
            categ_folder = os.path.join(pref.filepath, folder, gender)
        else:
            categ_folder = os.path.join(pref.filepath, folder)

        if not os.path.isdir(categ_folder):
            hg_log(
                f"Can't find folder {categ_folder} for preview collection {pcoll_name}",
                level="DEBUG",
            )
            return [("NOT INSTALLED", "NOT INSTALLED", "", i) for i in range(99)]

        dirlist = os.listdir(categ_folder)
        dirlist.sort()
        categ_list = []
        ext = (".jpg", "png", ".jpeg", ".blend")
        # FIXME
        for item in dirlist:
            if not item.endswith(ext) and ".DS_Store" not in item:
                categ_list.append(item)

        if not categ_list:
            categ_list.append("No Category Found")

        enum_list = [("All", "All Categories", "", 0)] if include_all else []
        for i, name in enumerate(categ_list):
            idx = i if pcoll_name == "texture" else i + 1
            enum_list.append((name, name, "", idx))

        if not enum_list:
            return [("ERROR", "ERROR", "", i) for i in range(99)]
        else:
            return enum_list
