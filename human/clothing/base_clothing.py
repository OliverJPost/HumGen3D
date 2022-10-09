# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import hashlib
import json
import os
from math import acos, pi
from pathlib import Path
from typing import Tuple

import bpy
import numpy as np
from HumGen3D.backend import get_prefs, hg_delete, hg_log
from HumGen3D.backend.preview_collections import PREVIEW_COLLECTION_DATA
from HumGen3D.human import clothing
from HumGen3D.human.base.collections import add_to_collection
from HumGen3D.human.base.decorators import injected_context
from HumGen3D.human.base.pcoll_content import PreviewCollectionContent
from HumGen3D.human.base.savable_content import SavableContent
from HumGen3D.human.base.shapekey_calculator import (
    build_distance_dict,
    deform_obj_from_difference,
    world_coords_from_obj,
)
from HumGen3D.human.clothing.add_obj_to_clothing import (
    add_corrective_shapekeys,
    auto_weight_paint,
    correct_shape_to_a_pose,
)
from HumGen3D.human.clothing.pattern import PatternSettings
from HumGen3D.human.clothing.saving import save_clothing
from HumGen3D.human.keys.keys import apply_shapekeys


def find_masks(obj) -> list:
    """Looks at the custom properties of the object, searching for custom tags
    that indicate mesh masks added for this cloth.

    Args:
        obj (Object): object to look for masks on

    Retruns:
        mask_list (list): list of str names of masks on this object
    """
    mask_list = []
    for i in range(10):
        try:
            mask_list.append(obj["mask_{}".format(i)])
        except:
            continue
    return mask_list


