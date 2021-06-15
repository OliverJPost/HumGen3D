from ... core.content.HG_CONTENT_PACKS import cpacks_refresh
import os
import json
from ... core.HG_PCOLL import get_pcoll_enum_items, list_pcoll_files_in_dir, _get_categ_and_subcateg_dirs, refresh_pcoll
from ... features.common.HG_COMMON_FUNC import get_prefs
import bpy #type: ignore

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
        
        return {"FINISHED"}

class HG_OT_EXIT_CPACK_EDIT(bpy.types.Operator):
    bl_idname = "hg3d.exit_cpack_edit"
    bl_label = "Exit the editing UI"
    bl_description = """Changes the window back to the HumGen preferences"""
    
    def execute(self, context):
        pref = get_prefs()
        #cpacks_refresh(self, context)
        pref.editing_cpack = ''
        return {"FINISHED"}
  
def build_content_list(self, context):
    pref = get_prefs()
    sett = context.scene.HG3D
    
    tab = pref.custom_content_categ
    categ_dict = {
        'starting_humans': 'humans',
        'texture_sets': 'textures',
        'shapekeys': 'humans',
        'hairstyles': 'hair',
        'poses': 'poses',
        'outfits': 'outfit',
        'footwear': 'footwear'
    }
    categ = categ_dict[tab]
    
    refresh_pcoll(self, context, categ, ignore_genders = True)
    
    
    col = context.scene.custom_content_col
    col.clear()
    for content_item in get_pcoll_enum_items(self, context, categ):
        dirname = os.path.dirname(content_item[0].lower())
        skip = (
            content_item[0] == 'none'
            or (categ == 'textures' and 'male' not in dirname) #TODO better implementation
        )
        if skip: #skip 'click here to select' item
            continue
        
        item = col.add()
        item.name = content_item[1]
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
    icon_value: bpy.props.IntProperty()
    include: bpy.props.BoolProperty(default = False)
    gender: bpy.props.StringProperty(default= 'none')
    