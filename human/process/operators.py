# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Texture baking operators."""


import importlib
import json
import logging
import os
import sys
import uuid

import bpy
from HumGen3D.backend import hg_log
from HumGen3D.backend.content.content_saving import remove_number_suffix
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.backend.properties.process_props import get_preset_list
from HumGen3D.common import find_multiple_in_list
from HumGen3D.common.collections import add_to_collection
from HumGen3D.human.human import Human
from HumGen3D.human.process.apply_modifiers import apply_modifiers
from HumGen3D.human.process.process import ProcessSettings
from HumGen3D.user_interface.documentation.feedback_func import ShowMessageBox
from mathutils import Vector


def status_text_callback(header, context):
    bake_sett = context.scene.HG3D.process.baking
    layout = header.layout

    layout.separator_spacer()
    layout.alignment = "EXPAND"

    row = layout.row(align=False)
    row.alignment = "CENTER"

    layout.label(
        text=f"Rendering texture {bake_sett.idx}/{bake_sett.total}",
        icon="TIME",
    )

    col = layout.column()
    col.scale_x = 1.6
    col.prop(bake_sett, "progress")

    layout.label(text="Press ESC to cancel", icon="EVENT_ESC")

    layout.separator_spacer()


class HG_OT_PROCESS(bpy.types.Operator):
    bl_idname = "hg3d.process"
    bl_label = "Process"
    bl_description = "Process according to these settings."
    bl_options = {"UNDO"}

    def execute(self, context):  # noqa
        pr_sett = context.scene.HG3D.process
        human_rigs = find_multiple_in_list(context.selected_objects)
        for rig_obj in human_rigs:
            human = Human.from_existing(rig_obj)
            if pr_sett.output != "replace":
                human = human.duplicate(context)
                if pr_sett.output == "duplicate":
                    human.location += Vector((0, 2, 0))
                for obj in human.objects:
                    add_to_collection(context, obj, "Processing Results")

            if pr_sett.haircards_enabled:
                quality = pr_sett.haircards.quality
                if human.hair.regular_hair.modifiers:
                    human.hair.regular_hair.convert_to_haircards(quality, context)
                human.hair.eyebrows.convert_to_haircards(quality, context)
                human.hair.eyelashes.convert_to_haircards(quality, context)
                if pr_sett.haircards.face_hair and human.hair.face_hair.modifiers:
                    human.hair.face_hair.convert_to_haircards(quality, context)
                human.objects.rig["haircards"] = True

            if pr_sett.baking_enabled:
                human.process.baking.bake_all(
                    samples=int(context.scene.HG3D.process.baking.samples),
                    context=context,
                )
                human.objects.rig["hg_baked"] = True

            if pr_sett.lod_enabled:
                human.process.lod.set_body_lod(int(pr_sett.lod.body_lod))
                human.process.lod.set_clothing_lod(
                    pr_sett.lod.decimate_ratio,
                    pr_sett.lod.remove_clothing_subdiv,
                    pr_sett.lod.remove_clothing_solidify,
                )
                human.objects.rig["lod"] = True

            if pr_sett.rig_renaming_enabled:
                naming_sett = context.scene.HG3D.process.rig_renaming
                props = naming_sett.bl_rna.properties
                prop_dict = {
                    str(prop.identifier): str(getattr(naming_sett, prop.identifier))
                    for prop in props
                }
                human.process.rename_bones_from_json(json.dumps(prop_dict))
                human.objects.rig["bones_renamed"] = True

            if pr_sett.renaming_enabled:
                obj_naming_sett = context.scene.HG3D.process.renaming
                props = obj_naming_sett.bl_rna.properties
                prop_dict = {
                    str(prop.identifier): str(getattr(obj_naming_sett, prop.identifier))
                    for prop in props
                }
                human.process.rename_objects_from_json(
                    json.dumps(prop_dict),
                    custom_token=obj_naming_sett.custom_token,
                    suffix=obj_naming_sett.suffix if obj_naming_sett.use_suffix else "",
                )
                material_naming_sett = context.scene.HG3D.process.renaming.materials
                props = material_naming_sett.bl_rna.properties
                prop_dict = {
                    str(prop.identifier): str(
                        getattr(material_naming_sett, prop.identifier)
                    )
                    for prop in props
                }
                human.process.rename_materials_from_json(
                    json.dumps(prop_dict),
                    custom_token=obj_naming_sett.custom_token,
                    suffix=obj_naming_sett.suffix
                    if material_naming_sett.use_suffix
                    else "",
                )
                human.objects.rig["parts_renamed"] = True
            if pr_sett.scripting_enabled:
                for item in context.scene.hg_scripts_col:
                    if item.name in sys.modules:
                        module = importlib.reload(sys.modules[item.name])
                    else:
                        sys.path.append(item.path)
                        module = importlib.import_module(item.name[:-3])
                        module = importlib.reload(module)
                        sys.path.remove(item.path)
                    module.main(context, human)

            if pr_sett.modapply_enabled:
                apply_modifiers(human, context=context)
                human.objects.rig["modifiers_applied"] = True

            if pr_sett.output == "export":
                fn = remove_number_suffix(
                    pr_sett.output_name.replace("{name}", human.name).strip()
                )
                export_method = getattr(
                    human.export, f"to_{pr_sett.file_type[1:].lower()}"
                )
                filepath = os.path.join(pr_sett.baking.export_folder, fn)
                export_method(filepath)
                human.delete()

        if not pr_sett.output == "export":
            ShowMessageBox("Processing completed", "Processing completed", "INFO")
        else:
            ShowMessageBox(
                f"Saved to {pr_sett.baking.export_folder}", "Export completed", "INFO"
            )
        return {"FINISHED"}


