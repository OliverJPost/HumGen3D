'''
Operators and functions for changing the length of the human
'''

import random

import bpy  # type: ignore
import numpy  # type: ignore

from ...features.common.HG_COMMON_FUNC import find_human


class HG_RANDOM_LENGTH(bpy.types.Operator):
    """Randomizes the length of the human between an even range of 150-200

    Operator type:
        Length
    
    Prereq:
        Active object is part of a HumGen human
    """
    bl_idname      = "hg3d.randomlength"
    bl_label       = "Random Length"
    bl_description = 'Random Length'
    bl_options     = {"UNDO"}

    def execute(self,context):
        sett = context.scene.HG3D
        sett.human_length = random.randrange(150, 200)
        return {'FINISHED'}

def update_length(self, context):
    """Called by human_length prop, changes stretch bone position in order to
    set length of the active human
    """
    if context.scene.HG3D.update_exception:
        return
    
    hg_rig  = find_human(context.active_object)
    hg_body = hg_rig.HG.body_obj
    sett    = context.scene.HG3D
    
    multiplier = ((2*sett.human_length)/100 -4)*-1
    old_length = hg_rig.dimensions[2]

    stretch_bone_dict = _get_stretch_bone_dict()

    bones = hg_rig.pose.bones

    for stretch_bone, bone_data in stretch_bone_dict.items():
        _set_stretch_bone_position(multiplier, bones, stretch_bone, bone_data)

    context.view_layer.update() #Requires update to get new length of rig
    hg_rig  = find_human(context.active_object)
    new_length = hg_rig.dimensions[2]
    hg_rig.location[2] += origin_correction(old_length) - origin_correction(new_length)

def _get_stretch_bone_dict() -> dict:
    """Dictionary to base stretch bone position on.

    Returns:
        dict:
            key (str): stretch bone name (does not inlude .R, .L suffix)
            value (dict):
                key 'sym':
                    value (bool): True if bones should have .R and .L suffix 
                        for symmetry
                key 'mac_loc':
                    value (FloatVectorProperty): local x,y,z location for stretch
                        bones in maximum position (human at 2.0m)
                key 'min_loc':
                    value (FloatVectorProperty): local x,y,z location for stretch
                        bones in minimum position (human at 1.5m)
        
    """
    stretch_bone_dict = {
        'stretch_upper_arm': {'sym': True,  'max_loc': (0, 0.0255, 0),          'min_loc': (0, -0.051, 0)},
        'stretch_forearm'  : {'sym': True,  'max_loc': (0, 0.0204, 0),          'min_loc': (0, -0.0408, 0)},
        'stretch_thigh'    : {'sym': True,  'max_loc': (0, 0.0468, 0),          'min_loc': (0, -0.0936, 0)},
        'stretch_shin'     : {'sym': True,  'max_loc': (0, 0.0408, 0),          'min_loc': (0, -0.0816, 0)},
        'stretch_foot'     : {'sym': True,  'max_loc': (0, 0.0066, 0.004286),   'min_loc': (0, -0.0132, -0.008571)},
        'stretch_spine'    : {'sym': False, 'max_loc': (0, 0.0214, 0),          'min_loc': (0, -0.0428, 0)},
        'stretch_spine.001': {'sym': False, 'max_loc': (0, 0.0214, 0),          'min_loc': (0, -0.0428, 0)},
        'stretch_spine.002': {'sym': False, 'max_loc': (0, 0.0107, 0),          'min_loc': (0, -0.0214, 0)},
        'stretch_spine.003': {'sym': False, 'max_loc': (0, 0.0107, 0),          'min_loc': (0, -0.0214 , 0)},
        'stretch_neck'     : {'sym': False, 'max_loc': (0, 0.0108, 0),          'min_loc': (0, -0.0214, 0)},
        'stretch_head'     : {'sym': False, 'max_loc': (0, 0.0015, 0),          'min_loc': (0, -0.003, 0)},
    }
    
    return stretch_bone_dict

def _set_stretch_bone_position(multiplier, bones, stretch_bone, bone_data):
    """Sets the position of this stretch bone according along the axis between
    'max_loc' and 'min_loc', based on passed multiplier

    Args:
        multiplier (float): value between 0 and 1, where 0 is 'min_loc' and 
            1 is 'max_loc' #CHECK if this is correct
        bones (PoseBone list): list of all posebones on hg_rig
        stretch_bone (str): name of stretch bone to adjust
        bone_data (dict): dict passed on from stretch_bone_dict containing 
            symmetry and transformation data (see _get_stretch_bone_dict.__doc__)
    """
    
    if bone_data['sym']:
        bone_list = [bones[f'{stretch_bone}.R'], bones[f'{stretch_bone}.L']]
    else:
        bone_list = [bones[stretch_bone],]

    xyz_substracted = numpy.subtract(bone_data['max_loc'], bone_data['min_loc'])
    xyz_multiplied  = tuple([multiplier*x for x in xyz_substracted])
    x_y_z_location  = numpy.subtract(bone_data['max_loc'], xyz_multiplied)

    for b in bone_list:
        b.location = x_y_z_location

    
def origin_correction(length):
    #DOCUMENT
    return -0.553*length + 1.0114

def apply_armature(obj):
    """Applies all armature modifiers on this object

    Args:
        obj (Object): object to apply armature modifiers on
    """
    bpy.context.view_layer.objects.active = obj
    armature_mods = [mod.name for mod in obj.modifiers 
                     if mod.type == 'ARMATURE']
    for mod_name in armature_mods:
        bpy.ops.object.modifier_apply(modifier=mod_name)    

def apply_length_to_rig(hg_rig, context):
    '''
    Applies the pose to the rig, Also sets the correct origin position
    
    Args:
        hg_rig (Object): Armature of HumGen human
    '''

    rig_length = hg_rig.dimensions[2]
    
    bpy.context.view_layer.objects.active = hg_rig
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.armature_apply(selected = False)

    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.transform_apply(location = False,
                                   rotation = False,
                                   scale = True)

    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    

    correct_origin(context, hg_rig, hg_rig.HG.body_obj)
    
    bpy.context.view_layer.objects.active = hg_rig

def correct_origin(context, obj_to_correct, hg_body):
    """Uses a formula to comensate the origina position for legnth changes

    """
    context.scene.cursor.location = obj_to_correct.location

    bottom_vertex_loc = hg_body.matrix_world @ hg_body.data.vertices[21085].co #RELEASE check if this is still the bottom vertex


    context.scene.cursor.location[2] = bottom_vertex_loc[2]

    context.view_layer.objects.active = obj_to_correct
    obj_to_correct.select_set(True)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
