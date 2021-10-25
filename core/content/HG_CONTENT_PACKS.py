"""
Operators and functions used for installing and managing HumGen's content packs

Nomenclature:
Installpack = a collection item that represents a zip file the user has selected. 
    Pressing 'install all packs' unzips these files into the file structure,
    making them cpacks (content packs)
cpack = Abbreviation of content pack. Represents a collection of items
    downloaded together and extracted in the HumGen file strucure, forming
    content to be used in the add-on. Settings and properties stored in a
    .json file
"""  

import json
import os
import zipfile
from pathlib import Path

import bpy  # type: ignore
from bpy_extras.io_utils import ImportHelper  # type: ignore

from ...features.common.HG_COMMON_FUNC import ShowMessageBox, get_prefs, hg_log
from ..HG_PCOLL import preview_collections
from .HG_UPDATE import check_update


class HG_UL_INSTALLPACKS(bpy.types.UIList):
    """
    UIList showing cpacks to be installed
    """   

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):      
        alert_dict = {
            'not_cpack'          : 'Not a content pack',
            'no_json'            : 'No .json file in pack',
            'incorrect_structure': 'Incorrect file structure',
            'not_zip'            : 'Not a zip file',
            'already_installed'  : 'Already installed, delete old pack before installing a new one'
        }
        
        row = layout.row(align = True)
        row.label(text= item.pack_name)
        
        if item.alert != 'None':
            row.alert = True
            row = row.row()
            row.label(text = alert_dict[item.alert],
                      icon = 'ERROR')

class HG_UL_CONTENTPACKS(bpy.types.UIList):
    """UIList showing content packs, including icons on who made the pack, 
    what version it is, what items are included, a weblink and a delete button
    """   
    def draw_item(self, context, layout, data, item, icon, active_data, 
                  active_propname, index):
        
        hg_icons = preview_collections["hg_icons"]
        header = True if item.name == 'header' else False 
        #header is true only for the first item in the list.
        #This fakes a header for the items in the ui_list
        
        row = layout.row(align = True)
        row.label(text='Name:' if header else item.pack_name)
        
        subrow = row
        self._draw_creator_column(item, hg_icons, header, subrow)

        subrow.label(text = 'Version:' if header 
                     else '%s.%s'% tuple(item.pack_version)
                     )           
        subrow.alignment = 'LEFT'
        
        self._draw_update_label(item, subrow, header)
        self._draw_category_dots(item, hg_icons, header, subrow)

        subrow.separator()

        self._draw_operator_buttons(item, header, subrow)

    def _draw_operator_buttons(self, item, header, subrow):
        """Draws buttons to go to edit cpack, to cpack weblink and button to 
        delete cpack"""
        if header:
            for i in range(3):
                subrow.label(text = '', icon = 'BLANK1')
            return
        
        #weblink button
        subrow.operator("wm.url_open", text="", icon = 'URL').url = item.weblink
        #delete button
        subrow.operator("hg3d.cpackdel", text="", icon = 'TRASH').item_name = item.name

        #Edit pack button
        if item.creator != 'HumGen' or get_prefs().dev_tools:
            subrow.operator("hg3d.edit_cpack",
                            text="",
                            icon='GREASEPENCIL',
                            emboss=False).item_name = item.name
        else:
            subrow.label(text = '', icon = 'BLANK1')
        
    def _get_icon_dict(self) -> dict:
        """Dictionary with custom icon names for each category

        Returns:
            dict: key: name of category, value: name of icon
        """
        
        icon_dict = {
            'humans'        : 'humans',
            'human_textures': 'textures',
            'shapekeys'     : 'body',
            'hair'          : 'hair',
            'poses'         : 'pose',
            'clothes'       : 'clothing',
            'footwear'      : 'footwear',
            'expressions'   : 'expression'
            }
            
        return icon_dict

    def _draw_category_dots(self, item, hg_icons, header, subrow):
        """Draws grid of dots to show what kind of content is in this cpack"""
        icon_dict = self._get_icon_dict()
            
        for categ, icon in icon_dict.items():
            if header:
                subrow.label(text = '', icon_value = hg_icons[icon].icon_id)
            else:
                if categ not in item:
                    subrow.label(text = '', icon = 'LAYER_USED')
                    continue
                
                subrow.label(text = '', icon = "LAYER_ACTIVE" if item[categ] else 'LAYER_USED')

    def _draw_creator_column(self, item, hg_icons, header, subrow):
        """Draws a column with info about the creator of this cpack"""
        if header:
            subrow.label(text = 'Creator:') 
        elif item.creator == 'HumGen':
            subrow.label(text = item.creator,
                         icon_value = hg_icons['HG_icon'].icon_id
                         )
        else:
            subrow.label(text = item.creator,
                         icon = item.icon_name
                         )

    def _draw_update_label(self, item, subrow, header):
        """Draws a column with info if the cpack is up to date"""
        if header:
            subrow.label(text = 'Update info:    ')
            return
        
        pack_version     = tuple(item.pack_version)
        req_version      = tuple(item.required_version)
        latest_version   = tuple(item.latest_version)
        
        upd = (
                'uptodate' if pack_version >= req_version 
                    and pack_version >= latest_version 
                else 'required' if pack_version < req_version 
                else 'available'
                )

        subrow.alert = True if upd == 'required' else False
        #format version number to string
        vnum = '%s.%s'% tuple(item.latest_version if upd == 'available'
                            else item.required_version)
            
        subrow.label(text = ('Up to date     ' if upd == 'uptodate' 
                             else f'{vnum} available' if upd == 'available' 
                             else f'{vnum} required! '
                             ),
                     icon = ('CHECKMARK' if upd == 'uptodate' 
                             else 'INFO' if upd == 'available'
                             else 'ERROR'
                             )
                         )
        subrow.alert = False

