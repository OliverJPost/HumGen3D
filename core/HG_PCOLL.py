"""
Functions related to the preview_collections of human generator, including 
population of them
"""

import os
from pathlib import Path

import bpy  # type: ignore

from ..features.common.HG_COMMON_FUNC import (HumGenException, find_human, get_addon_root,
                                              get_prefs, hg_log)

preview_collections = {} #global dictionary of all pcolls

def get_pcoll_enum_items(self, context, pcoll_type) -> list:
    """Returns an enum of the items in the passed preview collection

    Args:
        pcoll_type (str): name of preview collection

    Returns:
        list: enum with items for this preview collection
    """
    pcoll = preview_collections.get('pcoll_{}'.format(pcoll_type))
    if not pcoll:
        return [('none', 'Reload category below', '', 0),]
    
    return pcoll['pcoll_{}'.format(pcoll_type)]  

def refresh_pcoll(self, context, pcoll_name, ignore_genders = False, hg_rig = None):
    """Refresh the items of this preview

    Args:
        pcoll_name (str): name of the preview collection to refresh
    """
    sett = context.scene.HG3D
    _check_for_HumGen_filepath_issues(self)

    sett.load_exception = False if pcoll_name == 'poses' else True
        
    _populate_pcoll(self, context, pcoll_name, ignore_genders, hg_rig = hg_rig)
    sett['pcoll_{}'.format(pcoll_name)] = 'none' #set the preview collection to
                                                #the 'click here to select' item    
    
    sett.load_exception = False

def _check_for_HumGen_filepath_issues(self):
    pref = get_prefs()
    if not pref.filepath:
        raise HumGenException("No filepath selected in HumGen preferences.")
    base_humans_path = os.path.join(
        pref.filepath,
        'content_packs',
        'Base_Humans.json')

    
    base_content = os.path.exists(base_humans_path)
    
    if not base_content:
        raise HumGenException("Filepath selected, but no humans found in path")

def _populate_pcoll(self, context, pcoll_categ, ignore_genders, hg_rig = None):
    """Populates the preview collection enum list with blend file filepaths and 
    icons

    Args:
        pcoll_categ (str): name of preview collection
    """
    sett = context.scene.HG3D
    pref = get_prefs()

    #create variables if they dont exist in settings
    if not 'previews_dir_{}'.format(pcoll_categ) in sett:
        sett['previews_dir_{}'.format(pcoll_categ)] = ''
    #clear previews list        
    sett['previews_list_{}'.format(pcoll_categ)] = []
    
    # find category and subcategory in order to determine the dir to search
    if not hg_rig:
        hg_rig = find_human(context.active_object)
        
    gender = ('' if ignore_genders
              else sett.gender if pcoll_categ == 'humans' 
              else hg_rig.HG.gender)
    categ_dir, subcateg_dir = _get_categ_and_subcateg_dirs(pcoll_categ, sett, gender)
    
    pcoll_full_dir = str(pref.filepath) + str(Path('/{}/'.format(categ_dir)))
    if subcateg_dir != 'All':
        pcoll_full_dir = pcoll_full_dir + str(Path('/{}/'.format(subcateg_dir)))
   
    file_paths = list_pcoll_files_in_dir(pcoll_full_dir, pcoll_categ)    
    
    path_list = []  
    # I don't know why, but putting this double fixes a recurring issue where
    # pcoll equels None
    pcoll = preview_collections.setdefault("pcoll_{}".format(pcoll_categ))
    pcoll = preview_collections.setdefault("pcoll_{}".format(pcoll_categ))
    
    none_thumb = _load_thumbnail('pcoll_placeholder', pcoll)
    pcoll_enum = [('none', '', '', none_thumb.icon_id, 0)]
    for i, full_path in enumerate(file_paths):            
        _add_file_to_pcoll(pcoll_categ, sett, pref, pcoll, pcoll_enum,
                           path_list, i, full_path)
    
    if len(pcoll_enum) <= 1:
        empty_thumb = _load_thumbnail('pcoll_empty', pcoll)
        pcoll_enum = [('none', '', '', empty_thumb.icon_id, 0)]

    pcoll['pcoll_{}'.format(pcoll_categ)] = pcoll_enum
    sett['previews_list_{}'.format(pcoll_categ)] = path_list    
    pcoll['previews_dir_{}'.format(pcoll_categ)] = pcoll_full_dir

def _get_categ_and_subcateg_dirs(pcoll_categ, sett, gender) -> 'tuple[str, str]':
    """Gets the directory name of the preview collection category and of the 
    user selected subcategory

    Args:
        pcoll_categ (str): name of preview collection
        sett (ProeprtyGRoup): HumGen props
        gender (str): gender to find pcoll items for

    Returns:
        tuple[str, str]: 
            str: directory of preview collection items. Relative from HumGen filepath
            str: subdirectory, based on user selection. Relative from cateG_dir
    """
    dir_categ_dict = {
        'poses'      : 'poses',
        'outfit'     : 'outfits/{}'.format(gender),
        'hair'       : 'hair/head/{}'.format(gender),
        'face_hair'  : 'hair/face_hair',
        'expressions': 'expressions',
        'humans'     : 'models/{}'.format(gender),
        'footwear'   : 'footwear/{}'.format(gender),
        'patterns'   : 'patterns',
        'textures'   : 'textures/{}'.format(gender)
        }
    categ_dir = dir_categ_dict[pcoll_categ]
    dir_sub_dict = {
        'poses'      : sett.pose_sub,
        'outfit'     : sett.outfit_sub,
        'hair'       : sett.hair_sub,
        'face_hair'  : sett.face_hair_sub,
        'expressions': sett.expressions_sub,
        'humans'     : 'All',
        'footwear'   : sett.footwear_sub,
        'patterns'   : sett.patterns_sub,
        'textures'   : sett.texture_library
        }
    subcateg_dir = dir_sub_dict[pcoll_categ]
    
    return categ_dir, subcateg_dir

