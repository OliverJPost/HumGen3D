import os
import platform
import subprocess
from ast import Str

import bpy
from bpy.props import BoolProperty, EnumProperty, PointerProperty, StringProperty
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.custom_content.possible_content import (
    POSSIBLE_CONTENT_ITEM,
    find_possible_content,
)
from HumGen3D.human.clothing.add_obj_to_clothing import get_human_from_distance
from HumGen3D.human.human import Human
from HumGen3D.user_interface.documentation.feedback_func import ShowMessageBox


class HG_OT_START_SAVING_PROCESS(bpy.types.Operator):
    bl_idname = "hg3d.start_saving"
    bl_label = "Save to library"
    bl_description = "Save this item to the Human Generator content library"
    bl_options = {"UNDO"}

    category: StringProperty()
    key_name: StringProperty()

    def execute(self, context):
        cc_sett = context.scene.HG3D.custom_content
        cc_sett.content_saving_ui = True
        cc_sett.content_saving_type = self.category
        if self.category == "key":
            cc_sett.key.key_to_save = self.key_name
        cc_sett.content_saving_tab_index = 0
        cc_sett.content_saving_active_human = Human.find_hg_rig(context.object)
        return {"FINISHED"}


class HG_OT_REFRESH_POSSIBLE_CONTENT(bpy.types.Operator):
    bl_idname = "hg3d.refresh_possible_content"
    bl_label = "Refresh"
    bl_description = "Refresh list of possible content items."
    bl_options = {"UNDO"}

    def execute(self, context):
        find_possible_content(context)
        return {"FINISHED"}


class HG_OT_SAVE_TO_LIBRARY(bpy.types.Operator):
    bl_idname = "hg3d.save_to_library"
    bl_label = "Save to library"
    bl_description = "Save this item to the Human Generator content library"
    bl_options = {"UNDO"}

    def execute(self, context):
        cc_sett = context.scene.HG3D.custom_content
        category = cc_sett.content_saving_type
        human = Human.from_existing(cc_sett.content_saving_active_human)

        thumbnail = cc_sett.preset_thumbnail

        if category == "key":
            key_to_save = cc_sett.key.key_to_save
            key_name = cc_sett.key.name
            key_category = cc_sett.key.category_to_save_to
            key_subcategory = cc_sett.key.subcategory
            as_livekey = cc_sett.key.save_as == "livekey"
            delete_original = as_livekey and cc_sett.key.delete_original
            human.keys[key_to_save].save_to_library(
                key_name,
                key_category,
                key_subcategory,
                as_livekey=as_livekey,
                delete_original=delete_original,
            )
        elif category == "pose":
            name = cc_sett.pose.name
            if cc_sett.pose.category_to_save_to == "existing":
                subcategory = cc_sett.pose.chosen_existing_subcategory
            else:
                subcategory = cc_sett.pose.new_category_name

            human.pose.save_to_library(name, subcategory, thumbnail, context)

        cc_sett.content_saving_ui = False
        ShowMessageBox("Succesfully saved!", title="HG Content Saving")
        return {"FINISHED"}


class HG_OT_ADD_OBJ_TO_OUTFIT(bpy.types.Operator):
    bl_idname = "hg3d.add_obj_to_outfit"
    bl_label = "Add object to outfit"
    bl_description = "Add object to outfit"
    bl_options = {"UNDO"}

    cloth_type: EnumProperty(
        items=[
            ("torso", "Torso", "", 0),
            ("pants", "Pants", "", 1),
            ("full", "Full Body", "", 2),
            ("footwear", "Footwear", "", 3),
        ],
        default="torso",
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        col = self.layout
        col.label(text="What type of clothing is this?")

        col = col.column()
        col.scale_y = 1.5
        col.prop(self, "cloth_type", expand=True)

    def execute(self, context):
        cloth_obj = context.object
        human = get_human_from_distance(cloth_obj)

        if self.cloth_type == "footwear":
            human.footwear.add_obj(cloth_obj, context)
        else:
            human.outfit.add_obj(cloth_obj, self.cloth_type, context)


class HG_OT_SAVE_SK(bpy.types.Operator):
    bl_idname = "hg3d.save_sk_to_library"
    bl_label = "Save shapekey to library"
    bl_description = "Saves this shape key to the library as a LiveKey"
    bl_options = {"UNDO"}

    save_type: EnumProperty(
        items=[
            ("shapekey", "Shape key by default", "", 0),
            ("livekey", "LiveKey", "", 1),
        ],
        default="livekey",
    )
    delete_original = BoolProperty(default=False, name="Delete original")

    sk_name: StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout

        layout.label(text="How do you want to save this key?")
        col = layout.column(align=True)
        col.prop(self, "save_type", expand=True)

        if self.save_type == "livekey":
            col.prop(self, "delete_original")

    def execute(self, context):
        human = Human.from_existing(context.object)
        bpy_key = human.body_obj.data.shape_keys.key_blocks[self.sk_name]

        key = next(key for key in human.keys if key.as_bpy() == bpy_key)

        delete_original = (
            True if self.save_type == "livekey" and self.delete_original else False
        )
        key.save_to_library(
            as_livekey=self.save_type == "livekey", delete_original=delete_original
        )


class HG_OT_OPEN_FOLDER(bpy.types.Operator):
    """Open the folder that belongs to this section

    API: False

    Operator type:
        Open subprocess

    Prereq:
        subpath passed
    """

    bl_idname = "hg3d.openfolder"
    bl_label = "Open folder"
    bl_description = "Opens the folder that belongs to this type of content"

    subpath: bpy.props.StringProperty()

    def execute(self, context):
        pref = get_prefs()
        path = os.path.join(pref.filepath, self.subpath)

        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

        return {"FINISHED"}
