# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from shutil import copyfile

import bpy
from HumGen3D.backend import get_addon_root, get_prefs, hg_delete, hg_log
from HumGen3D.human.base.shapekey_calculator import (
    build_distance_dict,
    deform_obj_from_difference,
)
from HumGen3D.human.height.height import apply_armature
from HumGen3D.human.keys.keys import apply_shapekeys
from HumGen3D.user_interface.documentation.feedback_func import (
    ShowMessageBox,
    show_message,
)
from mathutils import Vector

refresh_pcoll = None  # FIXME


class Content_Saving_Operator:
    def overwrite_warning(self):
        """Show a warning popup if the file already exists"""
        layout = self.layout
        col = layout.column(align=True)
        col.label(text=f'"{self.name}" already exists in:')
        col.label(text=self.folder)
        col.separator()
        col.label(text="Overwrite?")

    def save_thumb(self, folder, img_name, save_name):
        """Save the thumbnail with this content

        Args:
            folder (Path): folder where to save it
            current_name (str): current name of the image
            save_name (str): name to save the image as
        """
        img = bpy.data.images[img_name]
        thumbnail_type = self.sett.thumbnail_saving_enum

        destination_path = os.path.join(folder, f"{save_name}.jpg")
        if thumbnail_type in ("last_render", "auto"):
            image_name = (
                "temp_render_thumbnail"
                if thumbnail_type == "last_render"
                else "temp_thumbnail"
            )
            source_image = os.path.join(
                get_prefs().filepath, "temp_data", f"{image_name}.jpg"
            )
            hg_log("Copying", source_image, "to", destination_path)
            copyfile(source_image, destination_path)

        else:
            try:
                img.filepath_raw = os.path.join(folder, f"{save_name}.jpg")
                img.file_format = "JPEG"
                img.save()
            except RuntimeError as e:
                show_message(self, "Thumbnail image doesn't have any image data")
                print(e)

    @staticmethod
    def save_objects_optimized(
        context,
        objs,
        folder,
        filename,
        clear_sk=True,
        clear_materials=True,
        clear_vg=True,
        clear_ps=True,
        run_in_background=True,
        clear_drivers=True,
    ):
        """Saves the passed objects as a new blend file, opening the file in the
        background to make it as small as possible

        Args:
            objs              (list)          : List of objects to save
            folder            (Path)          : Folder to save the file in
            filename          (str)           : Name to save the file as
            clear_sk          (bool, optional): Remove all shapekeys from objs.
                                                Defaults to True.
            clear_materials   (bool, optional): Remove all materials from objs.
                                                Defaults to True.
            clear_vg          (bool, optional): Remove all vertex groups from
                                                objs. Defaults to True.
            clear_ps          (bool, optional): Remove all particle systems from
                                                objs. Defaults to True.
            run_in_background (bool, optional): Open the new subprocess in the
                                                background. Defaults to True.
        """
        for obj in objs:
            if obj.type != "MESH":
                continue
            if clear_materials:
                obj.data.materials.clear()
            if clear_vg:
                obj.vertex_groups.clear()
            if clear_sk:
                Content_Saving_Operator._remove_shapekeys(obj)
            if clear_ps:
                Content_Saving_Operator._remove_particle_systems(context, obj)
            if clear_drivers:
                Content_Saving_Operator._remove_obj_drivers(obj)

        if clear_drivers:
            Content_Saving_Operator._clear_sk_drivers()

        new_scene = bpy.data.scenes.new(name="test_scene")
        new_col = bpy.data.collections.new(name="HG")
        new_scene.collection.children.link(new_col)
        for obj in objs:
            new_col.objects.link(obj)

        if not os.path.exists(folder):
            os.makedirs(folder)

        blend_filepath = os.path.join(folder, f"{filename}.blend")
        bpy.data.libraries.write(blend_filepath, {new_scene})

        python_file = os.path.join(get_addon_root(), "scripts", "hg_purge.py")
        if run_in_background:
            hg_log("STARTING HumGen background process", level="BACKGROUND")
            background_blender = subprocess.Popen(
                [
                    bpy.app.binary_path,
                    blend_filepath,
                    "--background",
                    "--python",
                    python_file,
                ],
                stdout=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                [bpy.app.binary_path, blend_filepath, "--python", python_file]
            )

        bpy.data.scenes.remove(new_scene)
        for obj in objs:
            hg_delete(obj)

    def _clear_sk_drivers(self):
        for key in bpy.data.shape_keys:
            try:
                fcurves = key.animation_data.drivers
                for _ in fcurves:
                    fcurves.remove(fcurves[0])
            except AttributeError:
                pass

    def _remove_obj_drivers(self, obj):
        try:
            drivers_data = obj.animation_data.drivers

            for dr in drivers_data[:]:
                obj.driver_remove(dr.data_path, -1)
        except AttributeError:
            return

    def _remove_particle_systems(self, context, obj):
        """Remove particle systems from the passed object

        Args:
            obj (Object): obj to remove particle systems from
        """
        context.view_layer.objects.active = obj
        for i, ps in enumerate(obj.particle_systems):
            obj.particle_systems.active_index = i
            bpy.ops.object.particle_system_remove()

    def _remove_shapekeys(self, obj):
        """Remove shapekeys from the passed object

        Args:
            obj (Object): obj to remove shapekeys from
        """
        for sk in [sk for sk in obj.data.shape_keys.key_blocks if sk.name != "Basis"]:
            obj.shape_key_remove(sk)
        if obj.data.shape_keys:
            obj.shape_key_remove(obj.data.shape_keys.key_blocks["Basis"])

    def remove_number_suffix(self, name) -> str:
        """Remove the number suffix from the passed name
        (i.e. Box.004 becomes Box)

        Args:
            name (str): name to remove suffix from

        Returns:
            str: name without suffix
        """
        re_suffix = re.search(r".\d\d\d", name)
        if not re_suffix or not name.endswith(re_suffix.group(0)):
            return name
        else:
            return name.replace(re_suffix.group(0), "")


