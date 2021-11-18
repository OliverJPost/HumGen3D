from ...features.common.HG_COMMON_FUNC import find_human


def scale_bones(self, context, bone_type):
    """
    Scales the bones based on the user input
    
    Args:
        bone_type (str): internal name of bone group to scale
    """
    hg_rig       = find_human(context.object)
    sett         = context.scene.HG3D

    if sett.update_exception:
        return

    sc = get_scaling_data(bone_type, sett)
    for bone_name in sc['bones']:
        bone = hg_rig.pose.bones[bone_name]
        x = sc['x']
        y = sc['x'] if sc['y'] == 'copy' else sc['y']
        z = sc['x'] if sc['z'] == 'copy' else sc['z']
        
        bone.scale = (
            x if sc['x'] else bone.scale[0],
            y if sc['y'] else bone.scale[1],
            z if sc['z'] else bone.scale[2]
            )

def get_scaling_data(bone_type, sett, return_whole_dict = False) -> dict:
    """Gets the scaling dict that determines how to scale this body part

    Args:
        bone_type (str): name of slider, which body part to scale
        sett (PropertyGRoup): HumGen props

    Returns:
        dict: 
            key (str) 'x', 'y', 'z': local scaling axis
                value (AnyType): float scaling factor or 'copy' if same as 'x' 
                    scaling factor
            key (str) 'bones': 
                value (list of str): list of bone names to scale   
    """
    size_dict= {
        'head'     : sett.head_size,
        'neck'     : sett.neck_size,
        'shoulder' : sett.shoulder_size,
        'chest'    : sett.chest_size,
        'breast'   : sett.breast_size,
        'forearm'  : sett.forearm_size,
        'upper_arm': sett.upper_arm_size,
        'hips'     : sett.hips_size,
        'thigh'    : sett.thigh_size,
        'shin'     : sett.shin_size,
        'foot'     : sett.foot_size,
        'hand'     : sett.hand_size,
    }

    s = size_dict[bone_type]
    scaling_dict = {
        'head'     : {'x': s/5+0.9,   'y': 'copy', 'z': 'copy', 'bones': ['head']},
        'neck'     : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['neck']},
        'chest'    : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['spine.002', 'spine.003']},
        'shoulder' : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['shoulder.L', 'shoulder.R']},
        'breast'   : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['breast.L', 'breast.R']},
        'forearm'  : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['forearm.L', 'forearm.R']},
        'upper_arm': {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['upper_arm.L', 'upper_arm.R']},
        'hips'     : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['spine.001', 'spine']},
        'thigh'    : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['thigh.L', 'thigh.R']},
        'shin'     : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['shin.L', 'shin.R']},
        'foot'     : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['foot.L', 'foot.R']},
        'hand'     : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['hand.L', 'hand.R']},
    }

    # if experimental:
    #     size = (context.scene.HG3D.chest_size + 0.5)
    # else:
    #     size = (context.scene.HG3D.chest_size + 2.5)/3

    sc = scaling_dict[bone_type]
    if return_whole_dict:
        return scaling_dict
    else:
        return sc
