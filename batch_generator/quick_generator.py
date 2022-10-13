# type:ignore
# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import os
import random
from pathlib import Path

import bpy  # type: ignore
from bpy.props import BoolProperty, EnumProperty, StringProperty  # type:ignore
from HumGen3D.backend import hg_delete, hg_log, preview_collections
from HumGen3D.human.human import Human
from HumGen3D.human.keys.keys import apply_shapekeys

from .batch_functions import height_from_bell_curve

set_random_active_in_pcoll = None  # FIXME


class HG_QUICK_GENERATE(bpy.types.Operator):
    """Operator to create a human from start to finish in one go. Includes
    properties to determine the quality of the human, as well as properties that
    determine what the human should look like, wear, expression etc.

    Args:
        HG_CREATION_BASE (bpy.types.Operator): For inheriting the methods for
        creating a new human
    """

    bl_idname = "hg3d.quick_generate"
    bl_label = "Quick Generate"
    bl_description = "Generates a full human from a list of arguments"
    bl_options = {"REGISTER", "UNDO"}

    delete_backup: BoolProperty()
    apply_shapekeys: BoolProperty()
    apply_armature_modifier: BoolProperty()
    remove_clothing_subdiv: BoolProperty()
    remove_clothing_solidify: BoolProperty()
    apply_clothing_geometry_masks: BoolProperty()

    texture_resolution: EnumProperty(
        name="Texture Resolution",
        items=[
            ("high", "High (~4K)", "", 0),
            ("optimised", "Optimised (~1K)", "", 1),
            ("performance", "Performance (~0.5K)", "", 2),
        ],
        default="optimised",
    )

    # poly_reduction: EnumProperty(
    #     name="Polygon reduction",
    #     items = [
    #             ("none", "Disabled (original topology)",    "", 0),
    #             ("medium", "Medium (33% polycount)", "", 1), #0.16 collapse
    #             ("high", "High (15% polycount)",  "", 2), # 0.08 collapse
    #             ("ultra", "Ultra (5% polycount)",  "", 3), # 0.025 collapse
    #         ],
    #     default = "medium",
    #     )

    # apply_poly_reduction: BoolProperty()

    gender: StringProperty()

    ethnicity: StringProperty()

    add_hair: BoolProperty()
    hair_type: StringProperty()
    hair_quality: StringProperty()

    add_clothing: BoolProperty()
    clothing_category: StringProperty()

    add_expression: BoolProperty()
    expression_category: StringProperty()

    pose_type: StringProperty()

    def execute(self, context):
        sett = context.scene.HG3D  # type:ignore[attr-defined]

        presets = Human.get_preset_options(self.gender)
        chosen_preset = random.choice(presets)
        human = Human.from_preset(chosen_preset)

        human.body.randomize()
        human.face.randomize(use_bell_curve=self.gender == "female")

        # if self.texture_resolution in ("optimised", "performance"):
        #    self._set_body_texture_resolution(sett, human.body_obj)

        human.skin.randomize()
        human.eyes.randomize()

        if self.add_hair:
            human.hair.regular_hair.randomize(context)
            if human.gender == "male":
                human.hair.face_hair.randomize(context)
                human.hair.face_hair.randomize_color()

        human.hair.set_hair_quality(
            self.hair_quality,
        )
        human.hair.regular_hair.randomize_color()

        human.hair.eyebrows.randomize_color()

        human.hair.children_set_hide(True)

        human.height.set(int(height_from_bell_curve(sett.batch, self.gender)[0]))

        if self.add_clothing:
            try:
                sett.pcoll.outfit_category = self.clothing_category
            except TypeError:
                hg_log(
                    f'Reverting to "All" outfit category, because \
                    {self.clothing_category} could not be resolved.',
                    level="WARNING",
                )
                sett.pcoll.outfit_category = "All"

            human.outfit.set_random(context)
            sett.pcoll.footwear_cateogry = "All"
            human.footwear.set_random(context)

            for cloth in human.outfit.objects:
                human.outfit.randomize_colors(cloth)
                human.outfit.set_texture_resolution(cloth, self.texture_resolution)

            for cloth in human.footwear.objects:
                human.footwear.randomize_colors(cloth)
                human.footwear.set_texture_resolution(cloth, self.texture_resolution)

        if self.pose_type != "a_pose":
            self._set_pose(human, context, sett, self.pose_type)

        if self.add_expression:
            human.expression.set_random(context)
            human.expression.shape_keys[0].value = random.choice(
                [0.5, 0.7, 0.8, 1, 1, 1]
            )

        # Quality settings

        hg_rig = human.rig_obj
        hg_body = human.body_obj

        self._set_quality_settings(context, hg_rig, hg_body)

        if self.apply_armature_modifier:
            self._make_body_obj_main_object(hg_rig, hg_body)
        else:
            hg_rig.HG.batch_result = True

        return {"FINISHED"}

    def _make_body_obj_main_object(self, hg_rig, hg_body):
        hg_body.HG.batch_result = True
        hg_body.HG.ishuman = True
        hg_body.HG.body_obj = hg_body
        hg_rig_name = hg_rig.name
        for child in hg_rig.children:
            if child == hg_body:
                continue
            child.parent = hg_body
            child.matrix_parent_inverse = hg_body.matrix_world.inverted()
        hg_delete(hg_rig)
        hg_body.name = hg_rig_name

    def _set_quality_settings(self, context, hg_rig, hg_body):

        if self.delete_backup:
            self._delete_backup_human(hg_rig)
        human = Human.from_existing(hg_rig)
        hg_objects = [
            hg_rig,
        ]
        hg_objects.extend(list(hg_rig.children))

        if self.apply_shapekeys:
            for obj in [o for o in hg_objects if o.type == "MESH"]:
                apply_shapekeys(obj)

        # Disconnect hair to prevent it shifting during mesh modification
        context.view_layer.objects.active = hg_body
        human.hair.children_set_hide(False)
        bpy.ops.particle.disconnect_hair(all=True)
        human.hair.children_set_hide(True)

        for obj in hg_objects:
            if self.apply_clothing_geometry_masks and self.apply_shapekeys:
                self._apply_modifier_by_type(context, obj, "MASK")
            if self.remove_clothing_solidify:
                self._remove_modifier_by_type(obj, "SOLIDIFY")
            if self.remove_clothing_subdiv:
                self._remove_modifier_by_type(obj, "SUBSURF")

        if self.apply_armature_modifier and self.apply_shapekeys:
            for obj in hg_objects:
                self._apply_modifier_by_type(context, obj, "ARMATURE")
                self._remove_redundant_vertex_groups(obj)

        # if self.poly_reduction != 'none':
        #     for obj in hg_objects:
        #         pr_mod = self._add_poly_reduction_modifier(obj)
        #         if self.apply_poly_reduction and pr_mod and self.apply_shapekeys:
        #             self._apply_modifier(context, obj, pr_mod)

        # Reconnect hair, so it follows the body again
        context.view_layer.objects.active = hg_body
        human.hair.children_set_hide(False)
        bpy.ops.particle.connect_hair(all=True)
        human.hair.children_set_hide(True)

    def _remove_redundant_vertex_groups(self, obj):
        vg_remove_list = [
            vg
            for vg in obj.vertex_groups
            if not vg.name.lower().startswith(("mask", "fh", "hair"))
        ]

        for vg in vg_remove_list:
            obj.vertex_groups.remove(vg)

    def _set_body_texture_resolution(self, sett, hg_body):
        resolution_tag = "1K" if self.texture_resolution == "optimised" else "512px"
        sett.texture_category = f"Default {resolution_tag}"

        nodes = hg_body.data.materials[0].node_tree.nodes
        old_image = next(n.image.name for n in nodes if n.name == "Color")
        pcoll_options = sett["previews_list_textures"]
        searchword = (  # FIXME
            os.path.splitext(old_image)[0]
            .replace("4K", "")
            .replace("MEDIUM", "")
            .replace("LOW", "")
            .replace("1K", "")
            .replace("512px", "")
            .replace("4k", "")
        )
        sett.pcoll_textures = next(p for p in pcoll_options if searchword in p)

    def _apply_modifier(self, context, obj, modifier):
        old_active_obj = context.view_layer.objects.active

        obj.select_set(True)
        context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)

        context.view_layer.objects.active = old_active_obj

    def _remove_modifier_by_type(self, obj, mod_type):
        for modifier in [m for m in obj.modifiers if m.type == mod_type]:
            obj.modifiers.remove(modifier)

    def _apply_modifier_by_type(self, context, obj, mod_type):
        for modifier in [m for m in obj.modifiers if m.type == mod_type]:
            self._apply_modifier(context, obj, modifier)

    def _delete_backup_human(self, hg_rig):
        backup_rig = hg_rig.HG.backup
        backup_children = list(backup_rig.children)

        for obj in backup_children:
            hg_log("Deleted", obj.name)
            hg_delete(obj)

        hg_log("Deleted", backup_rig.name)
        hg_delete(backup_rig)

    def _set_pose(self, human: Human, context, sett, pose_type):
        if pose_type == "t_pose":
            human.pose.set(os.path.join("poses", "Base Poses", "HG_T_Pose.blend"))
        else:
            sett.pose_category = pose_type.capitalize().replace("_", " ")
            options = human.pose.get_options(context)
            human.pose.set(random.choice(options))

    def pick_library(self, context, categ, gender=None):
        sett = context.scene.HG3D  # type:ignore[attr-defined]
        collection = getattr(context.scene, f"batch_{categ}_col")

        if gender:
            library_list = [
                i for i in collection if i.enabled and getattr(i, f"{gender}_items")
            ]
        else:
            library_list = [
                item.library_name
                for item in collection
                if item.count != 0 and item.enabled
            ]

        categ_tag = "outfit" if categ == "clothing" else categ
        setattr(sett.pcoll, f"{categ_tag}_category", random.choice(library_list))
