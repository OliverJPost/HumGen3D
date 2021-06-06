'''
Operator and corresponding functions for the next_tab and next_phase buttons
'''

from . HG_INFO_POPUPS import HG_OT_INFO
import bpy #type: ignore
from . HG_COMMON_FUNC import ShowMessageBox, find_human, apply_shapekeys, add_to_collection
from . HG_LENGTH import apply_armature, apply_length_to_rig, add_applied_armature
from . HG_PCOLL import refresh_pcoll
import time
import mathutils #type: ignore
from math import radians
from . HG_POSE import import_pose
from pathlib import Path


class HG_FINISH_CREATION(bpy.types.Operator):
    """
    Button in the creation phase for going to the next tab. 
    """
    bl_idname = "hg3d.finishcreation"
    bl_label = "Click to confirm. You can't go back to previous tabs"
    bl_description = "Complete creation phase, moving on to finalizing phase"
    bl_options = {"UNDO"}

    def execute(self,context):
        sett = context.scene.HG3D
        pref = context.preferences.addons[__package__].preferences

        hg_rig = find_human(context.active_object)
        hg_rig.select_set(True)
        hg_rig.hide_set(False)
        hg_rig.hide_viewport = False
        bpy.context.view_layer.objects.active = hg_rig
        HG = hg_rig.HG
        hg_body = HG.body_obj

        for obj in context.selected_objects:
            if obj != hg_rig:
                obj.select_set(False)

        for mod in [m for m in hg_body.modifiers if m.type == 'PARTICLE_SYSTEM']:
            ps_sett = mod.particle_system.settings
            if ps_sett.child_nbr > 1:
                ps_sett.child_nbr = 1
                self.report({'INFO'}, 'Hair children were hidden to improve performance. This can be turned off in preferences')
                if pref.auto_hide_popup:
                    HG_OT_INFO.ShowMessageBox(None, 'autohide_hair')

        finish_creation_phase(self, context, hg_rig, hg_body)     
        hg_rig.HG.phase = 'clothing'       
        
        if not pref.auto_hide_hair_switch:
            for mod in [m for m in hg_body.modifiers if m.type == 'PARTICLE_SYSTEM']:
                ps_sett = mod.particle_system.settings
                ps_sett.child_nbr = ps_sett.rendered_child_count

        return {'FINISHED'}

    def invoke(self, context, event):
        pref = context.preferences.addons[__package__].preferences
        
        if pref.show_confirmation:
            return context.window_manager.invoke_confirm(self, event)


def finish_creation_phase(self, context, hg_rig, hg_body):
    HG= hg_rig.HG
    sett = context.scene.HG3D
    old_shading = context.space_data.shading.type
    context.space_data.shading.type = 'SOLID'

    context.view_layer.objects.active = hg_body
    remove_unused_eyebrows(hg_body)
    context.view_layer.objects.active = hg_rig
    
    sk = hg_body.data.shape_keys.key_blocks if hg_body.data.shape_keys else []

    set_backup(context, hg_rig)   

    context.view_layer.objects.active = hg_rig

    sk_dict, driver_dict = corrective_shapekey_copy(context, hg_body)

    apply_shapekeys(hg_body)

    context.view_layer.objects.active = hg_rig
    hg_eyes = [child for child in hg_rig.children if 'hg_eyes' in child][0]
    hg_teeth = [child for child in hg_rig.children if 'hg_teeth' in child]

    child_list = [hg_eyes, hg_body, hg_teeth[0], hg_teeth[1]]

    for obj in child_list: 
        apply_armature(hg_rig, obj)

    apply_length_to_rig(hg_rig)

    context.view_layer.objects.active = hg_rig
    hg_rig.select_set(True)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

    for obj in context.selected_objects:
        obj.select_set(False)
    context.view_layer.objects.active = hg_rig
    remove_stretch_bones(hg_rig)

    for obj in  [hg_eyes, hg_body, hg_teeth[0], hg_teeth[1]]: 
        add_applied_armature(hg_rig, obj)     

    reapply_shapekeys(context, sk_dict, hg_body, driver_dict)

    context.view_layer.objects.active = hg_rig
    remove_teeth_constraint(hg_rig)
    set_teeth_parent(hg_rig)

    refresh_pcoll(self, context, 'poses')

    HG.length = hg_rig.dimensions[2]

    #force recalculation of shapekeys
    sk = hg_body.data.shape_keys.key_blocks
    sk['cor_ShoulderSideRaise_Lt'].mute = True
    sk['cor_ShoulderSideRaise_Lt'].mute = False

    sett.summer_toggle = True
    sett.normal_toggle = True
    sett.winter_toggle = True
    sett.inside_toggle = True
    sett.outside_toggle = True

    context.space_data.shading.type = old_shading

