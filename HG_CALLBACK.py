'''
Contains operators and functions for the callback HG3D gets whenever the active object changes.
This callback has the following usages:
-Update the choices for all preview collections, for example loading female hairstyles when a female human is selected
-Update the subsurface scattering toggle in the UI
-Makes sure the hg_rig.HG.body_object is updated to the correct body object when a human is duplicated by the user
'''

from . HG_UTILITY_FUNC import refresh_hair_ul, refresh_modapply, refresh_outfit_ul, refresh_shapekeys_ul
import bpy #type: ignore
from . HG_PCOLL import refresh_pcoll
from . HG_COMMON_FUNC import find_human

class HG_ACTIVATE(bpy.types.Operator):
    """
    activates the HumGen msgbus 
    """
    bl_idname = "hg3d.activate"
    bl_label = "Activate"
    bl_description = "Activate HumGen"
    
    def execute(self, context):    
        sett = bpy.context.scene.HG3D
        sett.subscribed = False
        msgbus(self, context)
        refresh_pcoll(self, context, 'humans')
        print('activating HumGen')
        return {'FINISHED'} 

def msgbus(self, context):
    """
    activates the subscribtion to the active object
    """ 
    sett = bpy.context.scene.HG3D

    if sett.subscribed == True:
        return

    subscribe_to = bpy.types.LayerObjects, "active"
    bpy.msgbus.subscribe_rna(
        key = subscribe_to,
        owner = self,
        args = (self,),
        notify = HG_Callback,
        )
    sett.subscribed = True    

def HG_Callback(self):
    """
    runs every time the active object changes
    """ 

    hg_rig = find_human(bpy.context.active_object)
    
    if not hg_rig:
        return #return immediately when the active object is not part of a human
    
    #Update HG.body_obj if it's not a child of the rig. This would happen if the user duplicated the human manually
    if hg_rig.HG.body_obj not in hg_rig.children:
        new_body = [obj for obj in hg_rig.children if 'hg_rig' in obj] if hg_rig.children else None
        if new_body:
            hg_rig.HG.body_obj = new_body[0]
            if 'no_body' in hg_rig:
                del hg_rig['no_body']
        else:
            hg_rig['no_body'] = 1
    else:
        if 'no_body' in hg_rig:
            del hg_rig['no_body']

    sett = bpy.context.scene.HG3D
    ui_phase = sett.ui_phase

    #set subsurface toggle to the correct value. Uses an exception prop to prevent a loop
    sett.update_exception = True
    try:
        principled_bsdf = [node for node in hg_rig.HG.body_obj.data.materials[0].node_tree.nodes if node.type == 'BSDF_PRINCIPLED'][0]
        sett.skin_sss = 'off' if principled_bsdf.inputs['Subsurface'].default_value == 0 else 'on'
    except:
        print('could not set subsurface toggle')


    sett.update_exception = False
    context = bpy.context
    #updates the preview_collection of the active tab to make sure the options are right for the gender of the current human
    if sett.active_ui_tab == 'TOOLS':   
        refresh_modapply(self, context)
        refresh_shapekeys_ul(self, context)
        refresh_hair_ul(self, context)
        refresh_outfit_ul(self, context)
        return
    elif ui_phase == 'body':
        refresh_body_scaling(self, sett, hg_rig.HG.body_obj)
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

def tab_change_update(self, context):
    refresh_modapply(self, context)
    refresh_shapekeys_ul(self, context)
    refresh_hair_ul(self, context)
    refresh_outfit_ul(self, context)

def refresh_body_scaling(self, sett, hg_body):
    pass