class HG_OT_REMOVE_SCRIPT(bpy.types.Operator):
    bl_idname = "hg3d.remove_script"
    bl_label = "Remove script"
    bl_description = "Remove script from the list."

    name: bpy.props.StringProperty()

    def execute(self, context):
        coll = context.scene.hg_scripts_col

        item_idx = next(i for i, item in enumerate(coll) if item.name == self.name)
        coll.remove(item_idx)
        return {"FINISHED"}


class HG_OT_MOVE_SCRIPT(bpy.types.Operator):
    bl_idname = "hg3d.move_script"
    bl_label = "Move script"
    bl_description = "Move script up or down in the stack."

    name: bpy.props.StringProperty()
    move_up: bpy.props.BoolProperty()

    def execute(self, context):
        coll = context.scene.hg_scripts_col

        item_idx = next(i for i, item in enumerate(coll) if item.name == self.name)
        if item_idx > 0 and not self.move_up:
            coll.move(item_idx, item_idx - 1)
        elif item_idx < len(coll) and self.move_up:
            coll.move(item_idx, item_idx + 1)

        return {"FINISHED"}


class HG_OT_ADD_SCRIPT(bpy.types.Operator):
    bl_idname = "hg3d.add_script"
    bl_label = "Add script"
    bl_description = "Add new script."

    name: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        col = self.layout.column()
        col.label(text="Give a name to your script:")

        subcol = col.column()
        subcol.scale_y = 1.5
        py_in_name = ".py" in self.name
        non_valid = any(char in self.name for char in r"\/:*?<>| .")
        subcol.alert = py_in_name or non_valid
        subcol.prop(self, "name", text="")
        if py_in_name:
            subcol.label(text="Don't include file extension.", icon="ERROR")
        elif non_valid:
            subcol.label(text="Only letters, numbers and underscores.", icon="ERROR")

    def execute(self, context):
        textblock = bpy.data.texts.new(self.name + ".py")
        textblock.write(
            '''"""You can place a decsription of your script here, it will be displayed in the interface."""
# This is a script template. DON'T FORGET TO SAVE!
# Saved scripts will appear in available scripts list.
# For API documentation, see https://help.humgen3d.com

import bpy
from HumGen3D import Human

def main(context: bpy.types.Context, human: Human):
    """This function is called when the script is executed.

    Args:
        context (bpy.types.Context): Blender context.
        human (Human): Instance of a single human. Script will be run for each human.
    """
    pass # Your code goes here
'''
        )
        textblock.filepath = os.path.join(
            get_prefs().filepath, "scripts", self.name + ".py"
        )
        coll = context.scene.hg_scripts_col
        coll.add().name = self.name + ".py"

        with open(textblock.filepath, "w") as f:
            f.write(textblock.as_string())

        scripting_workspace = bpy.data.workspaces.get("Scripting")
        if scripting_workspace:
            context.window.workspace = scripting_workspace

            # Set active text in text editor window
            for screen in scripting_workspace.screens:
                for area in screen.areas:
                    if area.type == "TEXT_EDITOR":
                        for space in area.spaces:
                            if space.type == "TEXT_EDITOR":
                                space.text = textblock
                                break
                        break
        else:
            ShowMessageBox(
                "Couldn't find Scripting workspace. Please open it manually."
            )
        return {"FINISHED"}


class HG_OT_ADD_LOD_OUTPUT(bpy.types.Operator):
    bl_idname = "hg3d.add_lod_output"
    bl_label = "Add LOD output."
    bl_description = "Adds a new output item for LODs."
    bl_options = {"UNDO"}

    def execute(self, context):
        coll = context.scene.lod_output_col

        last_item = coll[-1] if coll else None
        item = coll.add()
        item.name = str(uuid.uuid4())
        if last_item and last_item.suffix[-1].isdigit():
            new_index = int(last_item.suffix[-1]) + 1
            item.suffix = f"_LOD{new_index}"

        return {"FINISHED"}


