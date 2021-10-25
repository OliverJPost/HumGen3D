import random

import bpy  # type: ignore
import numpy as np #type:ignore

from ...features.common.HG_COMMON_FUNC import find_human


class HG_RESET_FACE(bpy.types.Operator):
    """Resets all face deformation values to 0
    
    Operator type:
        Prop setter
    
    Prereq:
        Active object is part of HumGen human
    """
    bl_idname      = "hg3d.resetface"
    bl_label       = "Reset face"
    bl_description = "Resets all face deformation values to 0"
    bl_options     = {"UNDO"}

    def execute(self,context):
        hg_rig  = find_human(context.object)
        hg_body = hg_rig.HG.body_obj

        face_sk = [sk for sk in hg_body.data.shape_keys.key_blocks
                   if sk.name.startswith('ff_')
                   ]

        for sk in face_sk:
            sk.value = 0

        return {'FINISHED'}
    
def randomize_facial_feature_categ(hg_body, ff_subcateg, use_bell_curve = False):
    """Randomizes the sliders of the passed facial features category

    Args:
        hg_body (Object): body object of a HumGen human
        ff_subcateg (str): subcategory of facial features to randomize, 'all'
            for randomizing all features
    """
    prefix_dict = _get_ff_prefix_dict()
    face_sk = [sk for sk in hg_body.data.shape_keys.key_blocks 
                    if sk.name.startswith(prefix_dict[ff_subcateg])
                    ] 
    all_v = 0
    for sk in face_sk:
        if use_bell_curve:
            new_value = np.random.normal(loc = 0, scale = 0.5)
        else:
            new_value = random.uniform(sk.slider_min, sk.slider_max)
        all_v += new_value
        sk.value = new_value

def _get_ff_prefix_dict() -> dict:
    """Returns facial features prefix dict

    Returns:
        dict: key: internal naming of facial feature category
            value: naming prefix of shapekeys that belong to that category
    """
    prefix_dict = {
            'all'    : 'ff',
            'u_skull': ('ff_a', 'ff_b'),
            'eyes'   : 'ff_c',
            'l_skull': 'ff_d',
            'nose'   : 'ff_e',
            'mouth'  : 'ff_f',
            'chin'   : 'ff_g',
            'cheeks' : 'ff_h',
            'jaw'    : 'ff_i',
            'ears'   : 'ff_j',
            'custom' : 'ff_x'
            }
        
    return prefix_dict
