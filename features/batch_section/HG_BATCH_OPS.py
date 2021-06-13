'''
Inactive file to be implemented later, batch mode for generating multiple humans at once
'''

import bpy #type: ignore
import random
import time
import threading

from .. creation_phase.HG_CREATION import load_human, give_name
from .. common.HG_RANDOM import get_random_from_pcoll, random_body_type, random_length
from .. creation_phase.HG_NEXTPHASE import corrective_shapekey_copy, reapply_shapekeys, set_backup, finish_creation_phase
from .. creation_phase.HG_LENGTH import random_length
from .. common.HG_COMMON_FUNC import apply_shapekeys

class HG_BATCH_GENERATE(bpy.types.Operator):
    """
    clears searchfield INACTIVE
    """
    bl_idname = "hg3d.generate"
    bl_label = "Generate"
    bl_description = "Generates specified amount of humans"
    bl_options = {"REGISTER", "UNDO"}


    def execute(self,context):
        sett = context.scene.HG3D

        total_start = time.time()

        for obj in context.selected_objects:
            obj.select_set(False)

        gender = random.choices(('male', 'female'), weights = (sett.male_chance, sett.female_chance), k=1)[0]
        sett.gender = gender
        get_random_from_pcoll(context, sett, 'humans')
        #ethnicity
        hg_rig, hg_body = load_human(context) 

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

        start_time = time.time()
        if sett.batch_clothing:
            get_random_from_pcoll(context, sett, 'outfit')
        print('clothing {}'.format(time.time()-start_time))


        if sett.batch_pose:
            get_random_from_pcoll(context, sett, 'poses')


        if sett.batch_expression:
            pick_library(context, 'expressions')
            get_random_from_pcoll(context, sett, 'expressions')


        print('total time {}'.format(time.time()-total_start))
        hg_rig.HG.phase = 'clothing'

        return {'RUNNING_MODAL'}
   


def pick_library(context, categ, gender = None):
    #INACTIVE
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




  
