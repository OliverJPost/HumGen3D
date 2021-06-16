from pathlib import Path
from ... core.content.HG_CONTENT_PACKS import cpacks_refresh
import os
import json
from ... core.HG_PCOLL import get_pcoll_enum_items, list_pcoll_files_in_dir, _get_categ_and_subcateg_dirs, refresh_pcoll
from ... features.common.HG_COMMON_FUNC import get_prefs
from ... extern.blendfile import open_blend
import bpy #type: ignore
from zipfile import ZipFile

class HG_OT_CREATE_CPACK(bpy.types.Operator):
    bl_idname = "hg3d.create_cpack"
    bl_label = "Create content pack"
    bl_description = """Creates a pack and changes the preferences window to the editing UI"""
        
    def execute(self, context):
        pref = get_prefs()
        name = pref.cpack_name
        
        cpack_folder = os.path.join(pref.filepath, 'content_packs')
        data = {
            "config": {"pack_name": name,
                        "creator": "Your Name",
                        "pack_version": (1,0),
                        "weblink": "https://www.[Your website].com"
                        }
                }
        with open(os.path.join(cpack_folder, name + '.json'), 'w') as f:
            json.dump(data, f, indent = 4)
        
        pref.editing_cpack = name
        return {"FINISHED"}


class HG_OT_EDIT_CPACK(bpy.types.Operator):
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
        pref.cpack_creator = item.creator
        pref.cpack_weblink = item.weblink
        build_content_list(self, context)
        return {"FINISHED"}

class HG_OT_EXIT_CPACK_EDIT(bpy.types.Operator):
    bl_idname = "hg3d.exit_cpack_edit"
    bl_label = "Exit the editing UI"
    bl_description = """Changes the window back to the HumGen preferences"""
    
    def execute(self, context):
        pref = get_prefs()

        col = context.scene.custom_content_col
        col.clear()
        pref.editing_cpack = ''
        return {"FINISHED"}

#TODO implement save to json and progress bar
class HG_OT_SAVE_CPACK(bpy.types.Operator):
    bl_idname = "hg3d.save_cpack"
    bl_label = "Save this pack"
    bl_description = """Saves this content pack"""
    
    export: bpy.props.BoolProperty()
    
    def execute(self, context):
        pref = get_prefs()
        
        cpack = context.scene.contentpacks_col[pref.cpack_name]
        content_to_export = [c for c in context.scene.custom_content_col if c.include]
        
        export_path_set, categ_set = self._build_export_set(pref, content_to_export)
        
        self._write_json_file(pref, cpack, export_path_set, categ_set)
            
        if self.export:
           failed_exports = self._zip_files(pref, export_path_set, cpack.json_path)
           print('Failed exports ', failed_exports)
        
        content_to_export.clear()
        pref.editing_cpack = ''
        return {"FINISHED"}

    def _write_json_file(self, pref, cpack, export_path_set, categ_set):
        with open(cpack.json_path, 'r') as f:
            data = json.load(f)
        data['config'] = {
            "pack_name": pref.cpack_name,
            "creator": pref.cpack_creator,
            "pack_version": [pref.cpack_version, pref.cpack_subversion], #TODO add auto sync from existing jsons
            "weblink": pref.cpack_weblink       
        }
        data["categs"] = self._build_categ_dict(categ_set, cpack.pack_name)
        data["files"] =  list(export_path_set)
        
        with open(cpack.json_path, 'w') as f:       
            json.dump(data, f, indent = 4)
            print('json data', data)

    def _build_export_set(self, pref, items_to_export) -> tuple[set, set]:
        export_list = []
        categ_list = []
        for export_item in filter(lambda i: i.include, items_to_export):
            item_path = export_item.path
            item_categ = export_item.categ
            export_list.append(item_path)
            if item_path.startswith('C'):
                print('ALERT', item_path, 'starts with C')
            if item_categ != 'shapekeys':
                thumb_path = os.path.splitext(item_path)[0] + '.jpg'
                if os.path.isfile(pref.filepath + thumb_path):
                    export_list.append(thumb_path)
            
            export_list.extend(self._find_associated_files(pref.filepath + item_path, item_categ))
            categ_list.extend(export_item.categ)
        
        return set(export_list), set(categ_list)

    #TODO implement compression
    def _zip_files(self, pref, export_paths, json_path) -> int:
        failed_exports = 0
        
        zip = ZipFile(r'C:\Users\Ole\sample19.zip', 'w')
        zip.write(json_path, os.path.relpath(json_path, pref.filepath))
        for relative_path in export_paths:
            full_path = pref.filepath + relative_path           
            try:
                zip.write(full_path, relative_path)
            except FileNotFoundError:
                print('Could not find file ', full_path)
                failed_exports += 1
        zip.close()
        
        return failed_exports
        
        
    def _find_associated_files(self, filepath, categ) -> set:       
        if not categ in ['outfits', 'footwear']:
            return []
        
        associated_files = []
        bf = open_blend(filepath)
        img_blocks = bf.find_blocks_from_code(b'IM')
        for block in img_blocks:
            image_path = block.get(b'name')
            associated_files.append(image_path)
        bf.close()
        
        associated_files = map(lambda x: self._correct_relative_path(x, categ), associated_files)
        
        return list(associated_files)
    
    def _correct_relative_path(self, path, categ) -> str:
        if os.path.isfile(path):
            print('Returning right away ', path)
            return os.path.relpath(get_prefs().filepath, path)
        path = path.replace('/', '\\') #unify slashes
        path_split = path.split('\\') #split path into list
        path_split = list(filter(lambda x: x != '..', path_split)) #remove double dots in list
        path_split.insert(0, categ)
        path = os.path.join(*path_split)
        print('returning corrected', path)
        return path

    def _build_categ_dict(self, categ_set, pack_name) -> dict:
        categ_dict = {
            'humans': 'starting_humans' in categ_set,
            'human_textures': 'textures' in categ_set,
            'shapekeys': 'shapekeys' in categ_set,
            'hair': 'hairstyles' in categ_set,
            'poses': 'poses' in categ_set,
            'clothes': 'outfits' in categ_set,
            'footwear': 'footwear' in categ_set,
            'expressions': pack_name == 'Base Humans'
        }
        
        return categ_dict
        
