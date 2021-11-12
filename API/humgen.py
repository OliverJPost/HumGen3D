import json
import os
import random
import subprocess
import time

import bpy  # type:ignore

from ..features.common.HG_COMMON_FUNC import get_addon_root  # type:ignore
from ..features.common.HG_COMMON_FUNC import (get_prefs, hg_log,
                                              toggle_hair_visibility)


def get_pcoll_options(pcoll_name) -> list:
    sett = bpy.context.scene.HG3D
    pcoll_list = sett['previews_list_{}'.format(pcoll_name)]
    
    return pcoll_list

def create_settings_dict_from_keywords(
    gender = random.choice(('male', 'female')),
    ethnicity = random.choice(('caucasian', 'black', 'asian')), #TODO option for custom ethnicities for custom starting humans
    add_hair = False,
    hair_type = 'particle',
    hair_quality = 'medium',
    add_expression = False,
    expressions_category = 'All',
    add_clothing = False,
    clothing_category = 'All',
    pose_type = 'A_Pose'
    ) -> dict:
    
    """Creates a dictionary with settings to pass to generate_human_in_background
    if you don't want to use the default settings or want to add hair, clothing
    etc. Creating this dict is optional.

    Args:
        gender (str, optional): The gender of the human to create, either 'male'
            or 'female'. 
            Defaults to random.choice(('male', 'female')).
        ethnicity (str, optional): Ethnicity of the human to create. Will search
            for starting humans with this string in their name.
            Defaults to random.choice(('caucasian', 'black', 'asian')).
        add_hair (bool, optional): If True, hair will be added to the created 
            human. 
            Defaults to False.
        hair_type (str, optional): Choose between 'particle' and 'haircards' for
            the add-on to create.
            Ignored if add_hair == False.
            Defaults to 'particle'.
        hair_quality (str, optional): The quality of the particle system to 
            create, in ('high', 'medium', 'low', 'ultralow'). 
            Defaults to 'medium'.
        add_expression (bool, optional): If True, a 1-click expression will be 
            added to the human.
            Defaults to False.
        expressions_category (str, optional): Category to choose expression 
            from.
            Use get_pcoll_categs('expression') to see options.
            Ignored if add_expression == False.
            Defaults to 'All'.
        add_clothing (bool, optional): If True, an outfit and footwear will be 
            added to this human.
            Defaults to False.
        clothing_category (str, optional): Category to choose outfit from. 
            Use get_pcoll_categs('outfit') to see options.
            Ignored if add_clothing == False.
            Defaults to 'All'.
        pose_type (str, optional): Category to choose pose from. 
            Use get_pcoll_categs('pose') to see options.
            Defaults to 'A_Pose'.

    Returns:
        dict: Settings dictionary to pass to generate_human_in_background
    """
    
    return locals()
    
def create_quality_dict_from_keywords(
    delete_backup = True,
    apply_shapekeys = True,
    apply_armature_modifier = True,
    remove_clothing_subdiv = True,
    remove_clothing_solidify = True,
    apply_clothing_geometry_masks = True,
    texture_resolution = 'optimised'
    ) -> dict:
    """Creates a dictionary with settings to pass to generate_human_in_background
    if you want to change the quality settings from the default values.

    Args:
        delete_backup (bool, optional): Delete the backup human, which is an 
            extra object used to revert to creation phase and to load 1-click 
            expressions. 
            Big storage impact. Medium RAM impact.
            Defaults to True.
        apply_shapekeys (bool, optional): Applies all the shape keys on the 
            human. Simplifies object. 
            Small performance impact, medium storage impact. 
            Defaults to True.
        apply_armature_modifier (bool, optional): Applies the armature modifier,
            removes bone vertex groups and deletes the rig. 
            Use this if you don't need a rig. 
            Small impact. 
            Defaults to True.
        remove_clothing_subdiv (bool, optional): Removes any subdiv modifier 
            from clothing.
            Small to medium impact. 
            Defaults to True.
        remove_clothing_solidify (bool, optional): Removes any solidify modifier
            from clothing. 
            Small to medium impact. 
            Defaults to True.
        apply_clothing_geometry_masks (bool, optional): Applies the modifiers 
            that hide the body geometry behind clothing. 
            Small impact.
            Defaults to True.
        texture_resolution (str, optional): Texture resolution in 
            ('high', 'optimised', 'performance') from high to low. 
            Also applies to clothing, eyes and teeth.
            HUGE memory and Eevee impact. 
            Defaults to 'optimised'.

    Returns:
        dict: Quality dictionary to pass to generate_human_in_background
    """
    
    return locals()


def generate_human_in_background(
        context,
        settings_dict = create_settings_dict_from_keywords(),
        quality_dict = create_quality_dict_from_keywords()
    ) -> bpy.types.Object:
    
    for obj in context.selected_objects:
        obj.select_set(False)

    python_file = os.path.join(get_addon_root(), 'scripts', 'batch_generate.py')
    
    start_time_background_process = time.time()
    
    hg_log('STARTING HumGen background process', level = 'BACKGROUND')
    _run_hg_subprocess(settings_dict, quality_dict, python_file)
    hg_log('^^^ HumGen background process ENDED', level = 'BACKGROUND')

    hg_log(f'Background Process succesful, took: ',
            round(time.time() - start_time_background_process, 2),
            's'
            )

    hg_rig = _import_generated_human()
    
    return hg_rig

def _run_hg_subprocess(settings_dict, quality_dict, python_file):
    background_blender = subprocess.run(
        [
            bpy.app.binary_path,
            "--background",
            "--python",
            python_file,
            json.dumps({**settings_dict, **quality_dict})
        ],
        stdout= subprocess.PIPE,
        stderr= subprocess.PIPE)

    for line in background_blender.stdout.decode("utf-8").splitlines():
        if line.startswith(('HG_', '\033')):
            print(line)

    if background_blender.stderr:
        hg_log('Exception occured while in background process', level = 'WARNING')
        print(background_blender.stderr.decode("utf-8"))
        #ShowMessageBox(message = 
        #    f'''An error occured while generating human, check the console for error details''')

def _import_generated_human():
    start_time_import = time.time()
    batch_result_path = os.path.join(get_prefs().filepath, 'batch_result.blend')
    with bpy.data.libraries.load(batch_result_path, link = False) as (data_from ,data_to):
        data_to.objects = data_from.objects
    
    for obj in data_to.objects:
        bpy.context.scene.collection.objects.link(obj)
        toggle_hair_visibility(obj, show = True)
    
    human_parent = next((obj for obj in data_to.objects if obj.HG.ishuman and obj.HG.backup),
                    [obj for obj in data_to.objects if obj.HG.ishuman][0])
    
    hg_log(f'Import succesful for human {human_parent.name}, import took: ',
            round(time.time() - start_time_import, 2),
            's'
            )
            
    return human_parent