def remove_teeth_constraint(hg_rig):
    p_bones = hg_rig.pose.bones
    p_bones["jaw"].constraints["Damped Track"].mute = False
    
    for bone in [p_bones['jaw'], p_bones['jaw_upper']]:
        child_constraints = [c for c in bone.constraints if c.type == 'CHILD_OF']
        for c in child_constraints:
            bone.constraints.remove(c)
        
def set_teeth_parent(hg_rig):
    bpy.ops.object.mode_set(mode='EDIT')
    e_bones = hg_rig.data.edit_bones
    for b_name in ['jaw', 'jaw_upper']:
        e_bones[b_name].parent = e_bones['head']
    bpy.ops.object.mode_set(mode='OBJECT')

def set_backup(context, hg_rig):
    hg_backup = hg_rig.copy()
    hg_rig.HG.backup = hg_backup
    hg_backup.data = hg_backup.data.copy()
    hg_backup.name = hg_rig.name + '_Backup'
    

    context.collection.objects.link(hg_backup)
    hg_backup.hide_viewport = True
    hg_backup.hide_render = True
    add_to_collection(context, hg_backup, collection_name = "HumGen_Backup [Don't Delete]")
    
    for obj in hg_rig.children:
        obj_copy = obj.copy()
        obj_copy.data = obj_copy.data.copy()
        context.collection.objects.link(obj_copy)
        add_to_collection(context, obj_copy, collection_name = "HumGen_Backup [Don't Delete]")
        obj_copy.parent = hg_backup
        armatures = [mod for mod in obj_copy.modifiers if mod.type == 'ARMATURE']
        if armatures:
            armatures[0].object = hg_backup
        obj_copy.hide_viewport = True
        obj_copy.hide_render = True


    hg_backup.matrix_parent_inverse = hg_rig.matrix_world.inverted()
    hg_backup.select_set(False)

############################
##### DONT REMOVE #########
###########################

# def set_t_pose(hg_rig):
#     bones = hg_rig.pose.bones
#     for upper_arm in [bones[bone_name] for bone_name in ('upper_arm.L', 'upper_arm.R')]:
#         #rot = mathutils.Matrix.Rotation(radians(45), 4, 'Z')
#         #upper_arm.matrix_world *= rot
#         upper_arm.rotation_mode = 'XYZ'
#         upper_arm.rotation_euler[2] = 43 if upper_arm.name.endswith(.L) else -43
#     for forearm in [bones[bone_name] for bone_name in ('forearm.L', 'forearm.R')]:
#         forearm.rotation_euler.rotate_axis("X", radians(27))

# def rotate_bone(bone, rot_x = 0.0, rot_z = 0.0):
#     global_rotation = mathutils.Euler((rot_x, 0.0, rot_z))
#     rot_matrix = bone.rotation_euler.to_matrix()
#     rot_matrix.invert()
#     local_rotation = global_rotation @ rot_matrix
#     bone.rotation_euler += local_rotation

def remove_stretch_bones(hg_rig):
    bpy.ops.object.mode_set(mode='POSE')
    for bone in hg_rig.pose.bones:
        copyLocConstraints = [ c for c in bone.constraints if c.type == 'STRETCH_TO' ]
        
        for c in copyLocConstraints:
            bone.constraints.remove(c) 
    bpy.ops.object.mode_set(mode='EDIT')
    remove_list = []
    for bone in hg_rig.data.edit_bones:
        if bone.name.startswith('stretch'):
            remove_list.append(bone)      
    for bone in remove_list:
        hg_rig.data.edit_bones.remove(bone)
    bpy.ops.object.mode_set(mode='OBJECT')    

