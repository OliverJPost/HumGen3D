"""
Functions related to the preview_collections of human generator, including population of them
"""

import bpy #type: ignore
import os
from pathlib import Path
from . HG_COMMON_FUNC import find_human

preview_collections = {} #master dictionary of all pcolls

def list_blends_in_dir(dir, pcoll_type):    
    """
    gets a list of blend files in folder
    """
    sett = bpy.context.scene.HG3D
    
    search_term_dict = {
        'poses'      : sett.search_term_poses,
        'expressions': sett.search_term_expressions,
        'outfit'     : sett.search_term_outfit,
        'patterns'   : sett.search_term_patterns,
        'footwear'   : sett.search_term_footwear
        }

    search_term = search_term_dict[pcoll_type] if pcoll_type in search_term_dict else ''

    file_paths = []
    ext_dict = {'expressions': '.txt', 'humans': '.jpg', 'patterns': '.png', 'face_hair': '.json', 'hair': '.json', 'textures': ('.png', '.tiff', '.tga')}
    ext = ext_dict[pcoll_type] if pcoll_type in ext_dict else '.blend'
    for root, dirs, files in os.walk(dir):
        for fn in [fn for fn in  files if fn.lower().endswith(ext) and search_term.lower() in fn.lower()]:
            if pcoll_type == 'textures' and 'PBR' in root:
                continue
            file_paths.append(os.path.join(root, fn))             
    if sett.diagnostics:
        print('getting files for {} in {}'.format(pcoll_type, dir))
        print('found files {}'.format(file_paths))

    return file_paths

def get_pcoll_items(self,context,pcoll_type):
    pcoll = preview_collections.get('pcoll_{}'.format(pcoll_type))
    if not pcoll:
        return []
    return pcoll['pcoll_{}'.format(pcoll_type)]  

def refresh_pcoll(self, context,dir_type):
    '''
    refreshes a preview collection 
    '''
    sett = context.scene.HG3D

    if not dir_type == 'poses': #only allow loading when changing category in psoe mode when random is selected
        sett.load_exception = True
    populate_pcoll(self, context, dir_type)
    sett['pcoll_{}'.format(dir_type)] = 'none'    
    sett.load_exception = False

def load_thumbnail(thumb_name, pcoll):
    '''
    loads and returns thumbnail
    '''

    filepath_thumb = str(os.path.dirname(__file__)) + str(Path('/icons/{}.jpg'.format(thumb_name)))
    if not pcoll.get(filepath_thumb):
        thumb = pcoll.load(filepath_thumb, filepath_thumb, 'IMAGE')
    else: 
        thumb = pcoll[filepath_thumb]
    return thumb

def populate_pcoll(self, context, pcoll_categ):
    '''
    populates the preview collection enum list with blend file filepaths and icons
    '''
    sett = context.scene.HG3D
    pref = context.preferences.addons[__package__].preferences

    pcoll = preview_collections["pcoll_{}".format(pcoll_categ)]
    

    none_thumb = load_thumbnail('pcoll_placeholder', pcoll)
    pcoll_enum = [('none', '', '', none_thumb.icon_id, 0)]

    #create variables if they dont exist in settings
    if not 'previews_dir_{}'.format(pcoll_categ) in sett:
        sett['previews_dir_{}'.format(pcoll_categ)] = ''

    #clear previews list        
    sett['previews_list_{}'.format(pcoll_categ)] = []
    
    path_list = []        

    # find category and subcategory in order to determine the dir to search
    hg_rig = find_human(context.active_object)
    if pcoll_categ != 'humans':
        gender = hg_rig.HG.gender
    else:
        gender = None

    dir_categ_dict = {
        'poses'      : 'poses',
        'outfit'     : 'outfits/{}'.format(gender),
        'hair'       : 'hair/head/{}'.format(gender),
        'face_hair'  : 'hair/face_hair',
        'expressions': 'expressions',
        'humans'     : 'models',
        'footwear'   : 'footwear/{}'.format(gender),
        'patterns'   : 'patterns',
        'textures'   : 'textures/{}'.format(gender)
        }
    dir_categ = dir_categ_dict[pcoll_categ]
    dir_sub_dict = {
        'poses'      : sett.pose_sub,
        'outfit'     : sett.outfit_sub,
        'hair'       : sett.hair_sub,
        'face_hair'  : sett.face_hair_sub,
        'expressions': sett.expressions_sub,
        'humans'     : sett.gender,
        'footwear'   : sett.footwear_sub,
        'patterns'   : sett.patterns_sub,
        'textures'   : sett.texture_library
        }
    dir_subcateg = dir_sub_dict[pcoll_categ]
    
    search_dir = str(pref.filepath) + str(Path('/{}/'.format(dir_categ)))
    if dir_subcateg != 'All':
        search_dir = search_dir + str(Path('/{}/'.format(dir_subcateg)))
   
    #find all blend files in the selected dir
    blend_paths = list_blends_in_dir(search_dir, pcoll_categ)    
    
    #iterate over all blend files, adding them to the pcoll_enum   
    for i, full_path in enumerate(blend_paths):            
        if pcoll_categ in ['outfit', 'shoe'] and outfit_subcateg_skip(sett, full_path):
            continue
        filepath_thumb = os.path.splitext(full_path)[0] + '.jpg' 
        if not pcoll.get(filepath_thumb):
            thumb = pcoll.load(filepath_thumb, filepath_thumb, 'IMAGE')
        else: thumb = pcoll[filepath_thumb]   

        short_path = full_path.replace(str(pref.filepath), '')
        display_name = os.path.basename(full_path)
        for remove_string in ('HG', 'Male', 'Female'):
            display_name = display_name.replace(remove_string, '') 
        display_name = display_name.replace('_', ' ')
        pcoll_enum.append((short_path, os.path.splitext(display_name)[0], "", thumb.icon_id, i+1))
        path_list.append(short_path)
    
    #set pcoll
    if len(pcoll_enum) <= 1:
        empty_thumb = load_thumbnail('pcoll_empty', pcoll)
        pcoll_enum = [('none', '', '', empty_thumb.icon_id, 0)]

    pcoll['pcoll_{}'.format(pcoll_categ)] = pcoll_enum

    #set other props
    sett['previews_list_{}'.format(pcoll_categ)] = path_list    
    pcoll['previews_dir_{}'.format(pcoll_categ)] = search_dir

def outfit_subcateg_skip(sett, full_path):
    '''
    special function to skip items whose boolean filters are off in the ui
    '''
    fn = os.path.basename(full_path)
    name = os.path.splitext(fn)[0]
    suffix = ('_HI', '_NI', '_CI', '_HO', '_NO', '_CO')
    if not name.endswith(suffix):
        return False
    
    season_dict = {sett.summer_toggle: 'H', sett.normal_toggle: 'N', sett.winter_toggle: 'C'}
    env_dict = {sett.inside_toggle: 'I', sett.outside_toggle: 'O'}

    if all(k for k in season_dict) and all(k for k in env_dict):
        return False

    for bool, suffix in season_dict.items():
        if bool == False and name[-2] == suffix:
            return True

    for bool, suffix in env_dict.items():
        if bool == False and name[-1] == suffix:
            return True    
    
    return False


