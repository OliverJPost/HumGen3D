'''
Inactive file to be implemented later, batch mode for generating multiple 
humans at once
'''

import bpy #type: ignore
import random
import time
import subprocess
import json 

from pathlib import Path

from bpy.props import IntProperty, StringProperty, FloatProperty, BoolProperty #type:ignore

from .. creation_phase.HG_CREATION import (HG_CREATION_BASE)
from .. common.HG_RANDOM import (
    set_random_active_in_pcoll,
    random_body_type,
)
from .. creation_phase.HG_FINISH_CREATION_PHASE import (
    extract_shapekeys_to_keep,
    reapply_shapekeys,
    _create_backup_human,
    finish_creation_phase
)
from .. common.HG_COMMON_FUNC import apply_shapekeys

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
    return all((
        'asociated_human' in marker,
        bpy.data.objects.get(marker['associated_human'].name)
    ))
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
            print('modal is cancelling')
            sett.batch_progress = sett.batch_progress + (100 - sett.batch_progress) / 2.0

            print('finishing because escape')
            self.finish_step = True
            context.workspace.status_text_set(status_text_callback)
            
            return {'RUNNING_MODAL'}
        
        elif event.type == 'TIMER':
            print('timer event')
            if self.human_idx < len(self.generate_queue):    
                marker = self.generate_queue[self.human_idx]
                hg_rig = self.generate_human_in_background(context)
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

    def invoke(self, context, event):
        #INACTIVE

        sett = context.scene.HG3D
          
        if True:#self.run_immediately:
            wm = context.window_manager
            wm.modal_handler_add(self)

            sett.batch_progress = 0

            self.human_idx = 0
            self.timer = wm.event_timer_add(0.01, window=context.window)

            sett.batch_idx = 1
            context.workspace.status_text_set(status_text_callback)
        
            return {'RUNNING_MODAL'}
        else:
            def draw(self, context):
                layout = self.layout
    
                layout.operator("hg3d.generate", text="Run anyway").run_immediately = True
                return 

            context.window_manager.popup_menu(draw, title="Test title")
            
            return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        
        layout.label(text = 'Test label')

    def cancel(self, context):
        #context.window.cursor_modal_restore()
        context.workspace.status_text_set(text=None)
        return {'CANCELLED'}

    def generate_human_in_background(self, context) -> bpy.types.Object:
        sett = context.scene.HG3D
        total_start = time.time()

        print('starting human', self.human_idx)

        for obj in context.selected_objects:
            obj.select_set(False)
        #print('running {}'.format(idx))

        python_file = str(Path(__file__).parent.parent.parent.absolute()) + str(Path('/scripts/batch_generate.py'))

        settings_dict = self._build_settings_dict(sett)

        start_time = time.time()
        subprocess.run([bpy.app.binary_path,
                            "--background",
                            "--python",
                            python_file,
                            json.dumps(settings_dict)])
        
        with bpy.data.libraries.load('/Users/olepost/Documents/Humgen_Files_Main/batch_result.blend', link = False) as (data_from ,data_to):
            data_to.objects = data_from.objects
        
        for obj in data_to.objects:
            bpy.context.scene.collection.objects.link(obj)
        
        print('end time', time.time() - start_time)
        
        return next(obj for obj in data_to.objects if obj.HG.ishuman)

    def _build_settings_dict(self, sett) -> dict:
        settings_dict = {
            'keep_backup': False,
            'clothing_subdiv': False,
            
            'male_chance': sett.male_chance,
            'female_chance': sett.female_chance,
            
            'caucasian_chance': sett.caucasian_chance,
            'black_chance': sett.black_chance,
            'asian_chance': sett.asian_chance,
            
            'add_hair': sett.batch_hair,
            'add_expression': sett.batch_expression,
            'add_clothing': sett.batch_clothing,
            'add_pose': sett.batch_pose
        }
        
        return settings_dict
        

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

class HG_BATCH_MAKE(bpy.types.Operator, HG_CREATION_BASE):
    """
    clears searchfield INACTIVE
    """
    bl_idname = "hg3d.batch_make"
    bl_label = "Batch make"
    bl_description = "Generates humans"
    bl_options = {"REGISTER", "UNDO"}

    keep_backup: BoolProperty()
    clothing_subdiv: BoolProperty()

    male_chance  : IntProperty()
    female_chance: IntProperty()

    caucasian_chance: IntProperty()
    asian_chance    : IntProperty()
    black_chance    : IntProperty()
    
    add_hair: BoolProperty()
    add_clothing: BoolProperty()
    add_expression: BoolProperty()
    add_pose: BoolProperty()
    

    def execute(self, context):
        sett = context.scene.HG3D

        gender = random.choices(('male', 'female'), weights = (self.male_chance, self.female_chance), k=1)[0]
        sett.gender = gender
        
        ethnicity_search = random.choices(
            ('caucasian',
             'black',
             'asian'
             ),
            weights = (
                self.caucasian_chance,
                self.black_chance,
                self.asian_chance
                ),
            k=1
            )[0]
        
        set_random_active_in_pcoll(context, sett, 'humans', searchterm = ethnicity_search)
        #ethnicity
        hg_rig, hg_body = self.create_human(context) #inherited

        context.view_layer.objects.active = hg_rig
        name = self._get_random_name(gender, hg_rig) #inherited        
        
        random_body_type(hg_rig)

        if self.add_hair:
            set_random_active_in_pcoll(context, sett, 'hair')
        
        sett.human_length = random.randrange(150, 200)
        
        start_time = time.time()
        finish_creation_phase(None, context, hg_rig, hg_body)
        print('finish creation {}'.format(time.time()-start_time))

        context.view_layer.objects.active = hg_rig

        if self.add_clothing:
            set_random_active_in_pcoll(context, sett, 'outfit')


        if self.add_pose:
            set_random_active_in_pcoll(context, sett, 'poses')

        if self.add_expression:
            #pick_library(context, 'expressions')
            set_random_active_in_pcoll(context, sett, 'expressions')


        hg_rig.HG.phase = 'clothing'        
        return {'FINISHED'}



  
