"""
Operators and functions used for installing and managing HumGen's content packs

Nomenclature:
Installpack = a collection item that represents a zip file the user has selected. Pressing 'install all packs' unzips these files into the file structure, making them cpacks (content packs)
cpack = Abbreviation of content pack. Represents a collection of items downloaded together and extracted in the HumGen file strucure, forming content to be used in the add-on. Settings and properties stored in a .json file
"""  

from . HG_UPDATE import check_update
import bpy #type: ignore
import os
import json
import shutil
import zipfile
import time
from pathlib import Path
from . HG_PCOLL import preview_collections
from bpy_extras.io_utils import ImportHelper #type: ignore
from . HG_COMMON_FUNC import ShowMessageBox

class HG_UL_INSTALLPACKS(bpy.types.UIList):
    """
    UIList showing cpacks to be installed
    """   

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):      
        alert_dict = {
            'not_cpack': 'Not a content pack',
            'no_json': 'No .json file in pack',
            'incorrect_structure': 'Incorrect file structure',
            'not_zip': 'Not a zip file',
            'already_installed': 'Already installed, delete old pack before installing a new one'
        }
        
        row = layout.row(align = True)
        row.label(text= item.pack_name)#, icon = 'INFO' if item.installed else 'TRASH')
        if item.alert != 'None':
            row.alert = True
            row = row.row()
            row.label(text = alert_dict[item.alert], icon = 'ERROR')

class HG_UL_CONTENTPACKS(bpy.types.UIList):
    """
    UIList showing content packs, including icons on who made the pack, what version it is, what items are included, a weblink and a delete button
    """   
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        hg_icons = preview_collections["hg_icons"]
        header = True if item.name == 'header' else False #header is true only for the first item in the list. This fakes a header for the items in the ui_list
        
        row = layout.row(align = True)
        #name
        row.label(text='Name:' if header else item.pack_name)
        
        subrow = row#.row(align = True) 
        #creator
        if header:
            subrow.label(text = 'Creator:') 
        elif item.creator == 'HumGen':
            subrow.label(text = item.creator, icon_value = hg_icons['HG_icon'].icon_id)
        else:
            subrow.label(text = item.creator, icon = item.icon_name)
        
        #version
        subrow.label(text = 'Version:' if header else '%s.%s'% tuple(item.pack_version))           
        subrow.alignment = 'LEFT'
        pack_version = tuple(item.pack_version)
        req_version = tuple(item.required_version)
        latest_version = tuple(item.latest_version)
        if header:
            subrow.label(text = 'Update info:    ')
        else:
            ud = 0 if pack_version >= req_version and pack_version >= latest_version else 2 if pack_version < req_version else 1

            subrow.alert = True if ud == 2 else False
            vn = '%s.%s'% tuple(item.latest_version if ud == 1 else item.required_version)
            subrow.label(text = 'Up to date     ' if ud == 0 else '{} available'.format(vn) if ud == 1 else '{} required! '.format(vn),
                icon = 'CHECKMARK' if ud == 0 else 'INFO' if ud == 1 else 'ERROR'
                )
            subrow.alert = False
        #section with dots showing what is included in this pack
        icon_dict = {
            'humans': 'humans',
            'human_textures': 'textures',
            'shapekeys': 'body',
            'hair': 'hair',
            'poses': 'pose',
            'clothes': 'clothing',
            'footwear': 'footwear',
            'expressions': 'expression'
            }
            
        for categ, icon in icon_dict.items():
            if header:
                subrow.label(text = '', icon_value = hg_icons[icon].icon_id)
            else:
                subrow.label(text = '', icon = "LAYER_ACTIVE" if item[categ] else 'LAYER_USED')

        subrow.separator()

        #weblink and delete button
        if header:
            for i in range(2):
                subrow.label(text = '', icon = 'BLANK1')
        else:
            subrow.operator("wm.url_open", text="", icon = 'URL').url = item.weblink
            subrow.operator("hg3d.cpackdel", text="", icon = 'TRASH').item_name = item.name

