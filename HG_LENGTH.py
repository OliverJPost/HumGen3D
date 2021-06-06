'''
Operators and functions for changing the length of the human
'''

import bpy #type: ignore
from . HG_COMMON_FUNC import find_human
import random
import time
import mathutils #type: ignore
import numpy #type: ignore

class HG_UPDATE_LENGTH(bpy.types.Operator):
    """
    plus or minus button to change the length of the human
    """
    bl_idname = "hg3d.updatelength"
    bl_label = "Update Length"
    bl_description = 'Update Length'
    bl_options = {"REGISTER", "UNDO"}

    longer : bpy.props.BoolProperty()

    def invoke(self, context, event):
        self.small_incement = event.ctrl
        return self.execute(context)

    def execute(self,context):
        longer = self.longer
        #update_length(context, longer, small_increment = self.small_incement)
        return {'FINISHED'}


class HG_RANDOM_LENGTH(bpy.types.Operator):
    """
    plus or minus button to change the length of the human
    """
    bl_idname = "hg3d.randomlength"
    bl_label = "Random Length"
    bl_description = 'Random Length'
    bl_options = {"UNDO"}

    def execute(self,context):
        sett = context.scene.HG3D
        sett.human_length = random.randrange(150, 200)
        return {'FINISHED'}


def update_length_v2(self, context):
    hg_rig = find_human(context.active_object)
    hg_body = hg_rig.HG.body_obj
    sett = context.scene.HG3D
    
    if context.scene.HG3D.update_exception:
        return

    multiplier = ((2*sett.human_length)/100 -4)*-1
    print('mult', multiplier)
    old_length = hg_rig.dimensions[2]

    stretch_bone_dict = {
        'stretch_upper_arm': {'sym': True, 'max_loc': (0, 0.0255, 0), 'min_loc': (0, -0.051, 0)},
        'stretch_forearm': {'sym': True, 'max_loc': (0, 0.0204, 0), 'min_loc': (0, -0.0408, 0)},
        'stretch_thigh': {'sym': True, 'max_loc': (0, 0.0468, 0), 'min_loc': (0, -0.0936, 0)},
        'stretch_shin': {'sym': True, 'max_loc': (0, 0.0408, 0), 'min_loc': (0, -0.0816, 0)},
        'stretch_foot': {'sym': True, 'max_loc': (0, 0.0066, 0.004286), 'min_loc': (0, -0.0132, -0.008571)},
        'stretch_spine': {'sym': False, 'max_loc': (0, 0.0214, 0), 'min_loc': (0, -0.0428, 0)},
        'stretch_spine.001': {'sym': False, 'max_loc': (0, 0.0214, 0), 'min_loc': (0, -0.0428, 0)},
        'stretch_spine.002': {'sym': False, 'max_loc': (0, 0.0107, 0), 'min_loc': (0, -0.0214, 0)},
        'stretch_spine.003': {'sym': False, 'max_loc': (0, 0.0107, 0), 'min_loc': (0, -0.0214 , 0)},
        'stretch_neck': {'sym': False, 'max_loc': (0, 0.0108, 0), 'min_loc': (0, -0.0214, 0)},
        'stretch_head': {'sym': False, 'max_loc': (0, 0.0015, 0), 'min_loc': (0, -0.003, 0)},
    }

    bones = hg_rig.pose.bones

    for stretch_bone, bone_data in stretch_bone_dict.items():
        if bone_data['sym']:
            bone_list = [bones[f'{stretch_bone}.R'], bones[f'{stretch_bone}.L']]
        else:
            bone_list = [bones[stretch_bone],]

        xyz_substracted = numpy.subtract(bone_data['max_loc'], bone_data['min_loc'])
        xyz_multiplied = tuple([multiplier*x for x in xyz_substracted])
        x_y_z_location = numpy.subtract(bone_data['max_loc'], xyz_multiplied)

        for b in bone_list:
            b.location = x_y_z_location
    
    new_length =  sett.human_length/100
    c_global = hg_body.matrix_world @ hg_body.data.vertices[21085].co
    #hg_rig.location[2] += origin_correction(new_length) - c_global[2]# - origin_correction(new_length)

#FIXME inaccurate, causing position shifting
def origin_correction(length):
    return -0.553*length + 1.0114

