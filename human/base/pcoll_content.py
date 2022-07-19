import os
import random
from typing import List, Tuple

from HumGen3D.backend.preferences import get_prefs
from HumGen3D.backend.preview_collections import preview_collections
from HumGen3D.human.base.decorators import injected_context


class PreviewCollectionContent:
    _pcoll_name: str
    _pcoll_gender_split: bool

    def set(self, preset, context=None):
        raise NotImplementedError

    def _set(self, context):
        """Internal way of setting content, only used by enum properties"""
        active_item = getattr(context.scene.HG3D.pcoll, self._pcoll_name)
        try:
            self.set(active_item, context)
        except TypeError:
            self.set(active_item)

    def set_random(self, context=None):
        options = self.get_options()
        chosen = random.choice(options)

        # Use indirect way so the UI reflects the chosen item
        setattr(context.HG3D.pcoll, self.pcoll_name, chosen)

    def get_options(self) -> List[Tuple[str, str, str, int]]:
        return [option[0] for option in self._get_full_options()]

    def _get_full_options(self):
        """Internal way of getting content, only used by enum properties"""
        pcoll = preview_collections.get(self._pcoll_name)
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

        if gender_toggle:
            categ_folder = os.path.join(pref.filepath, pcoll_name, gender)
        else:
            categ_folder = os.path.join(pref.filepath, pcoll_name)

        if not os.path.isdir(categ_folder):
            return [("NOT INSTALLED", "NOT INSTALLED", "", i) for i in range(99)]

        dirlist = os.listdir(categ_folder)
        dirlist.sort()
        categ_list = []
        ext = (".jpg", "png", ".jpeg", ".blend")
        for item in dirlist:
            if not item.endswith(ext) and ".DS_Store" not in item:
                categ_list.append(item)

        if not categ_list:
            categ_list.append("No Category Found")

        enum_list = [("All", "All Categories", "", 0)] if include_all else []
        for i, name in enumerate(categ_list):
            idx = i if pcoll_name == "textures" else i + 1
            enum_list.append((name, name, "", idx))

        if not enum_list:
            return [("ERROR", "ERROR", "", i) for i in range(99)]
        else:
            return enum_list
