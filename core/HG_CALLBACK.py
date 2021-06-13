'''
Contains operators and functions for the callback HG3D gets whenever 
    the active object changes.
This callback has the following usages:
-Update the choices for all preview collections, for example loading female 
    hairstyles when a female human is selected
-Update the subsurface scattering toggle in the UI
-Makes sure the hg_rig.HG.body_object is updated to the correct body object when
    a human is duplicated by the user
'''

from .. features.utility_section.HG_UTILITY_FUNC import (
    refresh_hair_ul,
    refresh_modapply,
    refresh_outfit_ul,
    refresh_shapekeys_ul
)
import bpy #type: ignore
from . HG_PCOLL import refresh_pcoll
from .. features.common.HG_COMMON_FUNC import find_human

class HG_ACTIVATE(bpy.types.Operator):
    """
    Activates the HumGen msgbus, also refreshes human pcoll
    """
    bl_idname      = "hg3d.activate"
    bl_label       = "Activate"
    bl_description = "Activate HumGen"
    
    def execute(self, context):    
        sett            = bpy.context.scene.HG3D
        sett.subscribed = False

        msgbus(self, context)
        refresh_pcoll(self, context, 'humans')
        print('activating HumGen')
        return {'FINISHED'} 

def msgbus(self, context):
    """
    Activates the subscribtion to the active object
    """ 
    sett = bpy.context.scene.HG3D

    if sett.subscribed == True:
        return

    subscribe_to = bpy.types.LayerObjects, "active"
    bpy.msgbus.subscribe_rna(
        key    = subscribe_to,
        owner  = self,
        args   = (self,),
        notify = HG_Callback,
        )
    sett.subscribed = True    

def HG_Callback(self):
    """
    Runs every time the active object changes
    """ 

    hg_rig = find_human(bpy.context.active_object) 
    if not hg_rig:
        return #return immediately when the active object is not part of a human
    
    _check_body_object(hg_rig)

    sett = bpy.context.scene.HG3D
    ui_phase = sett.ui_phase

    _set_subsurface_scattering(hg_rig, sett)

    _context_specific_updates(self, sett, hg_rig, ui_phase)

def _check_body_object(hg_rig):
    """Update HG.body_obj if it's not a child of the rig. This would happen if 
    the user duplicated the human manually

    Args:
        hg_rig (Object): HumGen human armature
    """
    if hg_rig.HG.body_obj not in hg_rig.children:
        new_body = ([obj for obj in hg_rig.children if 'hg_rig' in obj] 
                    if hg_rig.children 
                    else None)
        
        if new_body:
            hg_rig.HG.body_obj = new_body[0]
            if 'no_body' in hg_rig:
                del hg_rig['no_body']
        else:
            hg_rig['no_body'] = 1
    else:
        if 'no_body' in hg_rig:
            del hg_rig['no_body']

def _set_subsurface_scattering(hg_rig, sett):
    """Sets the subsurface toggle to the correct position. Update_exception is 
    used to prevent an endless loop of setting the toggle

    Args:
        hg_rig (Object): HumGen armature
        sett (PropertyGroup): HumGen props
    """
    sett.update_exception = True
    try:
        nodes = hg_rig.HG.body_obj.data.materials[0].node_tree.nodes
        principled_bsdf = next([node for node in nodes 
                                if node.type == 'BSDF_PRINCIPLED'])
        sett.skin_sss = ('off' 
                         if principled_bsdf.inputs['Subsurface'].default_value == 0 
                         else 'on')
    except Exception as e:
        print('Could not set subsurface toggle, with error: ', e)

def _context_specific_updates(self, sett, hg_rig, ui_phase):    
    """Does all updates that are only necessary for a certain UI context. I.e.
    updating the preview collection of clothing when in the clothing section

    Args:
        sett (PropertyGroup): HumGen props
        hg_rig (Ojbect): HumGen armature
        ui_phase (str): Currently open ui tab
    """
    sett.update_exception = False
    context = bpy.context
    if sett.active_ui_tab == 'TOOLS':   
        refresh_modapply(self, context)
        refresh_shapekeys_ul(self, context)
        refresh_hair_ul(self, context)
        refresh_outfit_ul(self, context)
        return
    elif ui_phase == 'body':
        _refresh_body_scaling(self, sett, hg_rig.HG.body_obj)
    elif ui_phase == 'skin':
        refresh_pcoll(self, context, 'textures')
        return      
      
    elif ui_phase == 'clothing':
        refresh_pcoll(self, context, 'outfit')
        return
    elif ui_phase == 'hair':
        refresh_pcoll(self, context, 'hair')
        if hg_rig.HG.gender == 'male':
            refresh_pcoll(self, context, 'face_hair')
        return
    elif ui_phase == 'expression':
        refresh_pcoll(self, context, 'expressions')
        return

#FIXME add callback for body scaling
def _refresh_body_scaling(self, sett, hg_body):
    pass


def tab_change_update(self, context):
    """Update function for when the user switches between the main tabs (Main UI,
    Batch tab and Utility tab)"""
    
    refresh_modapply(self, context)
    refresh_shapekeys_ul(self, context)
    refresh_hair_ul(self, context)
    refresh_outfit_ul(self, context)


