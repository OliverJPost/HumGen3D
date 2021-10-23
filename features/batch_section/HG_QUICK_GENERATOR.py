import os
import random
from pathlib import Path

import bpy  # type: ignore
from bpy.props import BoolProperty, EnumProperty, StringProperty  # type:ignore

from ...API.humgen import get_pcoll_options
from ...core.HG_PCOLL import refresh_pcoll
from ...features.creation_phase.HG_FACE import \
    randomize_facial_feature_categ  # type:ignore
from ...features.creation_phase.HG_HAIR import (random_hair_color,
                                                set_hair_quality)
from ...features.creation_phase.HG_MATERIAL import (randomize_iris_color,
                                                    randomize_skin_shader)
from ...features.finalize_phase.HG_CLOTHING import \
    randomize_clothing_colors  # type:ignore
from ...features.finalize_phase.HG_CLOTHING_LOAD import \
    set_clothing_texture_resolution
from ..common.HG_COMMON_FUNC import (apply_shapekeys, hg_delete,
                                     toggle_hair_visibility)
from ..common.HG_RANDOM import random_body_type, set_random_active_in_pcoll
from ..creation_phase.HG_CREATION import HG_CREATION_BASE
from ..creation_phase.HG_FINISH_CREATION_PHASE import finish_creation_phase
from .HG_BATCH_FUNC import length_from_bell_curve


