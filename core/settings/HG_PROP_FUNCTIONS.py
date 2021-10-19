'''
functions used by properties
'''

import os
from pathlib import Path

from ...features.common.HG_COMMON_FUNC import find_human, get_prefs


def find_folders(self, context, categ, gender_toggle, include_all = True, 
                 gender_override = None) -> list:
    """Gets enum of folders found in a specific directory. T
    hese serve as categories for that specific pcoll

    Args:
        context (bpy.context): blender context
        categ (str): preview collection name
        gender_toggle (bool): Search for folders that are in respective male/female
            folders. 
        include_all (bool, optional): include "All" as first item. 
            Defaults to True.
        gender_override (str): Used by operations that are not linked to a single
            human. Instead of getting the gender from hg_rig this allows for the
            manual passing of the gender ('male' or 'female')

    Returns:
        list: enum of folders
    """
    hg_rig = find_human(context.active_object)
    pref = get_prefs()

    if gender_override:
        gender = gender_override
    elif hg_rig:
        gender = hg_rig.HG.gender
    else:
        return []


    if gender_toggle == True:
        categ_folder = os.path.join(pref.filepath, categ, gender)
    else:
        categ_folder = os.path.join(pref.filepath, categ)
      
    dirlist = os.listdir(categ_folder)
    dirlist.sort()
    categ_list = []
    ext = ('.jpg', 'png', '.jpeg', '.blend')
    for item in dirlist:
        if not item.endswith(ext) and item != '.DS_Store':
            categ_list.append(item)
    
    if not categ_list:
        categ_list.append('No Category Found')
     
    enum_list = [('All', 'All Categories', '', 0)] if include_all else []
    for i, name in enumerate(categ_list):
        enum_list.append((name, name, '', i+1))

    return enum_list


def find_item_amount(context, categ, gender, folder) -> int:
    """used by batch menu, showing the total amount of items of the selected 
    categories

    Batch menu currently disabled
    """
    pref = get_prefs()
    
    if categ == 'expressions':
        ext = '.txt'
    else:
        ext = '.blend'
    
    if gender:
        dir = str(pref.filepath) + str(Path('/{}/{}/{}'.format(categ, gender, folder)))
    else:
        dir = str(pref.filepath) + str(Path('/{}/{}'.format(categ, folder)))

    if categ =='outfits':
        sett = context.scene.HG3D
        inside = sett.batch_clothing_inside
        outside = sett.batch_clothing_outside
        if inside and not outside:
            ext = 'I.blend'
        elif outside and not inside:
            ext = 'O.blend'

    return len([name for name in os.listdir(dir) if name.endswith(ext)])

def get_resolutions():
    return [
        ( "256",   "256 x 256",  "", 0),
        ( "512",   "512 x 512",  "", 1),
        ("1024", "1024 x 1024",  "", 2),
        ("2048", "2048 x 2048",  "", 3),
        ("4096", "4096 x 4096",  "", 4),
    ]
    
def poll_mtc_armature(self, object):
    return object.type == 'ARMATURE'
