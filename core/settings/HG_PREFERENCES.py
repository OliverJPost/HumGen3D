from ... features.common.HG_COMMON_FUNC import get_prefs
import bpy #type: ignore
from ... import bl_info
import os
from pathlib import Path
from bpy_extras.io_utils import ImportHelper #type: ignore
from ... core.content.HG_CONTENT_PACKS import cpacks_refresh
from ... core.HG_PCOLL import preview_collections

class HG_PREF(bpy.types.AddonPreferences):
    """
    user preferences 
    """   
    bl_idname = __package__.split('.')[0]

    latest_version        : bpy.props.IntVectorProperty(default = (0,0,0))
    cpack_update_available: bpy.props.BoolProperty(default = False)
    cpack_update_required : bpy.props.BoolProperty(default = False)

    pref_tabs : bpy.props.EnumProperty(
        name="tabs",
        description="",
        items = [
                ("settings", "Settings",      "", "INFO", 0),
                ("cpacks",   "Content Packs", "", "INFO", 1),
            ],
        default = "settings",
        update = cpacks_refresh
        )   

    units : bpy.props.EnumProperty(
        name="units",
        description="",
        items = [
                ("metric",      "Metric",   "", 0),
                ("imperial",    "Imperial", "", 1),
            ],
        default = "metric",
        )   
    hair_section : bpy.props.EnumProperty(
        name="Show hair section",
        description="",
        items = [
                ("both",        "Both phases",          "", 0),
                ("creation",    "Creation phase only",  "", 1),
                ("finalize",    "Finalize phase only",  "", 2),
            ],
        default = "creation",
        )   

    show_confirmation    : bpy.props.BoolProperty(default = True)
    dev_tools            : bpy.props.BoolProperty(name="Show Dev Tools", description="", default=True)
    auto_hide_hair_switch: bpy.props.BoolProperty(default = True)
    auto_hide_popup      : bpy.props.BoolProperty(default = True)
    remove_clothes       : bpy.props.BoolProperty(default = True)
    compact_ff_ui        : bpy.props.BoolProperty(name = 'Compact face UI', default = False)
    keep_all_shapekeys   : bpy.props.BoolProperty(name = 'Keep all shapekeys after creation phase', default = False)

    #RELEASE remove default path
    filepath    : bpy.props.StringProperty(name= 'Install Filepath', default = r'C:\Users\Ole\OneDrive\HumGen_Files_Main\2nd_test_install_cpacks\\')

    nc_colorspace_name: bpy.props.StringProperty(default = '')
    debug_mode: bpy.props.BoolProperty(default = False)

    def draw(self, context):  
        #check if base content is installed, otherwise show installation ui
        base_content = os.path.exists(self.filepath + str(Path('content_packs/Base_Humans.json'))) if self.filepath else False
        if not base_content:
            self.first_time_ui(context)
            return

        layout = self.layout
        col = layout.column()
        update_available = 'cpack_required' if self.cpack_update_required else 'addon' if tuple(bl_info['version']) < tuple(self.latest_version) else 'cpack_available' if self.cpack_update_available else None 
        if update_available:
            box = col.box().column(align = True)
            
            row           = box.row()
            row.alignment = 'CENTER'
            row.label(text = '*****************************************')
            
            col_h         = box.column()
            col_h.scale_y = 3
            col_h.alert   = update_available == 'cpack_required'
            alert_dict = {
                'cpack_required': ['One or more Content Packs are incompatible and need to be updated!', 'ERROR'],
                'addon': ['A new update of the Human Generator add-on is available!', 'INFO'],
                'cpack_available': ['One or more Content Packs can be updated!', 'INFO']
            }
            col_h.operator("wm.url_open", text=alert_dict[update_available][0], icon = alert_dict[update_available][1], depress = update_available != 'cpack_required' ).url = 'https://humgen3d.com/support/update'
            box.operator("wm.url_open", text = 'How to update?', icon = 'URL').url = 'https://humgen3d.com/support/update'
            row = box.row()
            row.alignment = 'CENTER'
            row.label(text = '*****************************************')
        row = col.box().row(align = True)
        row.scale_y = 2
        row.prop(self, 'pref_tabs', expand = True)

        if self.pref_tabs == 'settings':
            self.settings_ui()
        elif self.pref_tabs == 'cpacks':
            self.cpack_ui(context)
        
    def settings_ui(self):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.
        
        col = layout.column(heading="UI:")

        col.prop(self, 'show_confirmation', text = 'Show confirmation popups')
        col.prop(self, 'auto_hide_hair_switch', text = 'Auto hide hair children when switching tabs')
        if not self.auto_hide_hair_switch:
            self.warning(col, 'Having auto-hide enabled improves viewport performance')
        col.prop(self, 'auto_hide_popup', text = 'Show popup when auto-hiding hair')
        col.prop(self, 'compact_ff_ui')
        col.prop(self, 'hair_section', text = 'Show hair section:')

        layout.separator()
        col = layout.column(heading="Default behaviour:")        
        col.prop(self, 'remove_clothes', text = 'Remove old clothes when adding new ones')
        col.prop(self, 'keep_all_shapekeys')
        if self.keep_all_shapekeys:
            self.warning(col, 'Keeping all shapekeys makes finishing creation phase take longer')
        
        layout.separator()
        col = layout.column(heading="Color Profile Compatibility:")
        col.prop(self, 'nc_colorspace_name', text = 'Non-color alternative naming')
        layout.separator()
        col = layout.column(heading="Advanced options:")
        col.prop(self, 'debug_mode', text = "Debug Mode")
        col.prop(self, 'dev_tools')
        

    def warning(self, layout, message):
        row = layout.row()
        row.alignment = 'RIGHT'
        row.label(text = message, icon = 'ERROR')        

    def cpack_ui(self, context):
        layout = self.layout
        col    = layout.column()
        row    = col.row()
        row.label(text = 'Install path:')
        if self.filepath:
            subrow = row.row()
            subrow.enabled = False
            subrow.prop(self, 'filepath', text = '')
        row.operator('hg3d.pathchange', text = 'Change' if self.filepath else 'Select')    

        row = col.row(align = False)
        row.template_list("HG_UL_CONTENTPACKS", "", context.scene, "contentpacks_col", context.scene, "contentpacks_col_index", rows=10)
        col_side = row.column(align = False)
        col_side.operator('hg3d.cpacksrefresh', icon = 'FILE_REFRESH', text = '')
        col_side.popover(panel='HG_ICON_LEGEND', text = '', icon = 'PRESET')

        box = col.box()
        box.label(text = 'Select packs to install:')
        selected_packs = True if len(context.scene.installpacks_col) != 0 else False
        if selected_packs:
            row = box.row()
            row.template_list("HG_UL_INSTALLPACKS", "", context.scene, "installpacks_col", context.scene, "installpacks_col_index")
            row.operator('hg3d.removeipack', icon = 'TRASH')
        row = box.row()
        row.scale_y = 1.5
        row.operator('hg3d.cpackselect', text = 'Select Content Packs', depress = False if selected_packs else True, icon = 'PACKAGE')
        
        if selected_packs:
            box = col.box()
            box.label(text = 'Install selected packs')
            
            row = box.row()
            row.scale_y = 1.5
            row.operator('hg3d.cpackinstall', text = 'Install Selected Content Packs', depress =True, icon = 'PACKAGE')

    def first_time_ui(self, context):
        layout = self.layout
        
        #tutorial link section
        box         = layout.box()
        box.scale_y = 1.5
        box.label(text = 'STEP 1: Follow the installation tutorial')
        
        row       = box.row()
        row.alert = True
        row.operator("wm.url_open", text = 'Installation tutorial [Opens browser]', icon= 'HELP', depress = True).url = 'https://www.humgen3d.com/install'

        #select path section
        box = layout.box()
        box.scale_y = 1.5
        box.label(text = 'STEP 2: Select a folder for HumGen to install content packs in. 2 GB free space recommended.')
        if self.filepath:
            d_row = box.row()
            d_row.enabled = False
            d_row.prop(self, 'filepath', text = '')
        box.operator('hg3d.pathchange', text = 'Change folder' if self.filepath else 'Select folder', depress = False if self.filepath else True, icon = 'FILEBROWSER')
        box.label(text = "If you've already installed content packs, just select that folder.", icon = 'INFO')

        if not self.filepath:
            return
        
        #select packs section
        box = layout.box()
        box.label(text = 'STEP 3: Select packs to install')
        row = box.row()
        row.template_list("HG_UL_INSTALLPACKS", "", context.scene, "installpacks_col", context.scene, "installpacks_col_index")
        row.operator('hg3d.removeipack', icon = 'TRASH')
        selected_packs = True if len(context.scene.installpacks_col) != 0 else False
        row = box.row()
        row.scale_y = 1.5
        row.operator('hg3d.cpackselect', text = 'Select Content Packs', depress = False if selected_packs else True, icon = 'PACKAGE')
        box.label(text = 'Select multiple content packs by pressing Ctrl (Windows) or Cmd (Mac)', icon = 'INFO')
        box.label(text = 'Selected files with a red warning cannot be installed and will be skipped', icon = 'INFO')

        if not selected_packs:
            return

        #install button section
        box = layout.box()
        box.scale_y = 1.5
        box.label(text = 'STEP 4: Install all your content packs')
        box.operator('hg3d.cpackinstall', text = 'Install All Content Packs', depress =True, icon = 'PACKAGE')
        box.label(text = 'Installation time depends on your hardware and the selected packs', icon = 'INFO')


