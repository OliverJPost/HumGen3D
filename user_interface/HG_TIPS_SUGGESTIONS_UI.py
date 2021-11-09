import bpy

from ..core.HG_PCOLL import preview_collections
from ..tips_and_suggestions.batch_tips_and_suggestions import \
    get_batch_tips_from_context  # type:ignore
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
        col.separator()
        _draw_text_bloc(col, tip_item.tip_text)
        

def _draw_text_bloc(layout, text):
    col = layout.column()
    col.scale_y = 0.7
    col.enabled = False
    
    for line in text.splitlines():
        col.label(text = line)

def _update_tips_from_context(context, sett, hg_rig):
    hg_area = 'content_saving' if sett.content_saving_ui else sett.active_ui_tab
    phase = in_creation_phase(hg_rig)
    
    col = context.scene.hg_tips_and_suggestions
    
    if hg_area == 'BATCH':
        tips = get_batch_tips_from_context(context, sett, hg_rig)
    
    col.clear()
    for icon_name, tip_text, operator_name, operator_label in tips:
        item = col.add()
        item.icon_name = icon_name
        item.tip_text = tip_text
        item.operator_name = operator_name
        item.operator_label = operator_label

class TIPS_ITEM(bpy.types.PropertyGroup):
    """
    Properties of the items in the uilist
    """
    icon_name: bpy.props.StringProperty(default = '')   
    tip_text: bpy.props.StringProperty(default = '')
    operator_name: bpy.props.StringProperty(default = '')
    operator_label: bpy.props.StringProperty(default = '')