def corrective_shapekey_copy(context, hg_body, apply_armature = True):
    pref = context.preferences.addons[__package__].preferences
    
    obj_list = []
    

    
    try:
        test = hg_body.data.shape_keys.animation_data.drivers
    except Exception as e:
        print('returning None for ', hg_body, e)
        return None, None

    driver_dict = build_driver_dict(hg_body)
        
    sk = hg_body.data.shape_keys.key_blocks if hg_body.data.shape_keys else []
    for shapekey in sk:
        if not shapekey.name.startswith('cor_') and not pref.keep_all_shapekeys:
            continue
        ob = hg_body.copy()
        ob.data = ob.data.copy()
        context.collection.objects.link(ob)
        ob.name = shapekey.name
        obj_list.append(ob)

        face_sk = ob.data.shape_keys.key_blocks[shapekey.name]
        face_sk.mute = False
        face_sk.value = 1
        apply_shapekeys(ob)
        if apply_armature:
            bpy.ops.object.modifier_apply(modifier="HG_Armature")  

    return obj_list, driver_dict

def build_driver_dict(obj, remove = True):
    driver_dict = {}
    remove_list = []
    for driver in obj.data.shape_keys.animation_data.drivers:
        target_sk = driver.data_path.replace('key_blocks["', '').replace('"].value', '')
        expression = driver.driver.expression
        var = driver.driver.variables[0]
        target = var.targets[0]
        target_bone = target.bone_target
        transform_type = target.transform_type
        transform_space = target.transform_space
        driver_dict[target_sk] = {'expression': expression, 'target_bone': target_bone, 'transform_type': transform_type, 'transform_space': transform_space}
        remove_list.append(driver)
    if remove:
        for driver in remove_list:
            obj.data.shape_keys.animation_data.drivers.remove(driver)
    
    return driver_dict

def reapply_shapekeys(context, sk_objects, hg_body, driver_dict):
    for ob in context.selected_objects:
        ob.select_set(False)
    context.view_layer.objects.active = hg_body
    hg_body.select_set(True)

    for ob in sk_objects:
        ob.select_set(True)
        bpy.ops.object.join_shapes()
        ob.select_set(False)
        if ob.name in driver_dict:
            target_sk = hg_body.data.shape_keys.key_blocks[ob.name]
            add_driver(hg_body, target_sk, driver_dict[ob.name])

    for ob in sk_objects:
        print('deleting', ob.name)
        bpy.data.objects.remove(ob)

def add_driver(hg_body, target_sk, sett_dict):
    driver = target_sk.driver_add('value').driver
    var = driver.variables.new()
    var.type = 'TRANSFORMS'
    target = var.targets[0]
    target.id = hg_body.parent

    driver.expression = sett_dict['expression']
    target.bone_target = sett_dict['target_bone']
    target.transform_type = sett_dict['transform_type']
    target.transform_space = sett_dict['transform_space']

def remove_unused_eyebrows(hg_body):
    print('body', hg_body, hg_body.name)

    eyebrows = [mod for mod in hg_body.modifiers if mod.type == 'PARTICLE_SYSTEM' and mod.particle_system.name.startswith('Eyebrows')]
    print('eyebrows', eyebrows)
    remove_list = [mod.particle_system.name for mod in eyebrows if not mod.show_render]
    print('remove list', remove_list)
    
    if len(eyebrows) == len(remove_list):
        ShowMessageBox(message = "All eyebrow systems are hidden (render), please manually remove particle systems you aren't using")
        return
    
    for remove_name in remove_list:   
        ps_idx = [i for i, ps in enumerate(hg_body.particle_systems) if ps.name == remove_name]
        hg_body.particle_systems.active_index = ps_idx[0]
        bpy.ops.object.particle_system_remove()  