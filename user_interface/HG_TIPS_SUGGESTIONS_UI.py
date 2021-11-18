import json
import os

import bpy

from ..core.HG_PCOLL import preview_collections
from ..features.common.HG_COMMON_FUNC import get_prefs
from ..tips_and_suggestions.batch_tips_and_suggestions import \
    get_batch_tips_from_context  # type:ignore
from ..tips_and_suggestions.content_saving_tips_and_suggestions import \
    get_content_saving_tips_from_context
from ..tips_and_suggestions.extras_menu_tips_and_suggestions import \
    get_extras_menu_tips_from_context
from ..tips_and_suggestions.main_ui_tips_and_suggestions import \
    get_main_ui_tips_from_context
from ..user_interface.HG_PANEL_FUNCTIONS import in_creation_phase

lorum_ipsum = """
Lorem ipsum dolor sit amet, consectetur 
adipiscing elit, sed do eiusmod tempor
incididunt ut labore et dolore magna
aliqua. Ut enim ad minim veniam, quis
nostrud exercitation ullamco laboris
nisi ut aliquip ex ea commodo consequat.
Duis aute irure dolor in reprehenderit
in voluptate velit esse cillum dolore 
eu fugiat nulla pariatur. Excepteur
sint occaecat cupidatat non proident,
sunt in culpa qui officia deserunt 
mollit anim id est laborum
"""

def draw_tips_suggestions_ui(layout, context):
    sett = context.scene.HG3D
    
    col = layout.column(align = True)
    
    hg_icons = preview_collections['hg_icons']
    
    col.separator(factor = 2)
    
    important_tip = True
    

    
    box = col.box()
    box.enabled = False # important_tip
    light_state = 'on' if important_tip else 'off'
    box.label(text = 'Tips & Suggestions', icon_value = hg_icons[f'light_{light_state}'].icon_id)

    tips_col = context.scene.hg_tips_and_suggestions
    if not len(tips_col):
        row = layout.row()
        row.enabled = False
        row.label(text = "No active tips.")
    
    for tip_item in tips_col:
        if tip_item.hidden:
            continue
        col.separator()
        _draw_tips_bloc(col, tip_item)

    hidden_tips_amount = len([tip for tip in tips_col if tip.hidden])
    if hidden_tips_amount:
        col.separator()
        row = col.row()
        row.alignment = 'CENTER'
        row.prop(sett, 'show_hidden_tips',
                 text = '{tag} {amount} hidden tip{plural}'.format(
                     tag = 'Hide' if sett.show_hidden_tips else 'Show',
                     amount = hidden_tips_amount,
                     plural = 's' if hidden_tips_amount > 1 else ''
                    ),
                 toggle = True,
                 emboss = False
            )
        
    if sett.show_hidden_tips:
        for tip_item in [tip for tip in tips_col if tip.hidden]:
            col.separator()
            _draw_tips_bloc(col, tip_item)                
        

def _draw_tips_bloc(layout, tip_item):
    col = layout.box()
    row = col.row()
    row.alignment = 'CENTER'
    
    subrow = row.row()
    subrow.alignment = 'CENTER'
    subrow.enabled = False
    subrow.label(text = tip_item.title, icon = tip_item.icon_name)
    row.operator('hg3d.unhide_tip' if tip_item.hidden else 'hg3d.hide_tip',
                 text = "",
                 icon = 'CHECKMARK' if tip_item.hidden else 'X',
                 emboss = False
                 ).tip_name = tip_item.title
    subcol = col.column()
    subcol.scale_y = 0.8
    subcol.enabled = False
    
    for line in tip_item.tip_text.splitlines():
        subcol.label(text = line)

    if tip_item.operator_name:
        operator = col.operator(tip_item.operator_name, 
                     text = tip_item.operator_label,
                     icon = tip_item.operator_icon,
                     emboss = False)
        if tip_item.operator_keyword:
            setattr(operator, tip_item.operator_keyword, tip_item.operator_argument)