class HG_OT_REMOVE_LOD_OUTPUT(bpy.types.Operator):
    bl_idname = "hg3d.remove_lod_output"
    bl_label = "Remove LOD output."
    bl_description = "Remove this output from the list."
    bl_options = {"UNDO"}

    name: bpy.props.StringProperty()

    def execute(self, context):
        item = context.scene.lod_output_col.find(self.name)
        context.scene.lod_output_col.remove(item)
        return {"FINISHED"}


def get_existing_groups(self, context):
    path = os.path.join(get_prefs().filepath, "process_templates")
    # Return all directories in the process_templates folder
    return [
        (f.name, f.name, f.name)
        for f in os.scandir(path)
        if f.is_dir() and not f.name.startswith(".")
    ]


class HG_OT_SAVE_PROCESS_TEMPLATE(bpy.types.Operator):
    bl_idname = "hg3d.save_process_template"
    bl_label = "Save template."
    bl_description = "Save current settings as a template."

    name: bpy.props.StringProperty(name="Template name")
    new_or_existing: bpy.props.EnumProperty(
        items=[
            ("existing", "Existing", "Add to an existing group.", 0),
            ("new", "New", "Create a new group.", 1),
        ]
    )
    existing_groups: bpy.props.EnumProperty(items=get_existing_groups)
    new_group_name: bpy.props.StringProperty(name="New group name")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        col = self.layout.column()
        col.label(text="Give a name to your template:")

        subcol = col.column()
        subcol.scale_y = 1.5
        subcol.alert = self.name in [
            name for _, name, *_ in get_preset_list(None, None)
        ]
        subcol.prop(self, "name", text="")
        if subcol.alert:
            subcol.label(text="Will override existing.", icon="ERROR")

        col = self.layout.column()
        col.label(text="Category:")
        col.scale_y = 1.5
        row = col.row()
        row.prop(self, "new_or_existing", expand=True)
        if self.new_or_existing == "existing":
            col.prop(self, "existing_groups", text="")
        else:
            col.prop(self, "new_group_name", text="Name")

    def execute(self, context):
        if self.new_or_existing == "existing":
            group = self.existing_groups
        else:
            group = self.new_group_name

        path = os.path.join(get_prefs().filepath, "process_templates", group)
        ProcessSettings.save_settings_to_template(path, self.name, context)

        return {"FINISHED"}


# TODO progress bar
class HG_BAKE(bpy.types.Operator):
    """Bake all textures."""

    bl_idname = "hg3d.bake"
    bl_label = "Bake"
    bl_description = "Bake all textures"
    bl_options = {"UNDO"}

    def __init__(self):
        """Init"""
        self.timer = None
        self.bake_idx = 0
        self.image_dict = {}
        self.finish_modal = False

    def invoke(self, context, event):
        self.human = Human.from_existing(context.object)
        self.baketextures = self.human.process.baking.get_baking_list()

        bake_sett = context.scene.HG3D.process.baking
        bake_sett.total = len(self.baketextures)
        bake_sett.idx = 1

        (
            cancelled,
            self.switched_to_cuda,
            self.old_samples,
            _,
        ) = self.human.process.baking._check_bake_render_settings(
            context, samples=int(bake_sett.samples), force_cycles=False
        )

        if cancelled:
            return {"FINISHED"}

        wm = context.window_manager
        wm.modal_handler_add(self)

        self.timer = wm.event_timer_add(0.01, window=context.window)
        context.workspace.status_text_set(status_text_callback)

        return {"RUNNING_MODAL"}

    def modal(self, context, event):  # noqa CCR001
        bake_sett = context.scene.HG3D.process.baking

        if self.finish_modal:
            self.human.process.baking.set_up_new_materials(self.baketextures)
            context.area.tag_redraw()
            context.workspace.status_text_set(text=None)
            bake_sett.idx = 0

            if self.switched_to_cuda:
                context.preferences.addons[
                    "cycles"
                ].preferences.compute_device_type = "OPTIX"

            context.scene.cycles.samples = self.old_samples

            return {"FINISHED"}

        elif event.type in ["ESC"]:
            hg_log("Cancelling baking modal")

            self.finish_modal = True
            return {"RUNNING_MODAL"}

        elif event.type == "TIMER":
            if self.bake_idx == bake_sett.total:
                self.finish_modal = True
                return {"RUNNING_MODAL"}

            baketexture = self.baketextures[self.bake_idx - 1]

            self.human.process.baking.bake_single_texture(baketexture)
            self.bake_idx += 1
            bake_sett.idx += 1

            if self.bake_idx > 0:
                progress = self.bake_idx / bake_sett.total
                bake_sett.progress = int(progress * 100)

            context.workspace.status_text_set(status_text_callback)
            return {"RUNNING_MODAL"}

        else:
            return {"RUNNING_MODAL"}
