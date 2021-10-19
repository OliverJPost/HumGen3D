from ... features.finalize_phase.HG_CLOTHING_LOAD import set_clothing_texture_resolution
from ... features.creation_phase.HG_HAIR import set_hair_quality
from ... modules.humgen import get_pcoll_options
from ... core.HG_PCOLL import refresh_pcoll
import os
import bpy #type: ignore
import time
from pathlib import Path

from bpy.props import IntProperty, StringProperty, FloatProperty, BoolProperty, EnumProperty #type:ignore

from .. creation_phase.HG_CREATION import (HG_CREATION_BASE)
from .. common.HG_RANDOM import (
    set_random_active_in_pcoll,
    random_body_type,
)
from .. creation_phase.HG_FINISH_CREATION_PHASE import (
    finish_creation_phase
)
from .. common.HG_COMMON_FUNC import apply_shapekeys, hg_delete, time_update
from . HG_BATCH_FUNC import length_from_bell_curve


class HG_QUICK_GENERATE(bpy.types.Operator, HG_CREATION_BASE):
    """
    clears searchfield INACTIVE
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
                ("medium", "Medium (33% polycount)", "", 1), #2x unsubdivide
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

        sett.gender = self.gender
        set_random_active_in_pcoll(context, sett, 'humans', searchterm = self.ethnicity)
        #ethnicity
        hg_rig, hg_body = self.create_human(context) #inherited
        

        context.view_layer.objects.active = hg_rig
        name = self._get_random_name(self.gender, hg_rig) #inherited        
        
        random_body_type(hg_rig)
        


        if self.texture_resolution in ('optimised', 'performance'):
            resolution_tag = '1K' if self.texture_resolution == 'optimised' else '512px'
            sett.texture_library = f'Default {resolution_tag}' 
            
            nodes = hg_body.data.materials[0].node_tree.nodes
            old_image = next(n.image.name for n in nodes if n.name == 'Color')
            pcoll_options = get_pcoll_options('textures')
            searchword = os.path.splitext(old_image)[0].replace('4K', '').replace('MEDIUM', '').replace('LOW', '').replace('1K', '').replace('512px', '').replace('4k', '')
            print(pcoll_options, searchword)
            sett.pcoll_textures = next(p for p in pcoll_options if searchword in p) 

        if self.add_hair:
            set_random_active_in_pcoll(context, sett, 'hair')
        set_hair_quality(context, self.hair_type, self.hair_quality)

        toggle_hair_visibility(hg_body, show = False)

        sett.human_length = int(length_from_bell_curve(sett, self.gender))


        finish_creation_phase(None, context, hg_rig, hg_body)

        
        context.view_layer.objects.active = hg_rig

        if self.add_clothing:
            set_random_active_in_pcoll(context, sett, 'outfit')

            for child in [c for c in hg_rig.children if 'cloth' in c or 'shoe' in c]:
                set_clothing_texture_resolution(child, self.texture_resolution)

        if self.pose_type != 'a_pose':
            self._set_pose(context, sett, self.pose_type)

        if self.add_expression:
            #pick_library(context, 'expressions')
            set_random_active_in_pcoll(context, sett, 'expressions')

        hg_rig.HG.phase = 'clothing'  
        
        if self.delete_backup:
            self._delete_backup_human(hg_rig)
        
        hg_objects = [hg_rig,]
        hg_objects.extend([obj for obj in hg_rig.children])
        
        if self.apply_shapekeys:
            for obj in hg_objects:
                if obj.type != 'MESH':
                    continue
                apply_shapekeys(obj)  

        context.view_layer.objects.active = hg_body
        toggle_hair_visibility(hg_body, True)
        bpy.ops.particle.disconnect_hair(all=True) 
        toggle_hair_visibility(hg_body, False)
        for obj in hg_objects:
            if self.apply_clothing_geometry_masks and self.apply_shapekeys:
                self._apply_modifier_by_type(context, obj, 'MASK')
                #for vg in [vg for vg in obj.vertex_groups if vg.name.startswith('mask')]:
                #    obj.vertex_groups.remove(vg)
            if self.remove_clothing_solidify:
                self._remove_modifier_by_type(obj, 'SOLIDIFY')   
            if self.remove_clothing_subdiv:
                self._remove_modifier_by_type(obj, 'SUBSURF')   
            
        if self.apply_armature_modifier and self.apply_shapekeys:
            for obj in hg_objects:
                self._apply_modifier_by_type(context, obj, 'ARMATURE')
                for vg in [vg for vg in obj.vertex_groups if not vg.name.lower().startswith(('mask', 'fh', 'hair'))]:
                    obj.vertex_groups.remove(vg)               
            
        if self.poly_reduction != 'none':
            for obj in hg_objects:
                pr_mod = self._add_poly_reduction_modifier(obj)
                if self.apply_poly_reduction and pr_mod and self.apply_shapekeys:
                    self._apply_modifier(context, obj, pr_mod)      
            
        context.view_layer.objects.active = hg_body
        toggle_hair_visibility(hg_body, True)
        bpy.ops.particle.connect_hair(all=True)     
        toggle_hair_visibility(hg_body, False)
        return {'FINISHED'}

    def _apply_modifier(self, context, obj, modifier):
        old_active_obj = context.view_layer.objects.active
        
        obj.select_set(True)
        context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        
        context.view_layer.objects.active = old_active_obj

    def _add_poly_reduction_modifier(self, obj) -> bpy.types.Modifier:
        
        if obj.type != 'MESH':
            print('contuing because not mesh', obj, obj.type)
            return None      
            
        decimate_mod = obj.modifiers.new('HG_POLY_REDUCTION', 'DECIMATE')
            
        # if self.poly_reduction == 'medium':
        #     decimate_mod.decimate_type = 'UNSUBDIV'
        #     decimate_mod.iterations = 2
            
        # else:
        
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
  

def toggle_hair_visibility(obj, show = True):
    for mod in obj.modifiers:
        print('modcheck', mod.name, mod.type)
        if mod.type == 'PARTICLE_SYSTEM':
            mod.show_viewport = show