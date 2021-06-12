import bpy #type: ignore
from ... features.common.HG_COMMON_FUNC import find_human

def toggle_sss(self, context):
    '''
    turns subsurface on and off
    '''
    
    if context.scene.HG3D.update_exception:
        return

    toggle          = context.scene.HG3D.skin_sss
    hg_rig          = find_human(context.object)
    hg_body         = hg_rig.HG.body_obj
    mat             = hg_body.data.materials[0]
    principled_bsdf = [node for node in mat.node_tree.nodes if node.type == 'BSDF_PRINCIPLED'][0]

    principled_bsdf.inputs['Subsurface'].default_value = 0.015 if toggle == 'on' else 0