class HG_SELECT_CPACK(bpy.types.Operator, ImportHelper):
    """
    Opens a filebrowser popup, allowing the user to select files. This operator adds them to a collection property, meanwhile checking if any problems arise that mean the pack should not be installed
    """  
    bl_idname = "hg3d.cpackselect"
    bl_label = "Select content pack zips"
    bl_description = "Opens a file browser for you to select the zip files of the content packs you wish to install"

    files: bpy.props.CollectionProperty(
            name="File Path",
            type=bpy.types.OperatorFileListElement,
            )
    directory: bpy.props.StringProperty(
            subtype='DIR_PATH',
            )

    def execute(self, context):
        directory = self.directory
        pref = context.preferences.addons[__package__].preferences

        coll = context.scene.installpacks_col

        if not self.files:
            ShowMessageBox(message = '''No files selected, please select the zip files''')
            return {'FINISHED'}

        #iterate over all the files the user selected in the importhelper popup
        for fn in self.files:
            item = coll.add()
            filepath = os.path.join(directory, fn.name)
            
            item.name = filepath
            item.pack_name = filepath
            
            if not os.path.basename(filepath).startswith('HG_CP'):
                item.alert = 'not_cpack' #return error code if the prefix is not correct
                continue
            
            zf = zipfile.ZipFile(filepath)

            cpack_json_files = [file for file in zf.namelist() if file.startswith('content_packs')]
            if not cpack_json_files:
                item.alert = 'incorrect_structure' #return error code if the content_packs folder is not present or not in the correct place
                continue
            
            try:
                item.json_path = [file for file in cpack_json_files if os.path.splitext(file)[1] == '.json'][0]
            except:
                item.alert = 'no_json' # return error code if no .json file can be found
                continue

            json_folder = str(pref.filepath) + str(Path('/content_packs/'))
            try:
                dirlist = os.listdir(json_folder)
                if [fn for fn in dirlist if os.path.basename(item.json_path) == fn]:
                    item.alert = 'already_installed' #return error code if a .json already exists in the file structure with the same name
                else:
                    item.alert = 'None'
            except:
                item.alert = 'None'
        return {'FINISHED'}

class HG_INSTALL_CPACK(bpy.types.Operator):
    """
    Installs (unzips into file structure) all packs in the installpack collection if they don't have any error codes.
    """  
    bl_idname = "hg3d.cpackinstall"
    bl_label = "Install"
    bl_description = "Refresh the content pack list"
    
    _timer = None
    
    def execute(self,context):
        self.pref = context.preferences.addons[__package__].preferences
        self.files = [file for file in context.scene.installpacks_col if file.alert == 'None']
        pref = self.pref
        pref.installing = True
        pref.file_current = 1
        pref.file_all = len(self.files)

        for zip_path in self.files:
            self.unzip_file(zip_path)

        coll = context.scene.installpacks_col
        coll.clear()
        try:
            cpacks_refresh(self, context)
        except:
            pass

        return {'FINISHED'}

    def unzip_file(self, zip_path):
        print('starting unzip', zipfile)
        zf = zipfile.ZipFile(zip_path.name)

        file_list = [fn for fn in zf.namelist() if not fn.endswith('/')] 
        file_dict = {'files': file_list}
        
        filepath = self.pref.filepath

        zf.extractall(path = filepath)

        #adds a dictionary to the json file with all filenames of files in the content pack. This will be used by the HG_DELETE_CPACK operator
        json_path = filepath + str(Path(zip_path.json_path))
        with open(json_path) as f:
            data = json.load(f)
        data.update(file_dict)
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=4,)



class HG_CONTENT_PACK(bpy.types.PropertyGroup):
    """
    Properties of the content pack
    """
    pack_name: bpy.props.StringProperty(
        name='Content Pack Name',
        description="",
        default= '',
        )  
    creator: bpy.props.StringProperty()
    pack_version: bpy.props.IntVectorProperty(default = (0,0), size = 2)
    weblink: bpy.props.StringProperty()
    icon_name: bpy.props.StringProperty(default = 'COMMUNITY')

    #booleans for showing in the UI what categories are in this pack
    humans: bpy.props.BoolProperty(default = False)
    human_textures: bpy.props.BoolProperty(default = False)
    shapekeys: bpy.props.BoolProperty(default = False)
    hair: bpy.props.BoolProperty(default = False)
    poses: bpy.props.BoolProperty(default = False)
    clothes: bpy.props.BoolProperty(default = False)
    footwear: bpy.props.BoolProperty(default = False)
    expressions: bpy.props.BoolProperty(default = False)

    json_path: bpy.props.StringProperty()
    required_version: bpy.props.IntVectorProperty(default = (0,0), size = 2)
    latest_version: bpy.props.IntVectorProperty(default = (0,0), size = 2)

