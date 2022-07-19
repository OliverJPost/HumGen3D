"""
functions used by properties
"""

import os
from pathlib import Path

import bpy
from HumGen3D.backend.logging import hg_log
from HumGen3D.backend.preferences import get_prefs
from HumGen3D.human.human import Human
from HumGen3D.user_interface.feedback_func import ShowMessageBox  # type:ignore


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
        ext = ".txt"
    else:
        ext = ".blend"

    if gender:
        dir = str(pref.filepath) + str(Path("/{}/{}/{}".format(categ, gender, folder)))
    else:
        dir = str(pref.filepath) + str(Path("/{}/{}".format(categ, folder)))

    if categ == "outfits":
        sett = context.scene.HG3D
        inside = sett.batch_clothing_inside
        outside = sett.batch_clothing_outside
        if inside and not outside:
            ext = "I.blend"
        elif outside and not inside:
            ext = "O.blend"

    return len([name for name in os.listdir(dir) if name.endswith(ext)])


def get_resolutions():
    return [
        ("128", "128 x 128", "", 0),
        ("256", "256 x 256", "", 1),
        ("512", "512 x 512", "", 2),
        ("1024", "1024 x 1024", "", 3),
        ("2048", "2048 x 2048", "", 4),
        ("4096", "4096 x 4096", "", 5),
    ]


def poll_mtc_armature(self, obj):
    return obj.type == "ARMATURE"


def thumbnail_saving_prop_update(self, context):
    switched_to = self.thumbnail_saving_enum

    self.preset_thumbnail = None
    save_folder = os.path.join(get_prefs().filepath, "temp_data")

    if switched_to == "auto":
        full_image_path = os.path.join(save_folder, "temp_thumbnail.jpg")
        if os.path.isfile(full_image_path):
            try:
                img = bpy.data.images.load(full_image_path)
                self.preset_thumbnail = img
            except Exception as e:
                hg_log("Auto thumbnail failed to load with error:", e)

    if switched_to == "last_render":
        render_result = bpy.data.images.get("Render Result")
        hg_log([s for s in render_result.size])
        if not render_result:
            ShowMessageBox("No render result found")
            return
        elif render_result.size[0] > 1024:
            ShowMessageBox("Render result is too big! 256px by 256px is recommended.")
            return

        full_imagepath = os.path.join(save_folder, "temp_render_thumbnail.jpg")
        render_result.save_render(filepath=full_imagepath)

        saved_render_result = bpy.data.images.load(full_imagepath)
        self.preset_thumbnail = saved_render_result
        pass


def add_image_to_thumb_enum(self, context):
    """Adds the custom selected image to the enum"""
    img = self.preset_thumbnail

    self.preset_thumbnail_enum = img.name