class HG_OT_SAVEHAIR(bpy.types.Operator, Content_Saving_Operator):
    bl_idname = "hg3d.save_hair"
    bl_label = "Save hairstyle"
    bl_description = "Save hairstyle"

    name: bpy.props.StringProperty()

    def invoke(self, context, event):
        pref = get_prefs()
        self.cc_sett = context.scene.HG3D.custom_content

        self.hg_rig = self.cc_sett.content_saving_active_human
        try:
            pass  # TODO unhide_human(self.hg_rig)
        except Exception as e:
            show_message(self, "Could not find human, did you delete it?")
            hg_log("Content saving failed, rig could not be found with error: ", e)
            return {"CANCELLED"}

        self.thumb = self.cc_sett.preset_thumbnail_enum

        self.folder = pref.filepath + str(Path(f"/hair/{self.cc_sett.save_hairtype}/"))
        self.name = self.cc_sett.hairstyle_name
        if os.path.isfile(str(Path(f"{self.folder}/{self.name}.blend"))):
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)

    def draw(self, context):
        self.overwrite_warning()

    def execute(self, context):
        sett = self.cc_sett
        pref = get_prefs()

        hg_rig = self.hg_rig
        hg_body = hg_rig.HG.body_obj
        col = context.scene.savehair_col

        hair_obj = hg_body.copy()
        hair_obj.data = hair_obj.data.copy()
        hair_obj.name = "HG_Body"
        context.collection.objects.link(hair_obj)

        context.view_layer.objects.active = hair_obj
        hair_obj.select_set(True)
        self._remove_other_systems(
            hair_obj, [item.ps_name for item in col if item.enabled]
        )

        keep_vgs = self._find_vgs_used_by_hair(hair_obj)
        for vg in [vg for vg in hair_obj.vertex_groups if vg.name not in keep_vgs]:
            hair_obj.vertex_groups.remove(vg)

        genders = [
            gd
            for gd, enabled in {
                "male": sett.savehair_male,
                "female": sett.savehair_female,
            }.items()
            if enabled
        ]
        for gender in genders:
            hair_type = sett.save_hairtype
            if hair_type == "face_hair" and gender == "female":
                continue

            if hair_type == "head":
                folder = os.path.join(
                    pref.filepath, "hair", hair_type, gender, "Custom"
                )
            else:
                folder = os.path.join(pref.filepath, "hair", hair_type, "Custom")

            if not os.path.exists(folder):
                os.makedirs(folder)
            if not self.cc_sett.thumbnail_saving_enum == "none":
                self.save_thumb(folder, self.thumb, self.name)

            self._make_hair_json(context, hair_obj, folder, self.name)

        self.save_objects_optimized(
            context,
            [
                hair_obj,
            ],
            self.folder,
            self.name,
            clear_ps=False,
            clear_vg=False,
        )

        context.view_layer.objects.active = hg_rig
        msg = f"Saved {self.name} to {self.folder}"
        self.report({"INFO"}, msg)
        ShowMessageBox(message=msg)

        sett.content_saving_ui = False

        context.view_layer.objects.active = hg_rig
        refresh_pcoll(self, context, "hair")
        refresh_pcoll(self, context, "face_hair")

        return {"FINISHED"}

    def _find_vgs_used_by_hair(self, hair_obj) -> list:
        """Get a list of all vertex groups used by the hair systems

        Args:
            hair_obj (bpy.types.Object): Human body the hair is on

        Returns:
            list: list of vertex groups that are used by hairsystems
        """
        all_vgs = [vg.name for vg in hair_obj.vertex_groups]
        keep_vgs = []
        for ps in [
            ps for ps in hair_obj.particle_systems
        ]:  # TODO only iterate over selected systems
            vg_types = [
                ps.vertex_group_clump,
                ps.vertex_group_density,
                ps.vertex_group_field,
                ps.vertex_group_kink,
                ps.vertex_group_length,
                ps.vertex_group_rotation,
                ps.vertex_group_roughness_1,
                ps.vertex_group_roughness_2,
                ps.vertex_group_roughness_end,
                ps.vertex_group_size,
                ps.vertex_group_tangent,
                ps.vertex_group_twist,
                ps.vertex_group_velocity,
            ]
            for used_vg in vg_types:
                if used_vg in all_vgs:
                    keep_vgs.append(used_vg)

        return keep_vgs

    def _remove_other_systems(self, obj, keep_list):
        """Remove particle systems that are nog going to be saved

        Args:
            obj (bpy.types.Object): Human body object to remove systems from
            keep_list (list): List of names of particle systems to keep
        """
        remove_list = [
            ps.name for ps in obj.particle_systems if ps.name not in keep_list
        ]

        for ps_name in remove_list:
            ps_idx = [
                i for i, ps in enumerate(obj.particle_systems) if ps.name == ps_name
            ]
            obj.particle_systems.active_index = ps_idx[0]
            bpy.ops.object.particle_system_remove()

    def _make_hair_json(self, context, hair_obj, folder, style_name):
        """Make a json that contains the settings for this hairstyle and save it

        Args:
            context (context): bl context
            hair_obj (bpy.types.Object): Body object the hairstyles are on
            folder (str): Folder to save json to
            style_name (str): Name of this style
        """
        ps_dict = {}
        for mod in hair_obj.modifiers:
            if mod.type == "PARTICLE_SYSTEM":
                ps = mod.particle_system
                ps_length = ps.settings.child_length
                ps_children = ps.settings.child_nbr
                ps_steps = ps.settings.display_step
                ps_dict[ps.name] = {
                    "length": ps_length,
                    "children_amount": ps_children,
                    "path_steps": ps_steps,
                }

        json_data = {
            "blend_file": f"{style_name}.blend",
            "hair_systems": ps_dict,
        }

        full_path = os.path.join(folder, f"{style_name}.json")

        with open(full_path, "w") as f:
            json.dump(json_data, f, indent=4)


