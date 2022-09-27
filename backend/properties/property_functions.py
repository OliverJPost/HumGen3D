# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""
Functions used by properties
"""

import os
from pathlib import Path

from HumGen3D.human.human import Human

from ..preferences import get_prefs


def find_folders(
    self, context, categ, gender_toggle, include_all=True, gender_override=None
) -> list:
    """Gets enum of folders found in a specific directory. T
    hese serve as categories for that specific pcoll

    Args:
        context (bpy.context): blender context
        categ (str): preview collection name
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
    human = Human.from_existing(context.active_object, strict_check=False)
    pref = get_prefs()

    if gender_override:
        gender = gender_override
    elif human:
        gender = human.gender
    else:
        return [("ERROR", "ERROR", "", i) for i in range(99)]

    if gender_toggle:
        categ_folder = os.path.join(pref.filepath, categ, gender)
    else:
        categ_folder = os.path.join(pref.filepath, categ)

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
        idx = i if categ == "textures" else i + 1
        enum_list.append((name, name, "", idx))

    if not enum_list:
        return [("ERROR", "ERROR", "", i) for i in range(99)]
    else:
        return enum_list


def find_item_amount(context, categ, gender, folder) -> int:
    """used by batch menu, showing the total amount of items of the selected
    categories

    Batch menu currently disabled
    """
    pref = get_prefs()

    if categ == "expressions":
        ext = ".npy"
    else:
        ext = ".blend"

    if gender:
        dir = str(pref.filepath) + str(Path("/{}/{}/{}".format(categ, gender, folder)))
    else:
        dir = str(pref.filepath) + str(Path("/{}/{}".format(categ, folder)))

    if categ == "outfits":
        sett = context.scene.HG3D
        inside = sett.batch.clothing_inside
        outside = sett.batch.clothing_outside
        if inside and not outside:
            ext = "I.blend"
        elif outside and not inside:
            ext = "O.blend"

    return len([name for name in os.listdir(dir) if name.endswith(ext)])
