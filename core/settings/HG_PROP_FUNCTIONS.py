'''
functions used by properties
'''

import bpy #type: ignore
import os
from pathlib import Path
from ... features.common.HG_COMMON_FUNC import find_human

def find_folders(self, context, categ, gender_toggle, include_all = True):
    '''
    returns enum of folders found in a specific directory. These serve as categories for that specific pcoll
    '''
    hg_rig = find_human(context.active_object)
    pref = context.preferences.addons[__package__].preferences

    if isinstance(gender_toggle, (bool)):
        if hg_rig:
            gender = hg_rig.HG.gender
        else:
            return []
    else:
        gender = gender_toggle

    if gender_toggle == True:
        categ_folder = str(pref.filepath) + str(Path('/{}/{}/'.format(categ, gender)))
    elif gender_toggle == False:
        categ_folder = str(pref.filepath) + str(Path('/{}/'.format(categ)))
    else:
        categ_folder = str(pref.filepath) + str(Path('/{}/{}/'.format(categ, gender_toggle)))
        
    dirlist = os.listdir(categ_folder)
    dirlist.sort()
    categ_list = []
    ext = ('.jpg', 'png', '.jpeg', '.blend')
    for item in dirlist:
        if not item.endswith(ext):
            categ_list.append(item)
    
    if not categ_list:
        categ_list.append('No Category Found')
     
    enum_list = [('All', 'All Categories', '', 0)] if include_all else []
    for i, name in enumerate(categ_list):
        enum_list.append((name, name, '', i+1))
    
    return enum_list


def find_item_amount(context, categ, gender, folder):
    '''
    used by batch menu, showing the total amount of items of the selected categories
    '''
    pref = context.preferences.addons[__package__].preferences
    
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