class HG_INSTALLPACK(bpy.types.PropertyGroup):
    """
    Properties of the installpack representation of the selected zip files
    """
    pack_name: bpy.props.StringProperty(
        name='Content Pack Name',
        description="",
        default= '',
        )  
    json_path: bpy.props.StringProperty()
    installed: bpy.props.BoolProperty(default = False)
    alert: bpy.props.EnumProperty(
        name="posing",
        description="",
        items = [
                ("None", "None", "", 0),
                ("not_cpack", "Not a content pack", "", 1),
                ("incorrect_structure", "Incorrect zip method", "", 2),
                ("no_json", "Doesn't contain .json file", "", 3),
                ("already_installed", "Already installed, delete old pack before installing a new one", "", 4)
            ],
        default = "None",
        )   

class HG_REFRESH_CPACKS(bpy.types.Operator):
    """
    operator for the refresh cpacks button. Refresh function is outside class because it is used by other operators too 
    """
    bl_idname = "hg3d.cpacksrefresh"
    bl_label = "Refresh"
    bl_description = "Refresh the content pack list"

    def execute(self,context):
        cpacks_refresh(self, context)
        return {'FINISHED'}

def cpacks_refresh(self, context):
    """
    refreshes the content pack ui list by scanning the content_packs folder in the file structure
    """
    coll = context.scene.contentpacks_col
    pref = context.preferences.addons[__package__].preferences

    coll.clear()

    #add the fake header as an item to the collection, to be used in the ui list as a header
    header = coll.add()
    header.name = 'header'

    json_folder = str(pref.filepath) + str(Path('/content_packs/'))
    dirlist = os.listdir(json_folder)
  
    for fn in dirlist:
        if os.path.splitext(fn)[1] != '.json':
            continue #skip non json files

        #open json
        filepath = json_folder + str(Path('/{}'.format(fn)))
        with open(filepath) as f:
            data = json.load(f)
    
        item = coll.add()
        config = data['config']
        
        #add the properties to the collection item
        item.name = config['pack_name']
        for prop_name in ('pack_name', 'creator', 'weblink', 'description', 'icon_name'):
            item[prop_name] = config[prop_name] if prop_name in config else None
        
        pack_version = config['pack_version']
        if type(pack_version) is str: #compatibility with old str method of writing version
            pack_version =  [int(pack_version[0]), int(pack_version[2])]  
        item['pack_version'] = pack_version
        

        item.json_path = filepath
        categs = data['categs']
        for name, incl in categs.items():
            item[name] = incl     

    check_update()

class HG_DELETE_CPACK(bpy.types.Operator):
    """
    Deletes the cpack from the content pack collection. 
    Uses the dictionary of files in the .json of the cpack to delete all files belonging to this cpack
    """
    bl_idname = "hg3d.cpackdel"
    bl_label = "Delete content pack"
    bl_description = "Delete this content pack"

    item_name: bpy.props.StringProperty()

    def execute(self,context):
        pref = context.preferences.addons[__package__].preferences
        
        col = context.scene.contentpacks_col
        index = context.scene.contentpacks_col_index
        item = col[self.item_name]
        
        #delete files from dict in json
        with open(item.json_path) as f:
            data = json.load(f)
        file_list = data['files']
        for fn in file_list:
            filepath = pref.filepath + str(Path(fn))
            try:
                os.remove(filepath)
            except PermissionError:
                print('Could not remove ',filepath)

        #remove item from collection
        col.remove(index)
        context.scene.contentpacks_col_index = min(max(0, index - 1), len(col) - 1)

        self.removeEmptyFolders(pref.filepath)
        cpacks_refresh(self, context)
        return {'FINISHED'}

    def removeEmptyFolders(self, path):
        """
        Recursive function to remove empty folders
        """
        if not os.path.isdir(path):
            return

        files = os.listdir(path)
        if len(files):
            for f in files:
                fullpath = os.path.join(path, f)
                if os.path.isdir(fullpath):
                    self.removeEmptyFolders(fullpath)

        files = os.listdir(path)
        if len(files) == 0:
            os.rmdir(path)

    def invoke(self, context, event):
        #confirmation checkbox
        return context.window_manager.invoke_confirm(self, event)

class HG_DELETE_INSTALLPACK(bpy.types.Operator):
    """
    Removes installpack from ui_list collection
    """
    bl_idname = "hg3d.removeipack"
    bl_label = ""
    bl_description = "Remove the active item from the list"

    @classmethod
    def poll(cls, context): 
        return context.scene.installpacks_col 
    
    def execute(self, context): 
        col = context.scene.installpacks_col
        index = context.scene.installpacks_col_index
        
        col.remove(index) 
        context.scene.installpacks_col_index = min(max(0, index - 1), len(col) - 1)
        return{'FINISHED'}

