'''
Inactive file to be implemented later, batch mode for generating multiple 
humans at once
'''

import json
import os
import random
import subprocess
import time
from pathlib import Path

import bpy

from ...API import HG_Batch_Generator, HG_Human
from ...features.batch_section.HG_BATCH_FUNC import (get_batch_marker_list,
                                                     has_associated_human)
from ...features.batch_section.HG_QUICK_GENERATOR import toggle_hair_visibility
from ...features.utility_section.HG_BAKE import \
    get_bake_export_path  # type:ignore
from ...user_interface.HG_BATCH_UILIST import batch_uilist_refresh
from ..common.HG_COMMON_FUNC import get_prefs, hg_delete, hg_log, show_message
from ..creation_phase.HG_CREATION import (HG_CREATION_BASE,
                                          set_eevee_ao_and_strip)


def status_text_callback(header, context):  
    sett   = context.scene.HG3D
    layout = header.layout

    layout.separator_spacer()
    layout.alignment = 'EXPAND'
    
    row = layout.row(align=False)
    row.alignment = 'CENTER'
    
    layout.label(text=f'Building Human {sett.batch_idx}', icon='TIME')
    
    col         = layout.column()
    col.scale_x = 1.6
    col.prop(sett, "batch_progress")

    layout.label(text='Press ESC to cancel', icon='EVENT_ESC')
    
    layout.separator_spacer()
    
class HG_BATCH_GENERATE(bpy.types.Operator, HG_CREATION_BASE):
    """
    clears searchfield INACTIVE
    """
    bl_idname = "hg3d.generate"
    bl_label = "Generate"
    bl_description = "Generates specified amount of humans"
    bl_options = {"REGISTER", "UNDO"}

    run_immediately: bpy.props.BoolProperty(default = False)

    def __init__(self):
        self.human_idx = 0
        self.generate_queue = get_batch_marker_list(bpy.context)
        self.finish_modal = False
        self.timer = None
        self.start_time = time.time()

    def invoke(self, context, event):
        sett = context.scene.HG3D
        
        markers_with_associated_human = list(filter(has_associated_human, self.generate_queue))
          
        if self.run_immediately or not markers_with_associated_human:
            self._initiate_modal(context, sett)
            set_eevee_ao_and_strip(context)
            
            return {'RUNNING_MODAL'}
        else:
            self._show_dialog_to_confirm_deleting_humans(context)
            return {'CANCELLED'}

    def _initiate_modal(self, context, sett):
        wm = context.window_manager
        wm.modal_handler_add(self)

        sett.batch_progress = 0

        self.human_idx = 0
        self.timer = wm.event_timer_add(0.01, window =context.window)

        sett.batch_idx = 1
        context.workspace.status_text_set(status_text_callback)
        context.area.tag_redraw()

    def _show_dialog_to_confirm_deleting_humans(self, context):
        generate_queue = self.generate_queue
            
        def draw(self, context):
            layout = self.layout
                
            nonlocal generate_queue
                
            i = 0
            for marker in filter(has_associated_human, generate_queue):
                layout.label(text = marker['associated_human'].name)
                i += 1
                    
                if i > 9:
                    layout.label(text = f'+ {len(generate_queue) - 10} more')
                    break
                    
            layout.separator()
                
            layout.operator_context = 'INVOKE_DEFAULT'    
            layout.operator("hg3d.generate", text="Generate anyway").run_immediately = True
            return 

        context.window_manager.popup_menu(draw, title="This will delete these humans:")

    def modal(self, context, event):
        """ Event handling. """
        
        sett = context.scene.HG3D      

        if self.finish_modal:
            context.area.tag_redraw()
            context.workspace.status_text_set(text=None)

            sett.batch_idx = 0
            
            hg_log('Batch modal total running time: ', 
                   round(time.time()-self.start_time, 2),
                   's')
            
            return {'FINISHED'}
        
        elif event.type in ['ESC']:
            self._cancel(sett, context)
            
            return {'RUNNING_MODAL'}
        
        elif event.type == 'TIMER':
            #Check if all humans in the list are already generated
            if self.human_idx == len(self.generate_queue):   
                self.finish_modal = True
                return {'RUNNING_MODAL'}
            
            current_marker = self.generate_queue[self.human_idx]
            if has_associated_human(current_marker):
                self._delete_old_associated_human(current_marker)
                
            pose_type = current_marker['hg_batch_marker']

            generator = self._create_generator_instance(sett)   
            result = generator.generate_in_background(
                context = context,
                gender = str(random.choices(
                    ('male', 'female'),
                    weights = (sett.male_chance, sett.female_chance),
                    k=1)[0]),
                ethnicity = str(random.choices(
                    ('caucasian', 'black', 'asian'),
                    weights = (
                        sett.caucasian_chance,
                        sett.black_chance,
                        sett.asian_chance
                        ),
                    k=1
                    )[0]),
                add_hair = sett.batch_hair,
                hair_type = 'particle', #sett.batch_hairtype,
                hair_quality = getattr(sett, f'batch_hair_quality_particle'),#{sett.batch_hairtype}'),
                add_expression = sett.batch_expression,
                expressions_category = self._choose_category_list(context, 'expressions'),
                add_clothing = sett.batch_clothing,
                clothing_category= self._choose_category_list(context, 'outfit'),
                pose_type = pose_type
                )
            
            if not result:
                self._cancel(sett, context)
                return {'RUNNING_MODAL'}
            else:
                hg_rig = result.rig_object
            
            hg_rig.location = current_marker.location
            hg_rig.rotation_euler = current_marker.rotation_euler
            current_marker['associated_human'] = hg_rig
            
            self.human_idx += 1
            
            if self.human_idx > 0:
                progress = self.human_idx / (len(self.generate_queue))
                sett.batch_progress =  int(progress * 100)
                 
            sett.batch_idx += 1
            context.workspace.status_text_set(status_text_callback)
         
            return {'RUNNING_MODAL'}
        
        else:
            return {'RUNNING_MODAL'}

    def _delete_old_associated_human(self, marker):
        associated_human = marker['associated_human']
        for child in associated_human.children[:]:
            hg_delete(child)
        hg_delete(associated_human)

    def _cancel(self, sett, context):
        hg_log('Batch modal is cancelling')
        sett.batch_progress = sett.batch_progress + (100 - sett.batch_progress) / 2.0

        self.finish_modal = True
        context.workspace.status_text_set(status_text_callback)
        return {'CANCELLED'}

    def _choose_category_list(self, context, pcoll_name):
        
        #TODO fix naming inconsistency
        label = 'expressions' if pcoll_name == 'expressions' else 'clothing'
        
        collection = getattr(context.scene, f'batch_{label}_col')
        
        enabled_categories = [
                i.library_name
                for i in collection
                if i.enabled]
        if not enabled_categories:
            bpy.ops.hg3d.refresh_batch_uilists()
            
            enabled_categories = [i.library_name for i in collection]
            
        return random.choice(enabled_categories)

    def _create_generator_instance(self, sett):
        q_names = [
            'delete_backup',
            'apply_shapekeys',
            'apply_armature_modifier',
            'remove_clothing_subdiv',
            'remove_clothing_solidify',
            'apply_clothing_geometry_masks',
            'texture_resolution'
        ]
        
        quality_dict = {n: getattr(sett, f'batch_{n}') for n in q_names}
        
        generator = HG_Batch_Generator(**quality_dict)
        
        return generator