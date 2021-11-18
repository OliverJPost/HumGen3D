"""The cpack exporter works by adding all content items to the 
scene.custom_content_col when the user clicks the edit content pack icon.

In the editing UI the user can interact with these collection items. The
collection does not update during editing, the UI just filters what part of
the collection is hidden

When saving/exporting the cpack, each item that has include = True will 
be saved/exported
"""

import json
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import bpy  # type: ignore

from ...core.content.HG_CONTENT_PACKS import cpacks_refresh
from ...core.HG_PCOLL import get_pcoll_enum_items, refresh_pcoll
from ...extern.blendfile import open_blend
from ...features.common.HG_COMMON_FUNC import (ShowMessageBox, get_prefs,
                                               hg_log, show_message)


class HG_OT_CREATE_CPACK(bpy.types.Operator):
    """Adds a new json file it the content_packs folder and opens the cpack
    editing UI for the user to start creating this pack.
    
    Operator type:
        Content pack creation
    
    Prereq:
        pref.cpack_name given
    """
    bl_idname = "hg3d.create_cpack"
    bl_label = "Create custom content pack"
    bl_description = """Creates a pack and changes the preferences window to the editing UI"""

    def invoke(self, context, event):
        #confirmation checkbox
        return context.window_manager.invoke_confirm(self, event)
    
    def execute(self, context):
        pref = get_prefs()
        cpack_name = pref.cpack_name
        
        cpack_folder = os.path.join(pref.filepath, 'content_packs')

        self._create_cpack_json(cpack_name, cpack_folder)
        
        pref.editing_cpack = cpack_name
             
        cpacks_refresh(self, context)
        
        build_content_collection(self, context)
        return {"FINISHED"}

    def _create_cpack_json(self, name, cpack_folder):
        """Creates a new json file as content pack, adding the basic info to it

        Args:
            name (str): name of new content pack
            cpack_folder (Path): path to save the json to
        """
        data = {
            "config": {"pack_name": name,
                        "creator": "Your Name",
                        "pack_version": (1,0),
                        "weblink": "https://www.[Your website].com"
                        }
                }
        with open(os.path.join(cpack_folder, name + '.json'), 'w') as f:
            json.dump(data, f, indent = 4)

class HG_OT_EDIT_CPACK(bpy.types.Operator):
    """Edit the passed content pack
    
    Operator type:
        Content pack creation
        
    Prereq:
        item_name passed
        item_name is a correct cpack item.name in the cpack collection
    """
    bl_idname = "hg3d.edit_cpack"
    bl_label = "Edit content pack"
    bl_description = """Changes the preferences window to the editing UI"""
    
    item_name: bpy.props.StringProperty()
    
    def execute(self, context):
        pref = get_prefs()
        pref.editing_cpack = self.item_name  
        pref.cpack_name = self.item_name
        
        item = next(item for item in context.scene.contentpacks_col 
                    if item.name == self.item_name)
        
        #set the metadata input fields, cpack_name is already set
        pref.cpack_creator = item.creator
        pref.cpack_weblink = item.weblink
        pref.cpack_version, pref.cpack_subversion = tuple(item.pack_version)
        
        build_content_collection(self, context)
        
        return {"FINISHED"}

class HG_OT_EXIT_CPACK_EDIT(bpy.types.Operator):
    """Returns to the standard HumGen preferences without saving this cpack
    
    Operator type:
        Content pack creation
        
    Prereq:
        User was in cpack edit mode
    """
    bl_idname = "hg3d.exit_cpack_edit"
    bl_label = "Exit the editing UI without saving changes"
    bl_description = """Changes the window back to the HumGen preferences"""

    def invoke(self, context, event):
        #confirmation checkbox
        return context.window_manager.invoke_confirm(self, event)
    
    def execute(self, context):
        pref = get_prefs()
        col = context.scene.custom_content_col
        
        col.clear()
        pref.editing_cpack = ''
        return {"FINISHED"}

