import bpy #type: ignore
import os
from .. HG_PCOLL import preview_collections

def tab_switching_menu(layout, sett):
    row = layout.row()
    row.scale_x = 1.5
    row.alignment = 'EXPAND'
    row.prop(sett, 'active_ui_tab', expand = True, icon_only = True)

def next_phase(self):
    layout = self.layout
    col = layout.column()
    col.alert = True
    col.scale_y = 1.5
    col.operator('hg3d.finishcreation', text = 'Finish Creation Phase' , icon = 'FILE_ARCHIVE', depress = True)

def get_flow(sett, col, animation = False):
    col_2 =  col.column(align = True)
    col_2.use_property_split = True
    col_2.use_property_decorate = animation            
    flow = col_2.grid_flow(row_major=False, columns=1, even_columns=True, even_rows=False, align=True)
    return flow

def spoiler_box(self, ui_name):
    """
    called by other UI elements for getting a title box of that section. Returns if the box is open or not. If this section is already completed by the user, returns False so section cannot be opened again
    """ 
    pref = bpy.context.preferences.addons[os.path.splitext(__package__)[0]].preferences
    
    #fallback icons for when custom ones don't load
    icon_dict = {
        'body' : 'COMMUNITY',
        'face' : 'COMMUNITY',
        'skin' : 'COMMUNITY',
        'hair' : 'OUTLINER_OB_HAIR',
        'length': 'EMPTY_SINGLE_ARROW',
        'creation_phase': 'COMMUNITY',
        'clothing' : 'MATCLOTH',
        'footwear' : 'MATCLOTH',
        'pose' : 'ARMATURE_DATA',
        'expression': 'GHOST_ENABLED',
        'simulation' : 'NETWORK_DRIVE',
        'compression': 'FOLDER_REDIRECT'
        }

    is_open = True if self.sett.ui_phase == ui_name else False

    layout = self.layout
    box = layout.box()

    hg_rig = self.hg_rig

    row = box.row(align=True)
    row.scale_y= 2
    row.alignment = 'LEFT'

    label = ui_name.capitalize().replace('_', ' ')

    try:
        hg_icons =  preview_collections["hg_icons"]
        row.operator('hg3d.uitoggle', text = label, icon_value= hg_icons[ui_name].icon_id, emboss = False).categ = ui_name
    except:
        icon = icon_dict[ui_name]
        row.operator('hg3d.uitoggle', text = label, icon= icon,emboss=False).categ = ui_name

    return is_open, box

def searchbox(self, name, layout):
    sett = self.sett
    row = layout.row(align= True)
    row.prop(sett, 'search_term_{}'.format(name), text = '', icon = 'VIEWZOOM')
    
    sett_dict = {'poses': sett.search_term_poses, 'outfit': sett.search_term_outfit, 'footwear': sett.search_term_footwear, 'expressions': sett.search_term_expressions, 'patterns': sett.search_term_patterns}
    if sett_dict[name] != '':
        row.operator('hg3d.clearsearch', text = '', icon = 'X').categ = name