class HG_QUICK_GENERATE(bpy.types.Operator, HG_CREATION_BASE):
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
        items = [
                ("high", "High (~4K)",    "", 0),
                ("optimised", "Optimised (~1K)",       "", 1),
                ("performance", "Performance (~0.5K)",  "", 2),
            ],
        default = "optimised",
        )

    poly_reduction: EnumProperty(
        name="Polygon reduction",   
        items = [
                ("none", "Disabled (original topology)",    "", 0),
                ("medium", "Medium (33% polycount)", "", 1), #0.16 collapse
                ("high", "High (15% polycount)",  "", 2), # 0.08 collapse
                ("ultra", "Ultra (5% polycount)",  "", 3), # 0.025 collapse
            ],
        default = "medium",
        )
    
    apply_poly_reduction: BoolProperty()
    
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

    def execute(self, context):
        sett = context.scene.HG3D

        #### Creation Phase ####

        sett.gender = self.gender
        set_random_active_in_pcoll(context, sett, 'humans', searchterm = self.ethnicity)
        hg_rig, hg_body = self.create_human(context) #inherited
        
        self._give_random_name_to_human(self.gender, hg_rig)
        
        context.view_layer.objects.active = hg_rig
    
        random_body_type(hg_rig)
        randomize_facial_feature_categ(hg_body, 'all', use_bell_curve = self.gender == 'female')
        
        if self.texture_resolution in ('optimised', 'performance'):
            self._set_body_texture_resolution(sett, hg_body) 

        randomize_skin_shader(hg_body, self.gender)
        randomize_iris_color(hg_rig)

        if self.add_hair:
            set_random_active_in_pcoll(context, sett, 'hair')
        set_hair_quality(context, self.hair_type, self.hair_quality)
        random_hair_color(hg_body)

        toggle_hair_visibility(hg_body, show = False)

        sett.human_length = int(length_from_bell_curve(sett, self.gender))

        finish_creation_phase(None, context, hg_rig, hg_body)

        #### Finalize Phase #####
        
        context.view_layer.objects.active = hg_rig

        if self.add_clothing:
            sett.outfit_sub = self.clothing_category
            set_random_active_in_pcoll(context, sett, 'outfit')
            sett.footwear_sub = 'All'
            set_random_active_in_pcoll(context, sett, 'footwear')
            for child in [c for c in hg_rig.children if 'cloth' in c or 'shoe' in c]:
                randomize_clothing_colors(context, child)
                set_clothing_texture_resolution(child, self.texture_resolution)

        if self.pose_type != 'a_pose':
            self._set_pose(context, sett, self.pose_type)

        if self.add_expression:
            sett.expressions_sub = self.expressions_category
            set_random_active_in_pcoll(context, sett, 'expressions')
            expr_sk = next(sk for sk in hg_body.data.shape_keys.key_blocks if sk.name.startswith('expr_'))
            expr_sk.value = random.choice([.5,.7,.8,1,1,1])

        hg_rig.HG.phase = 'clothing' #TODO is this needed? Remove? 
        
        #### Quality settings #####
        
        self._set_quality_settings(context, hg_rig, hg_body)
        
        return {'FINISHED'}

    def _set_quality_settings(self, context, hg_rig, hg_body):
        
        if self.delete_backup:
            self._delete_backup_human(hg_rig)
        
        hg_objects = [hg_rig,]
        hg_objects.extend([obj for obj in hg_rig.children])
        
        if self.apply_shapekeys:
            for obj in [o for o in hg_objects if o.type == 'MESH']:
                apply_shapekeys(obj)  

        #Disconnect hair to prevent it shifting during mesh modification
        context.view_layer.objects.active = hg_body
        toggle_hair_visibility(hg_body, True)
        bpy.ops.particle.disconnect_hair(all=True) 
        toggle_hair_visibility(hg_body, False)
        
        for obj in hg_objects:
            if self.apply_clothing_geometry_masks and self.apply_shapekeys:
                self._apply_modifier_by_type(context, obj, 'MASK')
            if self.remove_clothing_solidify:
                self._remove_modifier_by_type(obj, 'SOLIDIFY')   
            if self.remove_clothing_subdiv:
                self._remove_modifier_by_type(obj, 'SUBSURF')   
            
        if self.apply_armature_modifier and self.apply_shapekeys:
            for obj in hg_objects:
                self._apply_modifier_by_type(context, obj, 'ARMATURE')
                self._remove_redundant_vertex_groups(obj)               
            
        if self.poly_reduction != 'none':
            for obj in hg_objects:
                pr_mod = self._add_poly_reduction_modifier(obj)
                if self.apply_poly_reduction and pr_mod and self.apply_shapekeys:
                    self._apply_modifier(context, obj, pr_mod)      
            
        #Reconnect hair, so it follows the body again
        context.view_layer.objects.active = hg_body
        toggle_hair_visibility(hg_body, True)
        bpy.ops.particle.connect_hair(all=True)     
        toggle_hair_visibility(hg_body, False)

    def _remove_redundant_vertex_groups(self, obj):
        vg_remove_list = [
                    vg for vg in obj.vertex_groups 
                    if not vg.name.lower().startswith(('mask',
                                                       'fh',
                                                       'hair'))
                ]
                
        for vg in vg_remove_list:
            obj.vertex_groups.remove(vg)

    def _set_body_texture_resolution(self, sett, hg_body):
        resolution_tag = '1K' if self.texture_resolution == 'optimised' else '512px'
        sett.texture_library = f'Default {resolution_tag}' 
            
        nodes = hg_body.data.materials[0].node_tree.nodes
        old_image = next(n.image.name for n in nodes if n.name == 'Color')
        pcoll_options = get_pcoll_options('textures')
        searchword = os.path.splitext(old_image)[0].replace('4K', '').replace('MEDIUM', '').replace('LOW', '').replace('1K', '').replace('512px', '').replace('4k', '')
        print(pcoll_options, searchword)
        sett.pcoll_textures = next(p for p in pcoll_options if searchword in p)

    def _apply_modifier(self, context, obj, modifier):
        old_active_obj = context.view_layer.objects.active
        
        obj.select_set(True)
        context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        
        context.view_layer.objects.active = old_active_obj

    def _add_poly_reduction_modifier(self, obj) -> bpy.types.Modifier:
        #TODO optimise polygon reduction, UV layout
        if obj.type != 'MESH':
            print('contuing because not mesh', obj, obj.type)
            return None      
            
        decimate_mod = obj.modifiers.new('HG_POLY_REDUCTION', 'DECIMATE')
            
        # if self.poly_reduction == 'medium':
        #     decimate_mod.decimate_type = 'UNSUBDIV'
        #     decimate_mod.iterations = 2
        decimate_mod.ratio = 0.16 if self.poly_reduction == 'medium' else 0.08 if self.poly_reduction == 'high' else 0.025
        
        return decimate_mod

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
            hg_delete(obj)
            
        hg_delete(backup_rig)

    def _set_pose(self, context, sett, pose_type):
        if pose_type == 't_pose':
            refresh_pcoll(None, context, 'poses')
            sett.pcoll_poses = str(Path('/poses/Base Poses/HG_T_Pose.blend'))
        else:          
            sett.pose_sub = pose_type.capitalize().replace('_', ' ')
            set_random_active_in_pcoll(context, sett, 'poses')
  
    def pick_library(self, context, categ, gender = None):
        sett = context.scene.HG3D

        collection = getattr(context.scene, f'batch_{categ}_col')    
            
        if gender:
            library_list = [
                i for i in collection 
                if i.enabled 
                and getattr(i, f'{gender}_items')
                ]
        else:
            library_list = [
                item.library_name for item in collection 
                if item.count != 0 
                and item.enabled
            ]

        categ_tag = 'outfit' if categ == 'clothing' else categ
        setattr(sett, f'{categ_tag}_sub', random.choice(library_list))