class HG_OT_SAVE_CPACK(bpy.types.Operator):
    bl_idname = "hg3d.save_cpack"
    bl_label = "Save this pack"
    bl_description = """Saves this content pack"""
    
    export: bpy.props.BoolProperty()


    def invoke(self, context, event):
        if self.export and not get_prefs().cpack_export_folder:
            ShowMessageBox(message = 'No export path selected')
            return {"CANCELLED"}
        #confirmation checkbox
        return context.window_manager.invoke_confirm(self, event)
    
    def execute(self, context):
        pref = get_prefs()
        
        cpack = context.scene.contentpacks_col[pref.cpack_name]
        content_to_export = [c for c in context.scene.custom_content_col 
                             if c.include]
        
        export_path_set, categ_set = self._build_export_set(pref, content_to_export)
        
        self._write_json_file(pref, cpack, export_path_set, categ_set)
            
        if self.export:
           self._zip_files(pref, export_path_set, cpack.json_path, cpack)
           
        content_to_export.clear()
        pref.editing_cpack = ''
        cpacks_refresh(self, context)
        if self.export:
            show_message(self, "Succesfully exported content pack to " + pref.cpack_export_folder)
        else:
            show_message(self, "Succesfully saved content pack")
        return {"FINISHED"}

    def _build_export_set(self, pref, items_to_export) -> 'tuple[set, set]':
        """Returns two sets with the filepaths of the items to export and the
        categories of the items that will be exported

        Args:
            pref (AddonPreferences): HumGen preferences
            items_to_export (CollectionProperty): collection of all the items 
            that need to be exported: CUSTOM_CONTENT_ITEM

        Returns:
            tuple[set, set]: 
                set: set of all RELATIVE paths of items to be exported
                set: set of category names that will be exported
        """
        export_list = []
        categ_list = []
        for export_item in filter(lambda i: i.include, items_to_export):
            item_path  = export_item.path
            item_categ = export_item.categ
            
            export_list.append(item_path)
            if item_categ != 'shapekeys':
                thumb_path = os.path.splitext(item_path)[0] + '.jpg'
                if os.path.isfile(pref.filepath + thumb_path):
                    export_list.append(thumb_path)
    
            associated_files = self._find_associated_files(pref.filepath + item_path, item_categ)        
            export_list.extend(associated_files)
            categ_list.append(export_item.categ)
        
        return set(export_list), set(categ_list)

    def _write_json_file(self, pref, cpack, export_path_set, categ_set):
        """Write the metadata of this pack to the cpack json file

        Args:
            pref (AddonPreferences): HumGen preferences
            cpack (CollectionProperty item): scene.contentpacks_col item
            export_path_set (set): set of all paths of files to export
            categ_set (set): set of names of categories that the exported items
                are in 
        """
        with open(cpack.json_path, 'r') as f:
            data = json.load(f)
        data['config'] = {
            "pack_name": pref.cpack_name,
            "creator": pref.cpack_creator,
            "pack_version": [pref.cpack_version, pref.cpack_subversion], 
            "weblink": pref.cpack_weblink       
        }
        data["categs"] = self._build_categ_dict(categ_set, cpack.pack_name)
        data["files"] =  list(export_path_set)
        
        with open(cpack.json_path, 'w') as f:       
            json.dump(data, f, indent = 4)

    def _build_categ_dict(self, categ_set, pack_name) -> dict:
        """Builds a dictionary of what kind of category content items are 
        included in this cpack

        Args:
            categ_set (set): set of category names that are included in this cpack
            pack_name (str): name of this content pack

        Returns:
            dict: 
                key (str): name of content category
                value (bool): True if included in this cpack 
        """
        categ_dict = {
            'humans': 'starting_humans' in categ_set,
            'human_textures': 'texture_sets' in categ_set,
            'shapekeys': 'shapekeys' in categ_set,
            'hair': 'hairstyles' in categ_set or 'face_hair' in categ_set,
            'poses': 'poses' in categ_set,
            'clothes': 'outfits' in categ_set,
            'footwear': 'footwear' in categ_set,
            'expressions': pack_name == 'Base Humans'
        }
        
        return categ_dict
      
    def _zip_files(self, pref, export_paths, json_path, cpack):
        """Zip all the files from the export_paths set to a zip file in the 
        user given directory

        Args:
            pref (AddonPreferences): HumGen preferencs
            export_paths (set): set of paths to export
            json_path (Path): path of the cpack json file
            cpack (CollecitonProperty item): scene.contentpacks_col item
        """
        #build export name to the template of: HG_CP_CPACKNAME_Vx_x
        export_name = (
            'HG_CP_' 
            + cpack.name.replace(' ', '_') 
            + '_V{}_{}'.format(pref.cpack_version, pref.cpack_subversion))

        failed_exports = 0
        zip_path = bpy.path.abspath(pref.cpack_export_folder) + export_name + '.zip'
        if get_prefs().compress_zip:
            try:
                zip = ZipFile(zip_path, 'w', ZIP_DEFLATED)
            except Exception as e:
                hg_log('Error while attempting zip compression', e, level= 'WARNING')
                zip = ZipFile(zip_path, 'w')
        else:
            zip = ZipFile(zip_path, 'w')
        zip.write(json_path, os.path.relpath(json_path, pref.filepath))
        for relative_path in export_paths:
            full_path = pref.filepath + relative_path           
            try:
                zip.write(full_path, relative_path)
            except FileNotFoundError:
                hg_log('Could not find file ', full_path, level = 'WARNING')
                failed_exports += 1
        zip.close()
        
        hg_log('Failed exports ', failed_exports, level = 'WARNING')
          
    def _find_associated_files(self, filepath, categ) -> set:      
        """Create a set of relative paths of files that are associated with the
        passed files. For example linked textures and hair collection files

        Args:
            filepath (Path): path of the file to find associated files for
            categ (str): category of this content item

        Returns:
            set: relative filepaths of associated files
        """
         
        associated_files = []
        if categ in ['outfits', 'footwear']:
            #find linked textures for clothing and shoe items
            bf = open_blend(filepath)
            img_blocks = bf.find_blocks_from_code(b'IM')
            for block in img_blocks:
                image_path = block.get(b'name')
                associated_files.append(image_path)
            bf.close()
        if categ in ['hairstyles', 'face_hair']:
            #find hair collection blendfile for hairstyles
            with open(filepath, 'r') as f:
                data = json.load(f)
                blendfile = data['blend_file']
                folder = 'head' if categ == 'hairstyles' else 'face_hair'
                associated_files.append(str(Path(f'/hair/{folder}/{blendfile}')))
        
        mapped_associated_files = map(lambda x: self._correct_relative_path(x, categ), associated_files)

        returnv = list(mapped_associated_files)
        return returnv
    
    def _correct_relative_path(self, path, categ) -> str:
        """Deals with Blender //..\..\ relative paths and converts any absolute
        paths to relative paths

        Args:
            path (str): path to correct relativity for
            categ (str): name of category of this content item

        Returns:
            str: corrected path (relative)
        """
        if os.path.isfile(path):
            #return the filepath as relative if it's an absolute path
            return os.path.relpath(path, get_prefs().filepath)
        
        path = path.replace('/', '\\') #unifies slashes
        path_split = path.split('\\') #splits path into list
        path_split = list(filter(lambda x: x != '..', path_split)) #removes double dots in list
        if categ not in ('hairstyles', 'face_hair'):
            path_split.insert(0, categ) #adds the category name to the start of the path
        path = os.path.join(*path_split) #rebuilds the path from the path_split

        return path

