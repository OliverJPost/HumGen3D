import bpy  # type:ignore

from ..core.HG_PCOLL import preview_collections

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

def draw_tips_suggestions_ui(layout, context = 'main', in_creation_phase = True):
    col = layout.column(align = True)
    hg_icons = preview_collections['hg_icons']
    
    col.separator(factor = 2)
    
    important_tip = True
    
    box = col.box()
    box.enabled = False # important_tip
    light_state = 'on' if important_tip else 'off'
    box.label(text = 'Tips & Suggestions', icon_value = hg_icons[f'light_{light_state}'].icon_id)
    
    _draw_text_bloc(col, lorum_ipsum)
   
    split = col.split(factor = 0.60)
    col1 = split.column()
    col1.enabled = False
    col2 = split.column().split(factor = 0.4)
    col3 = col2.column()
    col1.label(text = "Go there by clicking")
    col3.operator('hg3d.testop', text = 'here', emboss = False)
        

def _draw_text_bloc(layout, text):
    col = layout.column()
    col.scale_y = 0.7
    col.enabled = False
    
    for line in text.splitlines():
        col.label(text = line)