class BaseClothing(PreviewCollectionContent, SavableContent):
    @property
    def pattern(self) -> PatternSettings:
        return PatternSettings(self._human)

    @injected_context
    def set(self, preset, context=None):
        """Gets called by pcoll_outfit or pcoll_footwear to load the selected outfit

        Args:
            footwear (boolean): True if called by pcoll_footwear, else loads as outfit
        """
        pref = get_prefs()

        self._human.hide_set(False)

        is_footwear = isinstance(self, clothing.footwear.FootwearSettings)

        # returns immediately if the active item in the preview_collection is the
        # 'click here to select' icon
        if preset == "none":
            return

        tag = "shoe" if is_footwear else "cloth"
        # TODO as argument?
        mask_remove_list = self.remove() if pref.remove_clothes else []

        hg_log("Importing cloth item", preset, level="DEBUG")
        cloth_objs, collections = self._import_cloth_items(preset, context)

        new_mask_list = []
        for obj in cloth_objs:
            new_mask_list.extend(find_masks(obj))
            # adds a custom property to the cloth for identifying purposes
            obj[tag] = 1

            self.deform_cloth_to_human(context, obj)

            for mod in obj.modifiers:
                mod.show_expanded = False  # collapse modifiers

            self._set_cloth_corrective_drivers(obj, obj.data.shape_keys.key_blocks)

        # remove collection that was imported along with the cloth objects
        for col in collections:
            bpy.data.collections.remove(col)

        self._set_geometry_masks(mask_remove_list, new_mask_list)

        # refresh pcoll for consistent 'click here to select' icon
        self.refresh_pcoll(context)

        self._human.props.hashes[f"${self._pcoll_name}"] = str(hash(self))

    def add_obj(self, cloth_obj, cloth_type, context):
        body_obj = self._human.body_obj
        correct_shape_to_a_pose(cloth_obj, body_obj, context)
        add_corrective_shapekeys(cloth_obj, self._human, cloth_type)
        auto_weight_paint(cloth_obj, body_obj)

        rig_obj = self._human.rig_obj
        armature_mod = cloth_obj.modifiers.new("Armature", "ARMATURE")
        armature_mod.object = rig_obj
        cloth_obj.parent = rig_obj
        cloth_obj.matrix_parent_inverse = rig_obj.matrix_world.inverted()
        tag = "shoe" if cloth_type == "footwear" else "cloth"
        cloth_obj[tag] = 1

    def deform_cloth_to_human(self, context, cloth_obj):
        """Deforms the cloth object to the shape of the active HumGen human by using
        HG_SHAPEKEY_CALCULATOR

        Args:
            hg_rig (Object): HumGen armature
            hg_body (Object): HumGen body
            obj (Object): cloth object to deform
        """

        body_obj = self._human.body_obj
        if self._human.gender == "female":
            verts = body_obj.data.vertices
        else:
            verts = body_obj.data.shape_keys.key_blocks["Male"].data

        body_coords_world = world_coords_from_obj(body_obj, data=verts)

        cloth_coords_world = world_coords_from_obj(cloth_obj)

        distance_dict = build_distance_dict(body_coords_world, cloth_coords_world)

        cloth_obj.parent = self._human.rig_obj

        body_eval_coords_world = world_coords_from_obj(
            body_obj,
            data=self._human.keys.all_deformation_shapekeys,
        )

        deform_obj_from_difference(
            "Body Proportions",
            distance_dict,
            body_eval_coords_world,
            cloth_obj,
            as_shapekey=True,
        )

        # cloth_obj.data.shape_keys.key_blocks["Body Proportions"].value = 1

        context.view_layer.objects.active = cloth_obj
        self._set_armature(context, cloth_obj, self._human.rig_obj)
        context.view_layer.objects.active = self._human.rig_obj

    def _set_geometry_masks(self, mask_remove_list, new_mask_list):
        """Adds geometry mask modifiers to hg_body based on custom properties on the
        imported clothing

        Args:
            mask_remove_list (list): list of masks to remove from the human, that
                                    were added by previous outfits
            new_mask_list (list): list of masks to add that were not on theh human
                                before
            hg_body (Object): HumGen body to add the modifiers on
        """
        # remove duplicates from mask lists
        mask_remove_list = list(set(mask_remove_list))
        new_mask_list = list(set(new_mask_list))

        # find the overlap between both lists, these will be ignored
        ignore_masks = list(set(mask_remove_list) & set(new_mask_list))
        for mask in ignore_masks:
            mask_remove_list.remove(mask)
            new_mask_list.remove(mask)

        # remove modifiers used by old clothes
        for mask in mask_remove_list:
            try:
                self._human.body_obj.modifiers.remove(
                    self._human.body_obj.modifiers.get(mask)
                )
            except Exception:
                pass

        # add new masks used by new clothes
        for mask in new_mask_list:
            mod = self._human.body_obj.modifiers.new(mask, "MASK")
            mod.vertex_group = mask
            mod.invert_vertex_group = True

    def _set_armature(self, context, obj, hg_rig):
        """Adds an armature modifier to this cloth object

        Args:
            obj (Object): cloth object to add armature to
            hg_rig (Object): HumGen armature
        """
        # checks if the cloth object already has an armature modifier, adds one if it doesnt
        armature_mods = [mod for mod in obj.modifiers if mod.type == "ARMATURE"]

        if not armature_mods:
            armature_mods.append(obj.modifiers.new("Armature", "ARMATURE"))

        armature_mods[0].object = hg_rig
        self._move_armature_to_top(context, obj, armature_mods)

    def _move_armature_to_top(self, context, obj, armature_mods):
        """Moves the armature modifier to the top of the stack

        Args:
            context ([type]): [description]
            obj (Object): object the armature mod is on
            armature_mods (list): list of armature modifiers on this object
        """
        context.view_layer.objects.active = obj
        for mod in armature_mods:
            if (
                2,
                90,
                0,
            ) > bpy.app.version:  # use old method for versions older than 2.90
                while obj.modifiers.find(mod.name) != 0:
                    bpy.ops.object.modifier_move_up({"object": obj}, modifier=mod.name)
            else:
                bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)

    @injected_context
    def _import_cloth_items(
        self,
        preset,
        context=None,
    ) -> Tuple[list, list]:
        """Imports the cloth objects from an external file

        Args:
            context ([type]): [description]
            sett (PropertyGroup): HumGen props
            pref (AddonPreferences): HumGen preferences
            hg_rig (Object): HumGen armature object
            footwear (bool): True if import footwear, False if import clothing

        Returns:
            tuple[list, list]:
                cloth_objs: list with imported clothing objects
                collections: list with imported collections the cloth objs were in
        """
        # load the whole collection from the outfit file. It loads collections
        # instead of objects because this allows loading of linked objects

        blendfile = str(get_prefs().filepath) + str(Path(preset))
        with bpy.data.libraries.load(blendfile, link=False) as (
            data_from,
            data_to,
        ):
            data_to.collections = data_from.collections
            data_to.texts = data_from.texts

        # appends all collections and objects to scene
        collections = data_to.collections

        cloth_objs = []
        for col in collections:
            context.scene.collection.children.link(col)
            for obj in col.objects:
                cloth_objs.append(obj)

        for obj in context.selected_objects:
            obj.select_set(False)

        # loads cloth objects in the humgen collection and sets the rig as their
        # parent. This also makes sure their rotation and location is correct
        for obj in cloth_objs:
            add_to_collection(context, obj)
            obj.location = (0, 0, 0)
            obj.parent = self._human.rig_obj
            obj.select_set(True)

        # makes linked objects/textures/nodes local
        bpy.ops.object.make_local(type="SELECT_OBDATA_MATERIAL")
        bpy.ops.object.make_local(type="ALL")

        return cloth_objs, collections

    def remove(self) -> list:
        """Removes the cloth objects that were already on the human

        Args:
            pref (AddonPreferences): preferences of HumGen
            hg_rig (Object): HumGen armature
            tag (str): tag for identifying cloth and shoe objects

        Returns:
            list: list of geometry masks that need to be removed
        """
        # removes previous outfit/shoes if the preferences option is True
        mask_remove_list = []

        for obj in self.objects:
            mask_remove_list.extend(find_masks(obj))
            hg_delete(obj)

        return mask_remove_list

    def _set_cloth_corrective_drivers(self, hg_cloth, sk):
        """Sets up the drivers of the corrective shapekeys on the clothes

        Args:
            hg_body (Object): HumGen body object
            sk (list): List of cloth object shapekeys #CHECK
        """
        try:
            for driver in hg_cloth.data.shape_keys.animation_data.drivers[:]:
                hg_cloth.data.shape_keys.animation_data.drivers.remove(driver)
        except AttributeError:
            pass

        body_drivers = self._human.body_obj.data.shape_keys.animation_data.drivers

        for driver in body_drivers:
            target_sk = driver.data_path.replace('key_blocks["', "").replace(
                '"].value', ""
            )  # TODO this is horrible

            if target_sk not in [shapekey.name for shapekey in sk]:
                continue

            new_driver = sk[target_sk].driver_add("value")
            new_var = new_driver.driver.variables.new()
            new_var.type = "TRANSFORMS"
            new_target = new_var.targets[0]
            old_var = driver.driver.variables[0]
            old_target = old_var.targets[0]
            new_target.id = self._human.rig_obj

            new_driver.driver.expression = driver.driver.expression
            new_target.bone_target = old_target.bone_target
            new_target.transform_type = old_target.transform_type
            new_target.transform_space = old_target.transform_space

    # TODO item independent
    def set_texture_resolution(self, clothing_item, resolution_category):
        if resolution_category == "performance":
            resolution_tag = "low"
        elif resolution_category == "optimised":
            resolution_tag = "medium"

        mat = clothing_item.data.materials[0]
        nodes = mat.node_tree.nodes

        for node in [n for n in nodes if n.bl_idname == "ShaderNodeTexImage"]:
            image = node.image

            if not image:
                continue

            old_color_setting = image.colorspace_settings.name

            img_dir = os.path.dirname(image.filepath)
            filename, ext = os.path.splitext(os.path.basename(image.filepath))

            if filename.endswith("_MEDIUM"):
                filename = filename[:-7]
            elif filename.endswith("_LOW"):
                filename = filename[:-4]

            if resolution_category == "high":
                new_filename = filename + ext
            else:
                new_filename = filename + f"_{resolution_tag.upper()}" + ext

            new_path = os.path.join(img_dir, new_filename)

            if not os.path.isfile(new_path):
                hg_log(
                    "Could not find other resolution for outfit texture: ",
                    new_path,
                    level="WARNING",
                )
                return

            new_image = bpy.data.images.load(new_path, check_existing=True)
            node.image = new_image
            new_image.colorspace_settings.name = old_color_setting

    @injected_context
    def randomize_colors(self, cloth_obj, context=None):
        mat = cloth_obj.data.materials[0]
        if not mat:
            return
        nodes = mat.node_tree.nodes

        control_node = nodes.get("HG_Control")
        if not control_node:
            hg_log(
                f"Could not set random color for {cloth_obj.name}, control node not found",
                level="WARNING",
            )
            return

        # TODO Rewrite color_random so it doesn't need to be called as operator
        old_active = context.view_layer.objects.active

        colorgroups_json = "colorgroups.json"

        with open(colorgroups_json) as f:
            color_dict = json.load(f)

        for input_socket in control_node.inputs:
            color_groups = tuple(["_{}".format(name) for name in color_dict])
            color_group = (
                input_socket.name[-2:]
                if input_socket.name.endswith(color_groups)
                else None
            )

            if not color_group:
                continue

            context.view_layer.objects.active = cloth_obj

            bpy.ops.hg3d.color_random(
                input_name=input_socket.name, color_group=color_group
            )

        context.view_layer.objects.active = old_active

    @injected_context
    def _calc_percentage_clipping_vertices(self, context=None) -> float:
        body_obj = self._human.body_obj
        for modifier in body_obj.modifiers:
            if modifier.type != "ARMATURE":
                modifier.show_viewport = False

        depsgraph = context.evaluated_depsgraph_get()
        body_eval = body_obj.evaluated_get(depsgraph)

        def calc_if_inside(target_pt_global, mesh_obj, tolerance=0.02):

            # Convert the point from global space to mesh local space
            target_pt_local = mesh_obj.matrix_world.inverted() @ target_pt_global
            # Find the nearest point on the mesh and the nearest face normal
            _, pt_closest, face_normal, _ = mesh_obj.closest_point_on_mesh(
                target_pt_local
            )
            # Get the target-closest pt vector
            target_closest_pt_vec = (pt_closest - target_pt_local).normalized()
            # Compute the dot product = |a||b|*cos(angle)
            dot_prod = target_closest_pt_vec.dot(face_normal)
            # Get the angle between the normal and the target-closest-pt vector (from the dot prod)
            angle = acos(min(max(dot_prod, -1), 1)) * 180 / pi
            # Allow for some rounding error
            inside = angle < 90 - tolerance

            return inside

        is_inside_list = []
        for obj in self.objects:
            obj_eval = obj.evaluated_get(depsgraph)
            mx_obj = obj.matrix_world
            for vert in obj_eval.data.vertices:
                vert_global = mx_obj @ vert.co
                is_inside = calc_if_inside(vert_global, body_eval)
                is_inside_list.append(is_inside)

        return is_inside_list.count(True) / len(is_inside_list)

    def __hash__(self):
        hash_coll = []
        for obj in self.objects:
            vert_count = len(obj.data.vertices)
            vert_co = np.empty(vert_count * 3, dtype=np.float64)
            obj.data.vertices.foreach_get("co", vert_co)

            hash_coll.append(hashlib.sha1(vert_co).hexdigest())

            for sk in obj.data.shape_keys.key_blocks:
                sk_co = np.empty(vert_count * 3, dtype=np.float64)
                sk.data.foreach_get("co", sk_co)
                hash_coll.append(hashlib.sha1(sk_co).hexdigest())

            mat = obj.active_material
            if mat:
                node_names = []
                # TODO check effect of pattern loading
                for node in mat.node_tree.nodes:
                    node_names.append(node.name)
                hash_coll.append(hash(tuple(node_names)))

        return hash(tuple(hash_coll))

    @injected_context
    def save_to_library(
        self,
        name,
        for_male=True,
        for_female=True,
        open_when_finished=False,
        category="Custom",
        thumbnail=None,
        context=None,
    ):
        genders = []
        if for_male:
            genders.append("male")
        if for_female:
            genders.append("female")

        pcoll_subfolder = PREVIEW_COLLECTION_DATA[self._pcoll_name][2]
        folder = os.path.join(get_prefs().filepath, pcoll_subfolder)

        save_clothing(
            self._human,
            folder,
            category,
            name,
            context,
            self.objects,
            genders,
            open_when_finished,
            thumbnail=thumbnail,
        )