def build_content_collection(self, context):
    pref = get_prefs()
    sett = context.scene.HG3D
    sett.update_exception = True
    
    col = context.scene.custom_content_col
    col.clear()

    current_file_set = _get_current_file_set(context, pref)

    other_cpacks_content_set = _get_other_content_set(context, pref)
    
    pcoll_dict = {
        'starting_humans': 'humans',
        'texture_sets': 'textures',
        'hairstyles': 'hair',
        'face_hair': 'face_hair',
        'poses': 'poses',
        'outfits': 'outfit',
        'footwear': 'footwear'
    }

    _iterate_items_to_collection(
        self,
        context,
        pref,
        col,
        current_file_set,
        other_cpacks_content_set,
        pcoll_dict
    )
        
    sett.update_exception = False


def _get_current_file_set(context, pref):
    cpack = context.scene.contentpacks_col[pref.cpack_name]
    with open(os.path.join(pref.filepath, cpack.json_path), 'r') as f:
        json_data = json.load(f)    
    if 'files' in json_data:
        current_file_set = set(map(os.path.normpath, json_data['files']))
    else:
        current_file_set = []
    return current_file_set

def _get_other_content_set(context, pref):
    other_cpacks_content = []
    for item in context.scene.contentpacks_col:
        if item.pack_name == pref.cpack_name:
            continue
        try:
            with open(item.json_path, 'r') as f:
                json_data = json.load(f)       
                other_cpacks_content.extend(json_data['files'])    
        except (KeyError, FileNotFoundError):
            pass
      
    other_cpacks_content_set = set(map(os.path.normpath, other_cpacks_content))
    return other_cpacks_content_set