#REMOVE
def update_length(context, longer, hg_rig = None, small_increment = False):
    if not hg_rig:
        hg_rig = find_human(context.active_object)

    #return if the human would become too tall or too short
    if hg_rig.dimensions[2] <1.51 and not longer:
        return
    elif hg_rig.dimensions[2]  > 1.95 and longer:
        return

    upper_arm_controls = 'stretch_upper_arm'
    forearm_controls = 'stretch_forearm'
    thigh_controls = 'stretch_thigh'
    shin_controls = 'stretch_shin'
    foot_controls = 'stretch_foot'

    #in centimeters
    translation_value = {upper_arm_controls: .85, forearm_controls: .68, thigh_controls: 1.56, shin_controls:  1.36, foot_controls: .22}

    for control_bone in (upper_arm_controls, forearm_controls, thigh_controls, shin_controls, foot_controls):
        for suff in ('.L', '.R'):
            y_value = translation_value[control_bone]
            move_bone(hg_rig.pose.bones[control_bone+suff], 'y', y_value*.01 if longer else y_value*-.01 )

    spine_controls_short = ('stretch_spine{}'.format(suff) for suff in ['', '.001'])
    spine_controls_long = ('stretch_spine{}'.format(suff) for suff in [ '.002', '.003'])
    neck_controls = ('stretch_neck',)
    head_controls = ('stretch_head',)

    z_change = translation_value[shin_controls]/100 + translation_value[thigh_controls]/100
    
    hg_rig.location[2] += z_change + 0.0013 if longer else z_change*-1 - 0.0013

    #in centimeters
    translation_value2 = {spine_controls_short: 2.14/3, spine_controls_long: 2.14/6, neck_controls: .36, head_controls: .05}

    for control_bone_list in (spine_controls_short, spine_controls_long, neck_controls, head_controls):
        y_value = translation_value2[control_bone_list]
        for bone in control_bone_list:
            move_bone(hg_rig.pose.bones[bone], 'y', y_value*.01 if longer else y_value * -.01 )

    for bone_name in ['stretch_foot.L', 'stretch_foot.R']:
        bone = hg_rig.pose.bones[bone_name]
        bone.location += mathutils.Vector((0.0,0.0, 0.01/7)) if longer else mathutils.Vector((0.0,0.0, -0.01/7))

def apply_armature(hg_rig, obj):
    bpy.context.view_layer.objects.active = obj
    armature_mods = [mod.name for mod in obj.modifiers if mod.type == 'ARMATURE']
    for mod_name in armature_mods:
        bpy.ops.object.modifier_apply(modifier=mod_name)    

def apply_length_to_rig(hg_rig):
    '''
    Applies the rig
    Also sets the correct origin position
    '''

    rig_length = hg_rig.dimensions[2]
    bpy.context.view_layer.objects.active = hg_rig
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.armature_apply(selected = False)


    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.transform_apply(location = False, rotation = False, scale = True)

    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    bpy.context.scene.cursor.location = hg_rig.location

    new_origin_loc = bpy.context.scene.cursor.location[2] - ((rig_length*0.5473) - 1.0026) #formula for compensating length changes
    bpy.context.scene.cursor.location[2] = new_origin_loc
    
    bpy.context.view_layer.objects.active = hg_rig


def add_applied_armature(hg_rig, obj):
    bpy.context.view_layer.objects.active = hg_rig
    obj.select_set(True)
    
    armature = obj.modifiers.new("Armature", 'ARMATURE')
    armature.object = hg_rig
    
    bpy.context.view_layer.objects.active = obj
    if (2, 90, 0) > bpy.app.version: #use old method for versions older than 2.90
        while obj.modifiers.find("Armature") != 0: 
            bpy.ops.object.modifier_move_up({'object': obj}, modifier="Armature")
    else:
        bpy.ops.object.modifier_move_to_index(modifier="Armature", index=0)

    bpy.context.view_layer.objects.active = hg_rig


def random_length(context, hg_rig):
    z_dim = hg_rig.dimensions[2] 
    if z_dim < 1.61:
        longer = True
        exc = True
    elif z_dim > 1.89:
        longer = False
        exc = True
    else:
        longer = random.choice([True, False])
        exc = False

    amount = random.randint(1,5)
    for i in range(amount):
        z_dim = hg_rig.dimensions[2] 
        length_range = True if z_dim > 1.61 and z_dim < 1.89 else False
        if exc or length_range:
            update_length(context, longer)

def move_bone(bone, axis, translation):        
    global_translation = mathutils.Vector((0.0, translation, 0.0))
    rot_matrix = bone.rotation_euler.to_matrix()
    rot_matrix.invert()
    local_translation = global_translation @ rot_matrix
    bone.location = bone.location + local_translation
