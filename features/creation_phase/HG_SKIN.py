import bpy  # type: ignore

from ...features.common.HG_COMMON_FUNC import find_human


def toggle_sss(self, context):
    '''
    Turns subsurface on and off
    '''
    
    if context.scene.HG3D.update_exception:
        return

    toggle  = context.scene.HG3D.skin_sss
    hg_rig  = find_human(context.object)
    hg_body = hg_rig.HG.body_obj
    mat     = hg_body.data.materials[0]
    
    principled_bsdf = [node for node in mat.node_tree.nodes 
                       if node.type == 'BSDF_PRINCIPLED'][0]

    principled_bsdf.inputs['Subsurface'].default_value = (0.015 if toggle == 'on'
                                                          else 0)


def toggle_underwear(self, context):
    '''
    Turns underwear on and off
    '''
    if context.scene.HG3D.update_exception:
        return
   
    toggle  = context.scene.HG3D.underwear_switch
    hg_rig  = find_human(context.object)
    hg_body = hg_rig.HG.body_obj
    mat     = hg_body.data.materials[0]
    
    underwear_node = mat.node_tree.nodes.get('Underwear_Opacity')
    
    underwear_node.inputs[1].default_value = 1 if toggle == 'on' else 0   