def _iterate_items_to_collection(self, context, pref, col, current_file_set,
                                 other_cpacks_content_set, pcoll_dict):
    """Iterates trough all categories and adds their items to the custom_content
    collection. Separate procress for shapekeys, since those don't have an 
    associated preview collection

    Args:
        context ([type]): [description]
        pref (AddonPreferences): HumGen preferences
        col (CollectionProperty): collection to add the content items to
        current_file_set (set): set of files which are already in this cpack
        other_cpacks_content_set (set): set of files that are already in other
            content packs
        pcoll_dict (dict): 
            key (str): name of custom_content item
            value (str): name of corresponding preview collection
    """
    #add everything except shapekeys
    for categ in pcoll_dict:
        refresh_pcoll(self, context, pcoll_dict[categ], ignore_genders = True) 
        
        for content_item_enum in get_pcoll_enum_items(self, context, pcoll_dict[categ]):
            if categ == 'starting_humans' and 'shapekeys' in content_item_enum[0]:
                continue
            
            _add_to_collection(
                col,
                current_file_set,
                categ,
                content_item_enum,
                other_cpacks_content_set
            )
    
    #add shapekeys
    path_to_walk = pref.filepath + str(Path('/models/shapekeys'))
    for _, _, filenames in os.walk(path_to_walk):
        for fn in filenames:
            if not fn.endswith('.blend'):
                continue
            
            relative_path = str(Path(f'/models/shapekeys/{fn}'))
            filename_only = os.path.splitext(fn)[0]
            
            content_item_enum = [
                relative_path,
                filename_only,
                '',
                0
            ]
            
            _add_to_collection(
                col,
                current_file_set,
                'shapekeys',
                content_item_enum,
                other_cpacks_content_set
            )

def _add_to_collection(col, current_file_set, categ, content_item, other_cpacks_content_set):
    """Adds the passed item to the custom_content collection

    Args:
        col (CollectionProperty): collection to add the item to
        current_file_set (set): set of files that are already in this cpack and 
            should therefore be set to item.include = True
        categ (str): category of this content item
        content_item (list (enum)): enum list coming from the preview collection, containing:
            str: relative path of this item
            str: name of this item
            str: description (almost always empty string, not used by this function)
            int: custom icon as icon_id
            int: enumerator number (not used by this function)
        other_cpacks_content_set (set): set of content that's already in other 
            content packs and should therefore be hidden by default
    """
    dirname = os.path.dirname(content_item[0].lower())

    skip = (
                content_item[0] == 'none'
                or (categ == 'textures' and 'male' not in dirname) #TODO better implementation
            )
    if skip: #skip 'click here to select' item
        return
            
    item = col.add()
    item.name = content_item[1]
    item.categ = categ
    item.path = content_item[0]
    corrected_path = os.path.normpath(content_item[0])
    item.include = (corrected_path in current_file_set 
                    or corrected_path[1:] in current_file_set #compatibility with old path saving
                )
    if not item.include:
        item.existing_content = (corrected_path in other_cpacks_content_set 
                                 or corrected_path[1:] in other_cpacks_content_set #compatibility with old path saving
                                 )
        
    item.icon_value = content_item[3]
    if 'female' in dirname:
        item.gender = 'female'
    elif 'male' in dirname:
        item.gender = 'male'
       
def content_callback(self, context):
    """Gets called every time a content item's include boolean is changed,
    handles the newly_added and removed lists
    """
    
    if context.scene.HG3D.update_exception:
        return # Don't update when building the list for the first time
    
    if self.include:
        self.newly_added = False if self.removed else True
        self.removed = False
    else:
        self.removed = False if self.newly_added else True
        self.newly_added = False

class CUSTOM_CONTENT_ITEM(bpy.types.PropertyGroup):
    """Item in scene.custom_content_col that represents a content item for 
    Human Generator
    """
    name: bpy.props.StringProperty()
    path: bpy.props.StringProperty() #relative path of this item
    icon_value: bpy.props.IntProperty() #custom icon icon_id
    
    #determines if this item will be exported/included in this pack
    include: bpy.props.BoolProperty(default=False, update=content_callback)
    gender: bpy.props.StringProperty(default= 'none') #set to male or female
    categ: bpy.props.StringProperty() #category of this content item
    existing_content: bpy.props.BoolProperty() #if this item is already in another cpack
    newly_added: bpy.props.BoolProperty() #if it's been added in this editing session
    removed: bpy.props.BoolProperty() #if it's been removed in this editing session