def build_content_list(self, context):
    pref = get_prefs()
    sett = context.scene.HG3D

    col = context.scene.custom_content_col
    col.clear()

    cpack = context.scene.contentpacks_col[pref.cpack_name]
    with open(os.path.join(pref.filepath, cpack.json_path), 'r') as f:
        json_data = json.load(f)    
    if 'files' in json_data:
        current_file_set = set(map(lambda x : str(Path(x)), json_data['files']))
    else:
        current_file_set = []
    
    other_cpacks_content = []
    for item in context.scene.contentpacks_col:
        if item.pack_name == pref.cpack_name:
            continue

        try:
            with open(item.json_path, 'r') as f:
                json_data = json.load(f)       
                other_cpacks_content.extend(json_data['files'])    
        except (KeyError, FileNotFoundError):
            print('failed', item.pack_name, item.json_path)
        
    
    other_cpacks_content_set = set(map(lambda x : str(Path(x)), other_cpacks_content))
        
    pcoll_dict = {
        'starting_humans': 'humans',
        'texture_sets': 'textures',
        'shapekeys': 'humans',
        'hairstyles': 'hair',
        'poses': 'poses',
        'outfits': 'outfit',
        'footwear': 'footwear'
    }

    for categ in pcoll_dict:
        refresh_pcoll(self, context, pcoll_dict[categ], ignore_genders = True) 
        for content_item in get_pcoll_enum_items(self, context, pcoll_dict[categ]):
            _add_to_collection(col, current_file_set, categ, content_item, other_cpacks_content_set)

def _add_to_collection(col, current_file_set, categ, content_item, other_cpacks_content_set):
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
    corrected_path = os.path.normpath(content_item[0][1:])
    item.include = corrected_path in current_file_set
    if not item.include:
        item.existing_content = corrected_path in other_cpacks_content_set
        
    item.icon_value = content_item[3]
    if 'female' in dirname:
        item.gender = 'female'
    elif 'male' in dirname:
        item.gender = 'male'
       
def convert_loose_content_to_cpack():
    pass

def export_cpack():
    pass

class CUSTOM_CONTENT_ITEM(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    path: bpy.props.StringProperty()
    icon_value: bpy.props.IntProperty()
    include: bpy.props.BoolProperty(default = False)
    gender: bpy.props.StringProperty(default= 'none')
    categ: bpy.props.StringProperty()
    existing_content: bpy.props.BoolProperty()