#TODO build in preventive system for filepaths instead of dirpaths
class HG_PATHCHANGE(bpy.types.Operator, ImportHelper):
    '''
    Changes the path via file browser popup
    '''
    bl_idname      = "hg3d.pathchange"
    bl_label       = "Change Path"
    bl_description = "Change the install path"

    def execute(self,context):
        pref = get_prefs()

        pref.filepath  = self.filepath
        pref.pref_tabs = 'cpacks'
        pref.pref_tabs = 'settings'

        bpy.ops.wm.save_userpref()
        return {'FINISHED'}

class HG_ICON_LEGEND(bpy.types.Panel):
    '''
    Legend popover for the icons used in the ui_list
    '''
    bl_label       = 'Icon legend'
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x  = 8

    def draw (self,context): 
        layout = self.layout       
        hg_icons = preview_collections["hg_icons"]

        icon_dict = {
            'Human Meshes'  : 'humans',
            'Human Textures': 'textures',
            'Shapekeys'     : 'body',
            'Hairstyles'    : 'hair',
            'Poses'         : 'pose',
            'Outfits'       : 'clothing',
            'Footwear'      : 'footwear',
            'Expressions'   : 'expression'
            }

        for icon_desc, icon in icon_dict.items():
            layout.label(text = icon_desc, icon_value = hg_icons[icon].icon_id)
