import json
import os
from pathlib import Path
import subprocess
import time
import bpy #type:ignore
import sys
from .. features.common.HG_COMMON_FUNC import ShowMessageBox, get_prefs, show_message, toggle_hair_visibility  # type:ignore


def get_humgen_folder(context):
    try:
        humgen_name = next((addon for addon in context.preferences.addons 
                            if 'humgen' in addon.module.lower()))
    except StopIteration:
        return None
    
    print(bpy.app.binary_path)
    
    

def get_pcoll_options(pcoll_name) -> list:
    sett = bpy.context.scene.HG3D
    pcoll_list = sett['previews_list_{}'.format(pcoll_name)]
    
    return pcoll_list


def generate_human_in_background(context, settings_dict) -> bpy.types.Object:
    for obj in context.selected_objects:
        obj.select_set(False)

    #TODO make absolute
    python_file = str(Path(__file__).parent.parent.parent.absolute()) + str(Path('/scripts/batch_generate.py'))
    
    start_time_background_process = time.time()
    
    print('###########################################################')
    print('############### STARTING BACKGROUND PROCESS ###############')
    
    _run_hg_subprocess(settings_dict, python_file)

    print('################ END OF BACKGROUND PROCESS ################')

    print(f'Background Proces succesful, took: ',
            round(time.time() - start_time_background_process, 2),
            's'
            )

    hg_rig = _import_generated_human()
    
    return hg_rig

def _run_hg_subprocess(settings_dict, python_file):
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

    if background_blender.stderr:
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
    
    hg_rig = next((obj for obj in data_to.objects if obj.HG.ishuman and obj.HG.backup),
                    [obj for obj in data_to.objects if obj.HG.ishuman][0])
    
    print(f'Import succesful for human {hg_rig.name}, import took: ',
            round(time.time() - start_time_import, 2),
            's'
            )
            
    return hg_rig