'''
Inactive file to be implemented later, batch mode for generating multiple 
humans at once
'''

from ... features.batch_section.HG_QUICK_GENERATOR import toggle_hair_visibility
from ... user_interface.HG_BATCH_UILIST import uilist_refresh
import bpy #type: ignore
import random
import time
import subprocess
import json 

from pathlib import Path

from .. creation_phase.HG_CREATION import (HG_CREATION_BASE, set_eevee_ao_and_strip)
from .. common.HG_COMMON_FUNC import hg_delete, show_message

def status_text_callback(header, context):
    #INACTIVE
    
    sett   = context.scene.HG3D
    layout = header.layout

    layout.separator_spacer()
    layout.alignment = 'EXPAND'
    
    row           = layout.row(align=False)
    row.alignment = 'CENTER'
    
    layout.label(text=f'Building Human {sett.batch_idx}', icon='TIME')
    
    col         = layout.column()
    col.scale_x = 1.6
    col.prop(sett, "batch_progress")

    # if not sett.building:
    layout.label(text='', icon='EVENT_ESC')
    
    layout.separator_spacer()

def get_batch_marker_list(context) -> list:
    sett = context.scene.HG3D
    
    marker_selection = sett.batch_marker_selection

    all_markers = [obj for obj in bpy.data.objects if 'hg_batch_marker' in obj]
    
    if marker_selection == 'all':
        return all_markers
    
    elif marker_selection == 'selected':
        selected_markers = [
            o for o in all_markers 
            if o in context.selected_objects
            ]
        return selected_markers
    
    else:
        empty_markers = [o for o in all_markers if not has_associated_human(o)]
        return empty_markers