def list_pcoll_files_in_dir(dir, pcoll_type) -> list:    
    """Gets a list of files in dir with certain extension. Extension depends on
    the passed pcoll_type. Also handles search terms the users entered in a
    searchbox

    Args:
        dir (dir): Directory to search in
        pcoll_type (str): name of preview collection to search items for

    Returns:
        list: list of file paths in dir of certain extension
    """
    sett = bpy.context.scene.HG3D
    
    search_term = _get_search_term(pcoll_type, sett)

    ext = _get_pcoll_files_extension(pcoll_type)
    
    file_paths = []
    for root, dirs, files in os.walk(dir):
        if pcoll_type == 'textures' and 'PBR' in root:
            continue #don't show textures in PBR folder of texture sets
        
        found_files = [fn for fn in files 
                       if fn.lower().endswith(ext) 
                       and search_term.lower() in fn.lower()
                       ]
        for fn in found_files:
            full_path = os.path.join(root, fn)
            file_paths.append(full_path)          

    hg_log('getting files for {} in {}'.format(pcoll_type, dir), level = 'DEBUG')
    hg_log('found files {}'.format(file_paths), level = 'DEBUG')

    return file_paths

def _get_pcoll_files_extension(pcoll_type) -> str:
    """Gets the filetype extension that belongs to this preview collection.
    
    I.e. pcoll_humans looks for .json and pcoll_outfits looks for .blend

    Args:
        pcoll_type (str): name of preview collection

    Returns:
        str: extension, including dot (i.e. .json)
    """
    ext_dict = {'expressions': '.txt',
                'humans': '.json', #CHECK if still works
                'patterns': '.png',
                'face_hair': '.json',
                'hair': '.json',
                'textures': ('.png', '.tiff', '.tga')
                }
    ext = ext_dict[pcoll_type] if pcoll_type in ext_dict else '.blend'
    return ext

def _load_thumbnail(thumb_name, pcoll) -> list:
    """Loads a thumbnail for this pcoll item

    Args:
        thumb_name (str): name of the thumbnail image, excluding extension
        pcoll (list): preview collection

    Returns:
        list: icon in enumarator
    """
    filepath_thumb = os.path.join(get_addon_root(), 'icons', thumb_name+'.jpg')

    if not pcoll.get(filepath_thumb):
        thumb = pcoll.load(filepath_thumb, filepath_thumb, 'IMAGE')
    else: 
        thumb = pcoll[filepath_thumb]
    
    return thumb


def _add_file_to_pcoll(pcoll_categ, sett, pref, pcoll, pcoll_enum, path_list,
                       i, full_path):
    """Adds the passed file to the given preview collection

    Args:
        pcoll_categ (str)             : name of preview collection to add to
        sett        (PropertyGroup)   : HumGen props
        pref        (AddonPreferences): HumGen preferences
        pcoll       (str)             : internal pcoll name
        pcoll_enum  (list)            : enum of all items in pcoll
        path_list   (list)            : list of all filepaths of items in pcoll
        i           (int)             : index of enumerate of files
        full_path   (Path)            : filepath of item to add to pcoll
    """
    filepath_thumb = os.path.splitext(full_path)[0] + '.jpg' 
    if not pcoll.get(filepath_thumb):
        thumb = pcoll.load(filepath_thumb, filepath_thumb, 'IMAGE')
    else: thumb = pcoll[filepath_thumb]   

    short_path = full_path.replace(str(pref.filepath), '')
    
    display_name = _get_display_name(full_path)
    
    pcoll_enum.append((short_path,
                       os.path.splitext(display_name)[0],
                       "",
                       thumb.icon_id, i+1)
                      )
    path_list.append(short_path)

def _get_display_name(full_path) -> str:
    """Transforms internal name to displayable name

    Args:
        full_path (Path): full path of item to make display name for

    Returns:
        str: display name
    """
    display_name = os.path.basename(full_path)
    for remove_string in ('HG', 'Male', 'Female'):
        display_name = display_name.replace(remove_string, '') 
    display_name = display_name.replace('_', ' ')
    
    return display_name

def _get_search_term(pcoll_type, sett) -> str:
    """Gets the search if the user entered one in the corresponding searchbox
    of this pcoll type

    Args:
        pcoll_type (str): name of preview collection to find search term for
        sett (PropertyGRroup): HumGen props

    Returns:
        str: search term, filenames that include this search term will be loaded
    """
    search_term_dict = {
        'poses'      : sett.search_term_poses,
        'expressions': sett.search_term_expressions,
        'outfit'     : sett.search_term_outfit,
        'patterns'   : sett.search_term_patterns,
        'footwear'   : sett.search_term_footwear
        }

    search_term = (search_term_dict[pcoll_type]
                   if pcoll_type in search_term_dict 
                   else ''
                   )
                   
    return search_term

def get_hg_icon(icon_name) -> int:
    icon_list = preview_collections['hg_icons']
    
    return icon_list[icon_name].icon_id