class HG_SELECT_CPACK(bpy.types.Operator, ImportHelper):
    """Opens a filebrowser popup, allowing the user to select files. This 
    operator adds them to a collection property, meanwhile checking if any 
    problems arise that mean the pack should not be installed

    API: False

    Operator Type:
        HumGen installation
        File/dir selection
        
    Prereq:
        None

    Args:
        ImportHelper: prompts a filebrowser popup
    """
    bl_idname = "hg3d.cpackselect"
    bl_label = "Select content pack zips"
    bl_description = """Opens a file browser for you to select the zip files of 
        the content packs you wish to install"""

    files: bpy.props.CollectionProperty(
            name = "File Path",
            type = bpy.types.OperatorFileListElement,
            )
    directory: bpy.props.StringProperty(
            subtype = 'DIR_PATH',
            )

    def execute(self, context):
        directory = self.directory
        pref = get_prefs()

        coll = context.scene.installpacks_col

        if not self.files:
            ShowMessageBox(message = '''No files selected, 
                           please select the zip files''')
            return {'FINISHED'}

        #iterate over all the files the user selected in the importhelper popup
        for fn in self.files:
            self._add_to_collection(coll, directory, fn)
        return {'FINISHED'}

    def _add_to_collection(self, coll, directory, fn):
        """adds this cpack to the installpack collection

        Args:
            coll (CollectionProperty): installpack collection
            directory (dir): directory the cpack zips are in
            fn (str): names of selected files
        """
        item     = coll.add()
        filepath = os.path.join(directory, fn.name)
        
        item.name      = filepath
        item.pack_name = filepath
        item.alert = self._check_for_alerts(item, filepath)

    def _check_for_alerts(self, item, filepath) -> str:
        """checks for common errors with content packs

        Args:
            item (collection item): installpack item
            filepath (Path): filepath of this installpack

        Returns:
            str: alert code
        """
        if not os.path.basename(filepath).startswith('HG_CP'):
            return 'not_cpack' #return error code if the prefix is not correct

        zf = zipfile.ZipFile(filepath)

        cpack_json_files = [file for file in zf.namelist()
                            if file.startswith('content_packs')
                            ]
        
        if not cpack_json_files:
            return 'incorrect_structure' 
            #return error code if the content_packs folder is not present or not 
            #in the correct place

        json_path = next((file for file in cpack_json_files 
                          if os.path.splitext(file)[1] == '.json'),
                          None)
        if json_path:
            item.json_path = json_path
        else:
            return 'no_json' 

        json_folder = str(get_prefs().filepath) + str(Path('/content_packs/'))
        
        try:
            dirlist = os.listdir(json_folder)
            if [fn for fn in dirlist if os.path.basename(item.json_path) == fn]:
                return'already_installed' 
                #return error code if a .json already exists in the file 
                # structure with the same name
            else:
                return 'None'
        except:
            return 'None'        

