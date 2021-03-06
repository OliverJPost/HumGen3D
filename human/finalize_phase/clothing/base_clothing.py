import json
import os
from pathlib import Path
from typing import Tuple

import bpy
from HumGen3D.backend.logging import hg_log
from HumGen3D.backend.memory_management import hg_delete
from HumGen3D.backend.preference_func import get_prefs
from HumGen3D.backend.preview_collections import refresh_pcoll
from HumGen3D.human.base.collections import add_to_collection
from HumGen3D.human.base.shapekey_calculator import (
    build_distance_dict,
    deform_obj_from_difference,
)
from HumGen3D.human.finalize_phase import clothing
from HumGen3D.human.shape_keys.shape_keys import apply_shapekeys

from HumGen3D.human.base.decorators import injected_context


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


class BaseClothing:
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

        cloth_objs, collections = self._import_cloth_items(preset, context)

        new_mask_list = []
        for obj in cloth_objs:
            new_mask_list.extend(find_masks(obj))
            # adds a custom property to the cloth for identifying purposes
            obj[tag] = 1

            self._deform_cloth_to_human(context, obj)

            for mod in obj.modifiers:
                mod.show_expanded = False  # collapse modifiers

            self._set_cloth_corrective_drivers(
                obj, obj.data.shape_keys.key_blocks
            )

        # remove collection that was imported along with the cloth objects
        for col in collections:
            bpy.data.collections.remove(col)

        self._set_geometry_masks(mask_remove_list, new_mask_list)

        # refresh pcoll for consistent 'click here to select' icon
        refresh_pcoll(self, context, "outfit")

    def _deform_cloth_to_human(self, context, cloth_obj):
        """Deforms the cloth object to the shape of the active HumGen human by using
        HG_SHAPEKEY_CALCULATOR

        Args:
            hg_rig (Object): HumGen armature
            hg_body (Object): HumGen body
            obj (Object): cloth object to deform
        """
        backup_rig = self._human.props.backup
        cloth_obj.parent = backup_rig

        backup_rig.HG.body_obj.hide_viewport = False
        backup_body = [obj for obj in backup_rig.children if "hg_body" in obj][
            0
        ]

        backup_body_copy = self._copy_backup_with_gender_sk(backup_body)

        distance_dict = build_distance_dict(
            backup_body_copy, cloth_obj, apply=False
        )

        cloth_obj.parent = self._human.rig_obj

        deform_obj_from_difference(
            "Body Proportions",
            distance_dict,
            self._human.body_obj,
            cloth_obj,
            as_shapekey=True,
        )

        cloth_obj.data.shape_keys.key_blocks["Body Proportions"].value = 1

        context.view_layer.objects.active = cloth_obj
        self._set_armature(context, cloth_obj, self._human.rig_obj)
        context.view_layer.objects.active = self._human.rig_obj

        hg_delete(backup_body_copy)

    def _copy_backup_with_gender_sk(self, backup_body) -> bpy.types.Object:
        """Creates a copy of the backup human with the correct gender settings and
        all other shapekeys set to 0

        Args:
            backup_body (Object): body of the hidden backup human

        Returns:
            bpy.types.Object: copy of the backup body
        """
        copy = backup_body.copy()
        copy.data = backup_body.data.copy()
        bpy.context.scene.collection.objects.link(copy)

        for sk in [
            sk
            for sk in copy.data.shape_keys.key_blocks
            if sk.name not in ["Basis", "Male"]
        ]:
            sk.value = 0

        gender = backup_body.parent.HG.gender

        if gender == "female":
            return copy

        try:
            sk = copy.data.shape_keys.key_blocks
            sk["Male"].value = 1
            apply_shapekeys(copy)
        except:
            pass

        return copy

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
        armature_mods = [
            mod for mod in obj.modifiers if mod.type == "ARMATURE"
        ]

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
                    bpy.ops.object.modifier_move_up(
                        {"object": obj}, modifier=mod.name
                    )
            else:
                bpy.ops.object.modifier_move_to_index(
                    modifier=mod.name, index=0
                )

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

        body_drivers = (
            self._human.body_obj.data.shape_keys.animation_data.drivers
        )

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

    def load_pattern(self, context):
        """
        Loads the pattern that is the current active item in the patterns preview_collection
        """
        pref = get_prefs()
        mat = context.object.active_material

        # finds image node, returns error if for some reason the node doesn't exist
        try:
            img_node = mat.node_tree.nodes["HG_Pattern"]
        except KeyError:
            self.report(
                {"WARNING"},
                "Couldn't find pattern node, click 'Remove pattern' and try to add it again",
            )
            return

        filepath = str(pref.filepath) + str(
            Path(context.scene.HG3D.pcoll_patterns)
        )
        images = bpy.data.images
        pattern = images.load(filepath, check_existing=True)

        img_node.image = pattern

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
                input_socket.name[-2:] if input_socket.name.endswith(color_groups) else None
            )

            if not color_group:
                continue

            context.view_layer.objects.active = cloth_obj

            bpy.ops.hg3d.color_random(
                input_name=input_socket.name, color_group=color_group
            )

        context.view_layer.objects.active = old_active
