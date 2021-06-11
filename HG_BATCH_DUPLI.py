'''
Inactive file to be implemented later, batch mode for generating multiple humans at once
'''

import bpy #type: ignore
import random
import time
import threading

from . HG_CREATION import load_human, give_name
from . HG_RANDOM import get_random_from_pcoll, random_body_type, random_length
from . HG_NEXTPHASE import corrective_shapekey_copy, reapply_shapekeys, set_backup, finish_creation_phase
from . HG_LENGTH import random_length
from . HG_COMMON_FUNC import apply_shapekeys

def status_text_callback(header, context):
    print('text callback')
    sett   = context.scene.HG3D
    layout = header.layout

    layout.separator_spacer()
    layout.alignment = 'EXPAND'
    
    row           = layout.row(align=False)
    row.alignment = 'CENTER'
    
    # if sett.building:
    #     layout.label(text=t('info_building_model'), icon='TIME')
    # else:
    layout.label(text='Building Human X', icon='TIME')
    
    col         = layout.column()
    col.scale_x = 1.6
    col.prop(sett, "batch_progress")
    print('setting prop PROGRESSSSSSSSSSSSSSSS', sett.batch_progress)

    # if not sett.building:
    layout.label(text='', icon='EVENT_ESC')
    
    layout.separator_spacer()



class HG_BATCH_GENERATE(bpy.types.Operator):
    """
    clears searchfield
    """
    bl_idname = "hg3d.generate"
    bl_label = "Generate"
    bl_description = "Generates specified amount of humans"
    bl_options = {"REGISTER", "UNDO"}

    def __init__(self):
        self.human_idx = 0
        self.generate_amount = 4
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

            return {'RUNNING_MODAL'}
        
        elif event.type in ['ESC']:
            print('modal is cancelling')
            sett.batch_progress = sett.batch_progress + (100 - sett.batch_progress) / 2.0

            self.finish_step = True
            context.workspace.status_text_set(status_text_callback)
            
            return {'RUNNING_MODAL'}
        
        elif event.type == 'TIMER':
            print('timer event')
            if self.human_idx != self.generate_amount:    
                #time.sleep(5)
                generate_human(self, context)
                self.human_idx += 1
                
                if self.human_idx > 0:
                    # Calculate batch_progress in an exponential fashion, it's pretty accurate.
                    exponent = 1
                    if self.generate_amount > 4:
                        exponent = 1.4
                    progress = pow(self.human_idx / (self.generate_amount + 1), exponent)  # Plus one for building. REMOVE?
                    sett.batch_progress += 25 # max(1, int(progress * 100))
                    print('PROGRESSSSSSSSSSSSSSSSSSSSS', sett.batch_progress)
                
            else:
                self.finish_step = True
            

            context.workspace.status_text_set(status_text_callback)
         
            return {'RUNNING_MODAL'}
        else:
            return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        #context.window.cursor_modal_set('WAIT')

        sett = context.scene.HG3D

        
        wm = context.window_manager
        wm.modal_handler_add(self)

        sett.batch_progress = 0

        self.human_idx = 0
        self.timer = wm.event_timer_add(0.01, window=context.window)

        context.workspace.status_text_set(status_text_callback)
        print('invoking modal')
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        #context.window.cursor_modal_restore()
        context.workspace.status_text_set(text=None)
        return {'CANCELLED'}

def generate_human(self, context):
    sett = context.scene.HG3D
    total_start = time.time()

    print('starting human', self.human_idx)

    for obj in context.selected_objects:
        obj.select_set(False)
    #print('running {}'.format(idx))

    gender = random.choices(('male', 'female'), weights = (sett.male_chance, sett.female_chance), k=1)[0]
    sett.gender = gender
    get_random_from_pcoll(context, sett, 'humans')
    #ethnicity
    hg_rig, hg_body = load_human(context) 

    hg_rig.location[0] = self.x_loc
    self.x_loc += 2
    context.view_layer.objects.active = hg_rig
    name = give_name(gender, hg_rig)

    random_body_type(hg_rig)



    if sett.batch_hair:
        get_random_from_pcoll(context, sett, 'hair')


    random_length(context, hg_rig)

    start_time = time.time()
    finish_creation_phase(None, context, hg_rig, hg_body)
    print('finish creation {}'.format(time.time()-start_time))

    context.view_layer.objects.active = hg_rig

    if sett.batch_clothing:
        get_random_from_pcoll(context, sett, 'outfit')


    if sett.batch_pose:
        get_random_from_pcoll(context, sett, 'poses')

    if sett.batch_expression:
        pick_library(context, 'expressions')
        get_random_from_pcoll(context, sett, 'expressions')


    print('total time {}'.format(time.time()-total_start))
    hg_rig.HG.phase = 'clothing'


def pick_library(context, categ, gender = None):
    sett = context.scene.HG3D

    if categ == 'expressions':
        collection = context.scene.expressions_col
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

        sett.expressions_sub = random.choice(library_list)


    # def modal(self, context, event):
    #     context.area.tag_redraw()
    #     sett = context.scene.HG3D
    #     wm = context.window_manager
    #     print('modallll')
    #     if sett.batch_batch_progress == 0:
    #         print('starting run')
    #         self.run(context)
    #     elif sett.batch_batch_progress == 100:
    #         return {'FINISHED'}
    #     return {'PASS_THROUGH'}

    # def cancel(self, context):
    #     context.window.cursor_modal_restore()
    #     return {'CANCELLED'}

    # def invoke(self, context, event):
    #     context.window.cursor_modal_set('WAIT')
    #     context.window_manager.modal_handler_add(self)
    #     return {'RUNNING_MODAL'}


  