def update_tips_from_context(context, sett, hg_rig):
    hg_area = 'content_saving' if sett.content_saving_ui else sett.active_ui_tab
    if hg_rig:
        phase = in_creation_phase(hg_rig)
    
    col = context.scene.hg_tips_and_suggestions
    
    if hg_area == 'BATCH':
        tips = get_batch_tips_from_context(context, sett, hg_rig)
    elif hg_area == 'content_saving':
        tips = get_content_saving_tips_from_context(context, sett, hg_rig)
    elif hg_area == 'TOOLS':
        tips = get_extras_menu_tips_from_context(context, sett, hg_rig)
    else:
        tips = get_main_ui_tips_from_context(context, sett, hg_rig)
    
    if not tips:
        col.clear()
        return
 
    json_path = os.path.join(get_prefs().filepath, 'hidden_tips_list.json')

    if os.path.exists(json_path):
        with open(json_path) as f:
            hidden_tips_list = json.load(f) 
    else:
        hidden_tips_list = []
    
    col.clear()
    for title, icon_name, tip_text, operator in tips:
        item = col.add()
        item.title = title
        item.icon_name = icon_name
        item.tip_text = tip_text
        
        if title in hidden_tips_list:
            item.hidden = True
        
        if operator:
            item.operator_icon = operator[0]
            item.operator_name = operator[1]
            item.operator_label = operator[2]
            item.operator_keyword = operator[3]
            item.operator_argument = operator[4]

class TIPS_ITEM(bpy.types.PropertyGroup):
    """
    Properties of the items in the uilist
    """
    title: bpy.props.StringProperty(default = '')
    icon_name: bpy.props.StringProperty(default = '')   
    tip_text: bpy.props.StringProperty(default = '')
    operator_name: bpy.props.StringProperty(default = '')
    operator_label: bpy.props.StringProperty(default = '')
    operator_keyword: bpy.props.StringProperty(default = '')
    operator_argument: bpy.props.StringProperty(default = '')
    operator_icon: bpy.props.StringProperty(default = '')
    hidden: bpy.props.BoolProperty(default = False)
    
class HG_OT_HIDE_TIP(bpy.types.Operator):
    bl_idname      = "hg3d.hide_tip"
    bl_label       = "Hide this tip"
    bl_description = "Hides this tip from the tips/suggetions list"

    tip_name: bpy.props.StringProperty()

    def execute(self,context):        
        tips_col = context.scene.hg_tips_and_suggestions
        tips_item = next(tip for tip in tips_col if tip.title == self.tip_name)
        tips_item.hidden = True

        json_path = os.path.join(get_prefs().filepath, 'hidden_tips_list.json')

        if os.path.exists(json_path):
            with open(json_path) as f:
                hidden_tips_list = json.load(f)
        else:
            hidden_tips_list = []
        
        hidden_tips_list.append(self.tip_name)
    
        with open(json_path, 'w') as f:
            json.dump(hidden_tips_list, f, indent=4,)

        return {'FINISHED'}

class HG_OT_UNHIDE_TIP(bpy.types.Operator):
    bl_idname      = "hg3d.unhide_tip"
    bl_label       = "Unhide this tip"
    bl_description = "Unhides this tip from the tips/suggetions list"

    tip_name: bpy.props.StringProperty()

    def execute(self,context):        
        tips_col = context.scene.hg_tips_and_suggestions
        tips_item = next(tip for tip in tips_col if tip.title == self.tip_name)
        tips_item.hidden = False

        json_path = os.path.join(get_prefs().filepath, 'hidden_tips_list.json')

        if os.path.exists(json_path):
            with open(json_path) as f:
                hidden_tips_list = json.load(f)
        else:
            return {'FINISHED'}
        
        if self.tip_name in hidden_tips_list:
            hidden_tips_list.remove(self.tip_name)
        
            with open(json_path, 'w') as f:
                json.dump(hidden_tips_list, f, indent=4,)

        return {'FINISHED'}