def has_associated_human(marker) -> bool:
    """Check if this marker has an associated human and if that object still 
    exists

    Args:
        marker (Object): marker object to check for associated human

    Returns:
        bool: True if associated human was found, False if not
    """
    
    return (
        'associated_human' in marker #does it have the prop
        and marker['associated_human'] #is the prop not empty
        and bpy.data.objects.get(marker['associated_human'].name) #does the object still exist
        and marker.location == marker['associated_human'].location #is the object at the same spot as the marker
        and bpy.context.scene.objects.get(marker['associated_human'].name) #is the object in the current scene
    )
    
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
        self.generate_amount = bpy.context.scene.HG3D.generate_amount
        self.generate_queue = get_batch_marker_list(bpy.context)
        self.finish_step = False
        self.done  = False
        self.timer = None
        self.x_loc = 0
        self.start_time = time.time()

    def modal(self, context, event):
        """ Event handling. """
        
        sett = context.scene.HG3D
        wm = context.window_manager
        
        if self.done:
            sett.batch_progress = 100
            
            wm.event_timer_remove(self.timer)
            #context.window.cursor_modal_restore()
            context.area.tag_redraw()

            context.workspace.status_text_set(text=None)
            print('ENDING TIME: ', time.time()-self.start_time)
            return {'FINISHED'}

        elif self.finish_step:
            sett.batch_progress = sett.batch_progress + (100 - sett.batch_progress) / 2.0
            
            sett.batch_progress = 100
            context.workspace.status_text_set(status_text_callback)
            context.area.tag_redraw()

            self.done = True
            sett.batch_idx = 0
            
            return {'RUNNING_MODAL'}
        
        elif event.type in ['ESC']:
            
            self._cancel(sett, context)
            
            return {'RUNNING_MODAL'}
        
        elif event.type == 'TIMER':
            print('timer event')
            if self.human_idx < len(self.generate_queue):    
                marker = self.generate_queue[self.human_idx]
                if has_associated_human(marker):
                    self._delete_old_associated_human(marker)
                result = self.generate_human_in_background(context, marker)
                
                if not result:
                    self._cancel(sett, context)
                    return {'RUNNING_MODAL'}
                else:
                    hg_rig = result
                
                hg_rig.location = marker.location
                hg_rig.rotation_euler = marker.rotation_euler
                marker['associated_human'] = hg_rig
                
                self.human_idx += 1
                
                if self.human_idx > 0:
                    progress = self.human_idx / (len(self.generate_queue))
                    sett.batch_progress =  int(progress * 100)
                
            else:
                print('finishing because human_idx is generate amount', self.human_idx, self.generate_amount)
                self.finish_step = True
            
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

    def invoke(self, context, event):
        sett = context.scene.HG3D
        
        markers_with_associated_human = list(filter(has_associated_human, self.generate_queue))
          
        if self.run_immediately or not markers_with_associated_human:
            wm = context.window_manager
            wm.modal_handler_add(self)

            sett.batch_progress = 0

            self.human_idx = 0
            self.timer = wm.event_timer_add(0.01, window=context.window)

            sett.batch_idx = 1
            context.workspace.status_text_set(status_text_callback)
            set_eevee_ao_and_strip(context)
            
            return {'RUNNING_MODAL'}
        else:
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
            
            return {'CANCELLED'}

    def draw(self, context):
        layout = self.layout
        
        layout.label(text = 'Test label')

    def _cancel(self, sett, context):
        print('modal is cancelling')
        sett.batch_progress = sett.batch_progress + (100 - sett.batch_progress) / 2.0

        print('finishing because escape')
        self.finish_step = True
        context.workspace.status_text_set(status_text_callback)
        return {'CANCELLED'}

    def generate_human_in_background(self, context, marker) -> bpy.types.Object:
        sett = context.scene.HG3D
        total_start = time.time()

        print('starting human', self.human_idx)

        for obj in context.selected_objects:
            obj.select_set(False)
        #print('running {}'.format(idx))

        python_file = str(Path(__file__).parent.parent.parent.absolute()) + str(Path('/scripts/batch_generate.py'))


        pose_type = marker['hg_batch_marker']
        settings_dict = self._build_settings_dict(context, sett, pose_type)

        start_time = time.time()
        
        print('###########################################################')
        print('############### STARTING BACKGROUND PROCESS ###############')
        
        try:
            background_blender = subprocess.run(
                [
                    bpy.app.binary_path,
                    "--background",
                    "--python",
                    python_file,
                    json.dumps(settings_dict)
                ],
                stdout= subprocess.DEVNULL,
                stderr= subprocess.PIPE)
        except SystemError:
            print('Background SystemError')
        else:     
            if background_blender.stderr:
                print(background_blender.stderr.decode("utf-8"))
                show_message(self, f'An error occured while generating human {self.human_idx}, check the console for error details')
                return None #Cancel modal 
 
        print('################ END OF BACKGROUND PROCESS ################')

        print(f'Background Proces succesful for marker {marker.name}, took: ',
              round(time.time() - start_time, 2),
              's'
              )

        
        with bpy.data.libraries.load('/Users/olepost/Documents/Humgen_Files_Main/batch_result.blend', link = False) as (data_from ,data_to):
            data_to.objects = data_from.objects
        
        for obj in data_to.objects:
            bpy.context.scene.collection.objects.link(obj)
            toggle_hair_visibility(obj, show = True)
        
        
           
        return next((obj for obj in data_to.objects if obj.HG.ishuman and obj.HG.backup),
                    [obj for obj in data_to.objects if obj.HG.ishuman][0])

    def _build_settings_dict(self, context, sett, pose_type) -> dict:
        sd = {}
        
        for quality_setting in self._get_quality_setting_names():
            sd[quality_setting] = getattr(sett, f'batch_{quality_setting}')
        
        sd['gender'] = str(random.choices(
            ('male', 'female'),
            weights = (sett.male_chance, sett.female_chance),
            k=1)[0])
        
        sd['ethnicity'] = str(random.choices(
            ('caucasian', 'black', 'asian'),
            weights = (
                sett.caucasian_chance,
                sett.black_chance,
                sett.asian_chance
                ),
            k=1
            )[0])
                                    
        sd['add_hair'] = sett.batch_hair
        sd['hair_type'] = sett.batch_hairtype
        sd['hair_quality'] = getattr(sett, f'batch_hair_quality_{sett.batch_hairtype}')
        
        sd['add_expression'] = sett.batch_expression
        if sett.batch_expression:
            self._add_category_list(context, sd, 'expressions') 
        
        sd['add_clothing'] = sett.batch_clothing
        
        self._add_category_list(context, sd, 'clothing') 
        
        sd['pose_type'] = pose_type
        
        return sd

    def _add_category_list(self, context, sd, pcoll_name):
        
        #TODO fix naming inconsistency
        label = 'expressions' if pcoll_name == 'expressions' else 'clothing'
        
        enabled_categories = [
                i.library_name
                for i in getattr(context.scene, f'batch_{label}_col')
                if i.enabled]
        if not enabled_categories:
            uilist_refresh(self, context, label)
            enabled_categories = getattr(context.scene, [i.library_name for i in f'batch_{label}_col'])
            
        sd[f'{pcoll_name}_category'] = random.choice(enabled_categories)

    def _get_quality_setting_names(self):
        return [
            'delete_backup',
            'apply_shapekeys',
            'apply_armature_modifier',
            'remove_clothing_subdiv',
            'remove_clothing_solidify',
            'apply_clothing_geometry_masks',
            'texture_resolution',
            'poly_reduction',
            'apply_poly_reduction'
        ]
        

def pick_library(context, categ, gender = None):
    #INACTIVE
    sett = context.scene.HG3D

    if categ == 'expressions':
        collection = context.scene.batch_expressions_col
        if gender:
            library_list = []
            for item in collection:
                if not item.enabled:
                    continue
                elif gender:
                    if gender == 'male' and item.male_items >=0:
                        library_list.append(item.library_name)
                    elif gender == 'female' and item.female_items >= 0:
                        library_list.append(item.library_name)
        else:
            library_list = [item.library_name for item in collection if item.count != 0 and item.enabled]

        print('library list ', library_list)
        sett.expressions_sub = random.choice(library_list)