# TODO origin to model origin? Correction?
class HG_OT_SAVEOUTFIT(bpy.types.Operator, Content_Saving_Operator):
    """Save this outfit to the content folder

    Args:
        name (str): Internal prop
        alert (str): Internal prop #TODO check if redundant
    """

    bl_idname = "hg3d.save_clothing"
    bl_label = "Save as outfit"
    bl_description = "Save as outfit"
    bl_options = {"UNDO"}

    name: bpy.props.StringProperty()
    alert: bpy.props.StringProperty()

    def invoke(self, context, event):
        self.pref = get_prefs()
        self.cc_sett = context.scene.HG3D.custom_content
        self.hg_rig = self.cc_sett.content_saving_active_human
        self.col = context.scene.saveoutfit_col

        self.thumb = self.cc_sett.preset_thumbnail_enum

        obj_list_without_suffix = [
            self.remove_number_suffix(item.obj_name) for item in self.col
        ]
        if len(obj_list_without_suffix) != len(set(obj_list_without_suffix)):
            show_message(
                self,
                "There are objects in the list which have the same names if suffix like .001 is removed",
            )
            return {"CANCELLED"}

        self.folder = os.path.join(self.pref.filepath, self.cc_sett.saveoutfit_categ)
        self.name = self.cc_sett.clothing_name

        if os.path.isfile(
            str(Path(f"{self.folder}/{self.hg_rig.HG.gender}/Custom/{self.name}.blend"))
        ):
            self.alert = "overwrite"
            return context.window_manager.invoke_props_dialog(self)

        return self.execute(context)

    def draw(self, context):
        self.overwrite_warning()

    def execute(self, context):
        sett = self.cc_sett
        col = self.col
        objs = [bpy.data.objects[item.obj_name] for item in col]

        genders = []
        if sett.saveoutfit_female:
            genders.append("female")
        if sett.saveoutfit_male:
            genders.append("male")

        for gender in genders:
            gender_folder = self.folder + str(Path(f"/{gender}/Custom"))
            if not os.path.isdir(gender_folder):
                os.mkdir(gender_folder)
            if not self.cc_sett.thumbnail_saving_enum == "none":
                self.save_thumb(gender_folder, self.thumb, self.name)

        body_copy = self.hg_rig.HG.body_obj.copy()
        body_copy.data = body_copy.data.copy()
        context.collection.objects.link(body_copy)
        apply_shapekeys(body_copy)
        apply_armature(body_copy)

        self.save_material_textures(objs)
        obj_distance_dict = {}
        for obj in objs:
            distance_dict = build_distance_dict(body_copy, obj, apply=False)  # FIXME
            obj_distance_dict[obj.name] = distance_dict

        for gender in genders:
            export_list = []
            backup_human = next(
                (obj for obj in self.hg_rig.HG.backup.children if "hg_body" in obj)
            )
            if gender == "male":
                backup_human = backup_human.copy()
                backup_human.data = backup_human.data.copy()
                context.collection.objects.link(backup_human)
                sks = backup_human.data.shape_keys.key_blocks
                for sk in sks:
                    sk.value = 0
                sks["Male"].mute = False
                sks["Male"].value = 1
                apply_shapekeys(backup_human)
            backup_human.hide_viewport = False

            for obj in objs:
                obj_copy = obj.copy()
                obj_copy.data = obj_copy.data.copy()
                if "cloth" in obj_copy:
                    del obj_copy["cloth"]
                context.collection.objects.link(obj_copy)
                distance_dict = obj_distance_dict[obj.name]

                if gender != self.hg_rig.HG.gender:
                    name = "Opposite gender"
                    as_sk = True
                else:
                    name = ""
                    as_sk = False

                deform_obj_from_difference(
                    name, distance_dict, backup_human, obj_copy, as_shapekey=as_sk
                )
                human = None  # FIXME
                human.creation_phase.height._correct_origin(context, obj, backup_human)
                export_list.append(obj_copy)

            if gender == "male":
                hg_delete(backup_human)

            gender_folder = self.folder + str(Path(f"/{gender}/Custom"))
            self.save_objects_optimized(
                context,
                export_list,
                gender_folder,
                self.name,
                clear_sk=False,
                clear_materials=False,
                clear_vg=False,
                clear_drivers=False,
                run_in_background=not sett.open_exported_outfits,
            )
        hg_delete(body_copy)

        context.view_layer.objects.active = self.hg_rig
        refresh_pcoll(self, context, "outfit")
        refresh_pcoll(self, context, "footwear")

        show_message(self, "Succesfully exported outfits")
        self.cc_sett.content_saving_ui = False

        return {"FINISHED"}

    # CHECK naming adds .004 to file names, creating duplicates
    def save_material_textures(self, objs):
        """Save the textures used by the materials of these objects to the
        content folder

        Args:
            objs (list): List of objects to check for textures on
        """
        saved_images = {}

        for obj in objs:
            for mat in obj.data.materials:
                nodes = mat.node_tree.nodes
                for img_node in [
                    n for n in nodes if n.bl_idname == "ShaderNodeTexImage"
                ]:
                    self._process_image(saved_images, img_node)

    def _process_image(self, saved_images, img_node):
        """Prepare this image for saving and call _save_img on it

        Args:
            saved_images (dict): Dict to keep record of what images were saved
            img_node (ShaderNode): TexImageShaderNode the image is in
        """
        img = img_node.image
        if not img:
            return
        colorspace = img.colorspace_settings.name
        if not img:
            return
        img_path, saved_images = self._save_img(img, saved_images)
        if img_path:
            new_img = bpy.data.images.load(img_path)
            img_node.image = new_img
            new_img.colorspace_settings.name = colorspace

    def _save_img(self, img, saved_images) -> "tuple[str, list]":
        """Save image to content folder

        Returns:
            tuple[str, dict]:
                str: path the image was saved to
                dict[str: str]:
                    str: name of the image
                    str: path the image was saved to
        """
        img_name = self.remove_number_suffix(img.name)
        if img_name in saved_images:
            return saved_images[img_name], saved_images

        path = self.pref.filepath + str(
            Path(f"{self.cc_sett.saveoutfit_categ}/textures/")
        )
        if not os.path.exists(path):
            os.makedirs(path)

        full_path = os.path.join(path, img_name)
        try:
            shutil.copy(
                bpy.path.abspath(img.filepath_raw),
                os.path.join(path, img_name),
            )
            saved_images[img_name] = full_path
        except RuntimeError as e:
            hg_log(f"failed to save {img.name} with error {e}", level="WARNING")
            self.report(
                {"WARNING"},
                "One or more images failed to save. See the system console for specifics",
            )
            return None, saved_images
        except shutil.SameFileError:
            saved_images[img_name] = full_path
            return full_path, saved_images

        return full_path, saved_images
