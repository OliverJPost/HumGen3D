import os
import random
from pathlib import Path

import bpy  # type: ignore
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from HumGen3D.backend.logging import hg_log
from HumGen3D.backend.memory_management import hg_delete
from HumGen3D.backend.preview_collections import (
    refresh_pcoll,
    set_random_active_in_pcoll,
)
from HumGen3D.human.human import Human
from HumGen3D.human.shape_keys.shape_keys import apply_shapekeys

# from ..utility_section.baking import (  # type:ignore
#     add_image_node,
#     bake_texture,
#     check_bake_render_settings,
#     generate_bake_enum,
#     get_solidify_state,
#     material_setup,
# )
from .batch_functions import length_from_bell_curve


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
    expressions_category: StringProperty()

    pose_type: StringProperty()

    # bake_textures: BoolProperty()
    # bake_samples: IntProperty()
    # bake_extension: StringProperty()
    # body_resolution: IntProperty()
    # eyes_resolution: IntProperty()
    # mouth_resolution: IntProperty()
    # clothing_resolution: IntProperty()
    # bake_export_folder: StringProperty()

    def execute(self, context):
        sett = context.scene.HG3D

        #### Creation Phase ####

        presets = Human.get_preset_options(self.gender)
        chosen_preset = random.choice(presets)
        human = Human.from_preset(chosen_preset)

        human.creation_phase.body.randomize()
        human.creation_phase.face.randomize(
            use_bell_curve=self.gender == "female"
        )

        if self.texture_resolution in ("optimised", "performance"):
            self._set_body_texture_resolution(sett, human.body_obj)

        human.skin.randomize()
        human.eyes.randomize()

        if self.add_hair:
            human.hair.regular_hair.randomize(context)
            if self.gender == "male":
                human.hair.facial_hair.randomize(context)

        human.hair.set_hair_quality(self.hair_quality, context)
        human.hair.regular_hair.randomize_color()
        human.hair.facial_hair.randomize_color()
        human.hair.eyebrows.randomize_color()

        human.hair.children_set_hide(True)

        sett.human_length = int(length_from_bell_curve(sett, self.gender))

        human.creation_phase.finish(context)

        #### Finalize Phase #####

        if self.add_clothing:
            try:
                sett.outfit_sub = self.clothing_category
            except TypeError:
                hg_log(
                    f'Reverting to "All" outfit category, because \
                    {self.clothing_category} could not be resolved.',
                    level="WARNING",
                )
                sett.outfit_sub = "All"

            set_random_active_in_pcoll(context, sett, "outfit")
            sett.footwear_sub = "All"
            set_random_active_in_pcoll(context, sett, "footwear")
            # FIXME
            # for cloth in human.finalize_phase.outfit.obj_settings:
            #     cloth.randomize_colors(context)
            #     cloth.set_texture_resolution(self.texture_resolution)

            # for cloth in human.finalize_phase.footwear.obj_settings:
            #     cloth.randomize_colors(context)
            #     cloth.set_texture_resolution(self.texture_resolution)

        if self.pose_type != "a_pose":
            self._set_pose(context, sett, self.pose_type)

        if self.add_expression:
            # TODO implement in OOP
            sett.expressions_sub = self.expressions_category
            set_random_active_in_pcoll(context, sett, "expressions")
            expr_sk = next(
                (sk for sk in human.shape_keys if sk.name.startswith("expr_")),
                None,
            )
            if expr_sk:
                expr_sk.value = random.choice([0.5, 0.7, 0.8, 1, 1, 1])

        human.props.phase = "clothing"  # TODO is this needed? Remove?

        # if self.bake_textures:
        #     self._bake_all_textures(context, hg_rig)

        #### Quality settings #####

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

    # def _bake_all_textures(self, context, hg_rig):
    #     check_bake_render_settings(context, self.bake_samples, force_cycles=True)
    #     bake_enum = generate_bake_enum(context, [hg_rig,])
    #     hg_log("Bake enum", bake_enum)

    #     image_dict = {}

    #     for idx, sett_dict in enumerate(bake_enum):
    #         human_name, texture_name, bake_obj, mat_slot, tex_type = sett_dict.values()

    #         bake_obj.select_set(True)
    #         context.view_layer.objects.active = bake_obj

    #         solidify_state = get_solidify_state(bake_obj, False)
    #         current_mat = bake_obj.data.materials[mat_slot]

    #         img_name = f'{human_name}_{texture_name}_{tex_type}'

    #         #TODO  teeth
    #         if texture_name == 'body':
    #             resolution = self.body_resolution
    #         elif texture_name == 'eyes':
    #             resolution = self.eyes_resolution
    #         else:
    #             resolution = self.clothing_resolution

    #         hg_rig.select_set(False)
    #         img = bake_texture(context, current_mat, tex_type, img_name, self.bake_extension, resolution, self.bake_export_folder)

    #         assert img

    #         image_dict[img] = tex_type

    #         #check if next texture belongs to another object
    #         try:
    #             last_texture = True if bake_enum[idx+1]["texture_name"] != texture_name else False
    #         except IndexError:
    #             last_texture = True

    #         if last_texture:
    #             new_mat = material_setup(bake_obj, mat_slot)
    #             for img,tex_type in image_dict.items():
    #                 add_image_node(img, tex_type, new_mat)
    #             image_dict.clear()

    #         get_solidify_state(bake_obj, solidify_state)
    #         hg_rig = bpy.data.objects.get(human_name)
    #         hg_rig['hg_baked'] = 1

    def _set_quality_settings(self, context, hg_rig, hg_body):

        if self.delete_backup:
            self._delete_backup_human(hg_rig)
        human = Human.from_existing(hg_rig)
        hg_objects = [
            hg_rig,
        ]
        hg_objects.extend([obj for obj in hg_rig.children])

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
        resolution_tag = (
            "1K" if self.texture_resolution == "optimised" else "512px"
        )
        sett.texture_library = f"Default {resolution_tag}"

        nodes = hg_body.data.materials[0].node_tree.nodes
        old_image = next(n.image.name for n in nodes if n.name == "Color")
        pcoll_options = sett["previews_list_textures"]
        searchword = (
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

    # def _add_poly_reduction_modifier(self, obj) -> bpy.types.Modifier:
    #     #TODO optimise polygon reduction, UV layout
    #     if obj.type != 'MESH':
    #         return None

    #     decimate_mod = obj.modifiers.new('HG_POLY_REDUCTION', 'DECIMATE')

    #     # if self.poly_reduction == 'medium':
    #     #     decimate_mod.decimate_type = 'UNSUBDIV'
    #     #     decimate_mod.iterations = 2
    #     decimate_mod.ratio = 0.16 if self.poly_reduction == 'medium' else 0.08 if self.poly_reduction == 'high' else 0.025

    #     return decimate_mod

    def _remove_modifier_by_type(self, obj, mod_type):
        for modifier in [m for m in obj.modifiers if m.type == mod_type]:
            obj.modifiers.remove(modifier)

    def _apply_modifier_by_type(self, context, obj, mod_type):
        for modifier in [m for m in obj.modifiers if m.type == mod_type]:
            self._apply_modifier(context, obj, modifier)

    def _delete_backup_human(self, hg_rig):
        backup_rig = hg_rig.HG.backup
        backup_children = [obj for obj in backup_rig.children]

        for obj in backup_children:
            hg_log("Deleted", obj.name)
            hg_delete(obj)

        hg_log("Deleted", backup_rig.name)
        hg_delete(backup_rig)

    def _set_pose(self, context, sett, pose_type):
        if pose_type == "t_pose":
            refresh_pcoll(None, context, "poses")
            sett.pcoll_poses = str(Path("/poses/Base Poses/HG_T_Pose.blend"))
        else:
            sett.pose_sub = pose_type.capitalize().replace("_", " ")
            set_random_active_in_pcoll(context, sett, "poses")

    def pick_library(self, context, categ, gender=None):
        sett = context.scene.HG3D

        collection = getattr(context.scene, f"batch_{categ}_col")

        if gender:
            library_list = [
                i
                for i in collection
                if i.enabled and getattr(i, f"{gender}_items")
            ]
        else:
            library_list = [
                item.library_name
                for item in collection
                if item.count != 0 and item.enabled
            ]

        categ_tag = "outfit" if categ == "clothing" else categ
        setattr(sett, f"{categ_tag}_sub", random.choice(library_list))