class HG_INSTALL_CPACK(bpy.types.Operator):
    """Installs (unzips into file structure) all packs in the installpack 
    collection if they don't have any error codes.
    
    Operator type:
        HumGen installation
        File management
    
    Prereq:
        Items in installpack collection
    """  
    bl_idname = "hg3d.cpackinstall"
    bl_label = "Install"
    bl_description = "Refresh the content pack list"
    
    def execute(self,context):
        pref  = get_prefs()
        self.files = [file for file in context.scene.installpacks_col 
                      if file.alert == 'None']

        filepath = pref.filepath

        for zip_path in self.files:
            file_dict = self._unzip_file(zip_path, filepath)
            self._add_filelist_to_json(filepath, zip_path, file_dict)

        coll = context.scene.installpacks_col
        coll.clear()
        try:
            cpacks_refresh(self, context)
        except:
            pass

        return {'FINISHED'}

    def _unzip_file(self, zip_path, filepath) -> dict:
        """unzips the file to the HumGen cpack directory

        Args:
            filepath (str): filepath of the HumGen cpack directory
            zip_path (str): filepath of the zip to unzip

        Returns:
            dict: directory of files that were installed, used for deleting cpack
        """
        hg_log('Starting unzip, file:', zipfile)
        zf = zipfile.ZipFile(zip_path.name)

        file_list = [fn for fn in zf.namelist() if not fn.endswith('/')]
        zf.extractall(path = filepath)
        
        return {'files': file_list}

    def _add_filelist_to_json(self, filepath, zip_path, file_dict):
        """adds a dictionary to the json file with all filenames of files in the 
        content pack. This will be used by the HG_DELETE_CPACK operator

        Args:
            filepath (str): filepath of the HumGen cpack directory
            zip_path (str): filepath of the zip to unzip
            file_dict (dict): dictionary of all files in zip
        """
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
        name        = 'Content Pack Name',
        description = "",
        default     = '',
        )  
    
    creator     : bpy.props.StringProperty()
    pack_version: bpy.props.IntVectorProperty(default = (0,0), size = 2)
    weblink     : bpy.props.StringProperty()
    icon_name   : bpy.props.StringProperty(default = 'COMMUNITY')

    #booleans for showing in the UI what categories are in this pack
    humans        : bpy.props.BoolProperty(default = False)
    human_textures: bpy.props.BoolProperty(default = False)
    shapekeys     : bpy.props.BoolProperty(default = False)
    hair          : bpy.props.BoolProperty(default = False)
    poses         : bpy.props.BoolProperty(default = False)
    clothes       : bpy.props.BoolProperty(default = False)
    footwear      : bpy.props.BoolProperty(default = False)
    expressions   : bpy.props.BoolProperty(default = False)

    json_path       : bpy.props.StringProperty()
    required_version: bpy.props.IntVectorProperty(default = (0,0), size = 2)
    latest_version  : bpy.props.IntVectorProperty(default = (0,0), size = 2)

class HG_INSTALLPACK(bpy.types.PropertyGroup):
    """Properties of the installpack representation of the selected zip files"""
    pack_name: bpy.props.StringProperty(
        name        = 'Content Pack Name',
        description = "",
        default     = '',
        )  
    json_path: bpy.props.StringProperty()
    installed: bpy.props.BoolProperty(default = False)
    alert    : bpy.props.EnumProperty(
        name  = "posing",
        description = "",
        items = [
            ("None",                "None",                         "", 0),
            ("not_cpack",           "Not a content pack",           "", 1),
            ("incorrect_structure", "Incorrect zip method",         "", 2),
            ("no_json",             "Doesn't contain .json file",   "", 3),
            ("already_installed",   "Already installed, delete old pack before installing a new one", "", 4)
            ],
        default = "None",
        )   

class HG_REFRESH_CPACKS(bpy.types.Operator):
    """Operator for the refresh cpacks button. Refresh function is outside class
    because it is called as an update for certain props
    
    Operator type:
        UI_list refresh
    
    Prereq:
        None
    """
    bl_idname      = "hg3d.cpacksrefresh"
    bl_label       = "Refresh"
    bl_description = "Refresh the content pack list"

    def execute(self,context):
        cpacks_refresh(self, context)
        return {'FINISHED'}

