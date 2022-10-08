# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""
context.scene.HG3D.custom_content
Properties for creating and managing custom content in Human Generator
"""


import os
from re import L

import bpy
from bpy.props import (  # type: ignore
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from genericpath import isdir
from HumGen3D.backend import get_prefs, hg_log
from HumGen3D.custom_content.possible_content import find_possible_content
from HumGen3D.human.human import Human
from HumGen3D.user_interface.content_panel.operators import (
    refresh_hair_ul,
    refresh_shapekeys_ul,
)
from HumGen3D.user_interface.documentation.feedback_func import ShowMessageBox
from HumGen3D.user_interface.panel_functions import prettify

from ..content_packs.custom_content_packs import build_content_collection
from .property_functions import find_folders


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


def get_preset_thumbnail(self, context) -> list:
    img = self.preset_thumbnail
    return [(img.name, "Selected Thumbnail", "", img.preview.icon_id, 0)] if img else []


def add_image_to_thumb_enum(self, context):
    """Adds the custom selected image to the enum"""
    img = self.preset_thumbnail

    self.preset_thumbnail_enum = img.name


def get_key_subcategories(category_type):
    folder_livekeys = os.path.join(get_prefs().filepath, "livekeys", category_type)
    folder_shapekeys = os.path.join(get_prefs().filepath, "shapekeys", category_type)

    categories = []
    if os.path.isdir(folder_livekeys):
        categories.extend([f.name for f in os.scandir(folder_livekeys) if f.is_dir()])

    if os.path.isdir(folder_shapekeys):
        categories.extend([f.name for f in os.scandir(folder_shapekeys) if f.is_dir()])

    if ".DS_Store" in categories:
        categories.remove(".DS_Store")

    return [(categ, prettify(categ), "", i) for i, categ in enumerate(categories)]


# FIXME load order with class property instead of alphabetical
class ACustomKeyProps(bpy.types.PropertyGroup):
    key_to_save: StringProperty()
    name: StringProperty()
    save_as: EnumProperty(
        name="Save key as:",
        items=[("livekey", "Live Key", "", 0), ("shapekey", "Shape Key", "", 1)],
        default="livekey",
    )
    delete_original: BoolProperty(name="Delete original", default=False)

    category_to_save_to: EnumProperty(
        name="Category to save to",
        items=[
            ("body_proportions", "Body Proportions (Visible)", "", 0),
            ("face_proportions", "Face Proportions (Visible)", "", 1),
            ("face_presets", "Face Presets (Semi-hidden)", "", 2),
            ("expressions", "Expressions (Visible)", "", 3),
            ("special", "Special (Hidden)", "", 4),
        ],
    )

    subcategory: EnumProperty(
        name="Subcategory",
        items=lambda self, _: get_key_subcategories(self.category_to_save_to),
    )
    existing_or_new_subcategory: EnumProperty(
        items=[("existing", "Existing", "", 0), ("new", "Create new", "", 1)],
        default="existing",
    )
    new_category_name: StringProperty()


# FIXME load order with class property instead of alphabetical
class ACustomPoseProps(bpy.types.PropertyGroup):
    name: StringProperty()
    category_to_save_to: EnumProperty(
        name="Pose Category",
        items=[("existing", "Existing", "", 0), ("new", "Create new", "", 1)],
        default="existing",
    )
    chosen_existing_subcategory: EnumProperty(
        name="Pose Library",
        items=lambda self, context: Human.from_existing(
            context.scene.HG3D.custom_content.content_saving_active_human
        ).pose.get_categories(include_all=False),
    )
    new_category_name: StringProperty()


class CustomContentProps(bpy.types.PropertyGroup):
    """Subclass of HG_SETTINGS, properties related to custom_content in HG"""

    key: PointerProperty(type=ACustomKeyProps)
    pose: PointerProperty(type=ACustomPoseProps)
    starting_human_name: StringProperty()

    sk_collection_name: StringProperty(default="")
    show_saved_sks: BoolProperty(default=False, update=refresh_shapekeys_ul)
    show_unchanged: BoolProperty(
        default=False, update=lambda self, context: find_possible_content(context)
    )

    hairstyle_name: StringProperty(default="")
    save_hairtype: EnumProperty(
        name="Hairtype",
        items=[
            ("head", "Regular Hair", "", 0),
            ("face_hair", "Facial Hair", "", 1),
        ],
        default="head",
    )

    savehair_male: BoolProperty(default=True)
    savehair_female: BoolProperty(default=True)
    show_eyesystems: BoolProperty(
        name="Show eye hairsystems", default=False, update=refresh_hair_ul
    )

    clothing_name: StringProperty(default="")
    saveoutfit_categ: EnumProperty(
        name="Clothing type",
        items=[
            ("outfit", "Outfit", "", 0),
            ("footwear", "Footwear", "", 1),
        ],
        default="outfit",
    )

    saveoutfit_male: BoolProperty(default=True)
    saveoutfit_female: BoolProperty(default=True)

    open_exported_outfits: BoolProperty(default=False)
    open_exported_hair: BoolProperty(default=False)
    open_exported_shapekeys: BoolProperty(default=False)

    mtc_armature: PointerProperty(
        name="Armature", type=bpy.types.Object, poll=poll_mtc_armature
    )
    mtc_add_armature_mod: BoolProperty(default=True)
    mtc_parent: BoolProperty(default=True)

    mask_long_arms: BoolProperty(default=False)
    mask_short_arms: BoolProperty(default=False)
    mask_long_legs: BoolProperty(default=False)
    mask_short_legs: BoolProperty(default=False)
    mask_torso: BoolProperty(default=False)
    mask_foot: BoolProperty(default=False)

    pose_name: StringProperty()

    custom_content_categ: EnumProperty(
        name="Content type",
        description="",
        items=[
            ("starting_humans", "Starting Humans", "", 0),
            ("texture_sets", "Texture sets", "", 1),
            ("shapekeys", "Shapekeys", "", 2),
            ("hairstyles", "Hairstyles", "", 3),
            ("pose", "Pose", "", 4),
            ("outfits", "Outfits", "", 5),
            ("footwear", "Footwear", "", 6),
        ],
        default="starting_humans",
        update=build_content_collection,
    )

    content_saving_ui: BoolProperty(default=False)
    content_saving_type: StringProperty()
    mtc_not_in_a_pose: BoolProperty(default=False)

    thumbnail_saving_enum: EnumProperty(
        name="Thumbnail",
        items=[
            ("none", "No thumbnail", "", 0),
            ("auto", "Automatic render", "", 1),
            ("custom", "Select custom image", "", 2),
            ("last_render", "Use last render result", "", 3),
        ],
        default="auto",
        update=thumbnail_saving_prop_update,
    )

    content_saving_tab_index: IntProperty(default=0)

    content_saving_active_human: PointerProperty(type=bpy.types.Object)
    content_saving_object: PointerProperty(type=bpy.types.Object)
    preset_name: StringProperty(default="")

    preset_thumbnail_enum: EnumProperty(
        items=get_preset_thumbnail,
    )
    preset_thumbnail: PointerProperty(
        type=bpy.types.Image,
        description="Thumbnail image for starting human",
        update=add_image_to_thumb_enum,
    )