#FIXME slow switch between preferences tabs
def cpacks_refresh(self, context):
    """Refreshes the content pack ui list by scanning the content_packs folder 
    in the file structure"""
    coll = context.scene.contentpacks_col
    pref = get_prefs()

    coll.clear()

    #add the fake header as an item to the collection,
    header= coll.add()
    header.name = 'header'

    json_folder = str(pref.filepath) + str(Path('/content_packs/'))
    dirlist = os.listdir(json_folder)
  
    for fn in dirlist:
        if os.path.splitext(fn)[1] == '.json':
            _add_cpack_to_coll(coll, json_folder, fn)

    check_update()

def _add_cpack_to_coll(coll, json_folder, fn):
    """Adds this cpack to the content pack collection

    Args:
        coll (CollectionProperty): cpack collection
        json_folder (Path): folder where the cpack jsons are
        fn (str): filename of json file for this cpack
    """
    filepath = json_folder + str(Path('/{}'.format(fn)))
    with open(filepath) as f:
        data = json.load(f)
    
    item = coll.add()
    config = data['config']
      
    item.name = config['pack_name']
    
    prop_names = (
        'pack_name',
        'creator',
        'weblink',
        'description',
        'icon_name'
        )
    for prop_name in prop_names:
        item[prop_name] = config[prop_name] if prop_name in config else None
        
    pack_version = config['pack_version']
    if type(pack_version) is str: #compatibility with old str method of writing version
        pack_version =  [int(pack_version[0]), int(pack_version[2])]  
    item['pack_version'] = pack_version
        
    item.json_path = filepath
    
    if 'categs' not in data:
        return
    
    categs = data['categs']
    for categ_name, includes_items_from_categ in categs.items(): 
        item[categ_name] = includes_items_from_categ #bool

class HG_DELETE_CPACK(bpy.types.Operator):
    """Deletes the cpack from the content pack collection. 
    Uses the dictionary of files in the .json of the cpack to delete all files 
    belonging to this cpack
    
    Operator type:
        File management
    
    Prereq:
        Cpack passed. Needs to be installed, not copied in
    
    Args:
        item_name (str): name of cpack item to remove
    """
    bl_idname      = "hg3d.cpackdel"
    bl_label       = "Delete content pack"
    bl_description = "Delete this content pack"

    item_name: bpy.props.StringProperty()

    def invoke(self, context, event):
        #confirmation checkbox
        return context.window_manager.invoke_confirm(self, event)

    def execute(self,context):
        pref  = get_prefs()    
        col   = context.scene.contentpacks_col
        index = context.scene.contentpacks_col_index
        item  = col[self.item_name]
        
        #delete files from dict in json
        with open(item.json_path) as f:
            data = json.load(f)
        
        os.remove(item.json_path)
        if 'files' in data:    
            file_list = data['files']
            
            for fn in file_list:
                filepath = pref.filepath + str(Path(fn))
                try:
                    os.remove(filepath)
                except PermissionError:
                    hg_log('Could not remove ', filepath, level = 'WARNING')
                except FileNotFoundError as e:
                    hg_log('Could not remove ', filepath, level = 'WARNING')
                    print(e)
            
        #remove item from collection
        col.remove(index)
        context.scene.contentpacks_col_index = min(max(0, index - 1),
                                                   len(col) - 1)

        self._removeEmptyFolders(pref.filepath)
        
        cpacks_refresh(self, context)
        
        return {'FINISHED'}

    def _removeEmptyFolders(self, path):
        """Recursive function to remove empty folders

        Args:
            path (Path): filepath of HumGen cpack directory
        """
        
        if not os.path.isdir(path):
            return

        files = os.listdir(path)
        if len(files):
            for f in files:
                fullpath = os.path.join(path, f)
                if os.path.isdir(fullpath):
                    self._removeEmptyFolders(fullpath)

        files = os.listdir(path)
        if len(files) == 0:
            os.rmdir(path)

class HG_DELETE_INSTALLPACK(bpy.types.Operator):
    """
    Removes installpack from ui_list collection
    
    API: False
    
    Operator type:
        UI list removal
        
    Prereq:
        Installpacks in installpack_col
        Active installpack
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
        context.scene.installpacks_col_index = min(max(0, index - 1),
                                                   len(col) - 1
                                                   )
        return{'FINISHED'}

