"""
Operators and functions relating to the posing of the human
"""

import bpy #type: ignore
from pathlib import Path
import os
from . HG_COMMON_FUNC import add_to_collection, find_human
from . HG_PCOLL import refresh_pcoll

class HG_RIGIFY(bpy.types.Operator):
    """
    Changes the rig to make it compatible with Rigify, then generates the rig
    """
    bl_idname = "hg3d.rigify"
    bl_label = "Generate Rigify Rig"
    bl_description = "Generates a Rigify rig for this human"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self,context):
        hg_rig = find_human(context.active_object)
        context.view_layer.objects.active = hg_rig
        hg_body = hg_rig.HG.body_obj
            
        bpy.ops.object.mode_set(mode='POSE')
        for posebone in hg_rig.pose.bones:
            posebone.bone.select = True
        
        bpy.ops.pose.transforms_clear()
        bpy.ops.object.mode_set(mode='OBJECT')

        try:
            bpy.ops.pose.rigify_generate()
        except Exception as e:
            print('Rigify Error:', e)
            self.report({'WARNING'}, 'Something went wrong, please check if Rigify is enabled')
            return {'FINISHED'}
               
        rigify_rig = self.find_created_rigify_rig(context)
        self.rename_vertex_groups(hg_body)
        add_to_collection(context, rigify_rig)
        rigify_rig.name = hg_rig.name + '_RIGIFY'

        self.iterate_children(hg_rig, rigify_rig)
        self.set_HG(hg_rig, rigify_rig)

        armature_mod = [mod for mod in hg_body.modifiers if mod.type == 'ARMATURE'][0]
        armature_mod.object = rigify_rig

        bpy.data.objects.remove(hg_rig)
        return {'FINISHED'}

    def rename_vertex_groups(self, obj):
        """
        renames vertex groups to match the rigify naming convention
        """
        for vg in obj.vertex_groups:
            prefix_list = ('mask', 'pin', 'def-', 'hair', 'fh', 'sim', 'lip')
            if not vg.name.lower().startswith(prefix_list):
                vg.name = 'DEF-' + vg.name    

    def set_HG(self, hg_rig, rigify_rig):
        nHG = rigify_rig.HG
        HG = hg_rig.HG
        nHG.ishuman = True
        nHG.phase = HG.phase
        nHG.gender = HG.gender
        nHG.body_obj = HG.body_obj
        nHG.backup = HG.backup
        nHG.length = HG.length

    def iterate_children(self, hg_rig, rigify_rig):
        for child in hg_rig.children:
            child.parent = rigify_rig
            child_armature = [mod for mod in child.modifiers if mod.type == 'ARMATURE']
            if child_armature:
                child_armature[0].object = rigify_rig
                self.rename_vertex_groups(child)
                self.correct_drivers(child, rigify_rig)

    def find_created_rigify_rig(self, context):
        unused_rigify_rigs = [obj for obj 
            in bpy.data.objects 
            if obj.type == 'ARMATURE' 
                and 'rig_id' in obj.data 
                and not obj.children 
                and not 'hg_rigify' in obj.data]  

        for rig in unused_rigify_rigs:
            if rig in context.selected_objects:
                rigify_rig = rig
                rigify_rig.data['hg_rigify'] = 1

        return rigify_rig
    
    def correct_drivers(self, obj, rigify_rig):
        if not obj.data.shape_keys or not obj.data.shape_keys.animation_data:
            return
        for driver in obj.data.shape_keys.animation_data.drivers:            
            var = driver.driver.variables[0]
            target = var.targets[0]
            target.id = rigify_rig    
            target.bone_target = 'DEF-' + target.bone_target        


def import_pose(context):
    pref = context.preferences.addons[__package__].preferences

    blendfile = str(pref.filepath) + context.scene.HG3D.pcoll_poses
    with bpy.data.libraries.load(blendfile, link = False) as (data_from ,data_to):
        data_to.objects = ['HG_Pose']

    hg_pose = data_to.objects[0]
    if not hg_pose:
        print('could not load pose:', context.scene.HG3D.pcoll_poses)
    
    scene = context.scene
    scene.collection.objects.link(hg_pose)
    return hg_pose

def lrs_keyframe(object, frame):
    #loc rotation scale keyframe  
    object.keyframe_insert(data_path="location", frame=frame)
    if object.rotation_mode == "QUATERNION":
        object.keyframe_insert(data_path = 'rotation_quaternion', frame = frame)
    else:
        object.keyframe_insert(data_path = 'rotation_euler', frame = frame)
 

def copy_pose(context, pose):
    for obj in context.selected_objects:
        obj.select_set(False)

    pose.select_set(True)
    context.view_layer.objects.active = pose
    
    bpy.ops.object.mode_set(mode='POSE')
    
    for posebone in pose.pose.bones:
        posebone.bone.select = True
    
    bpy.ops.pose.copy()
    bpy.ops.object.mode_set(mode='OBJECT')

def apply_pose(self, context):
    sett = context.scene.HG3D
    pref = context.preferences.addons[__package__].preferences
    
    if sett.load_exception:
        return
    hg_rig = find_human(context.active_object)
    hg_pose = import_pose(context)
    
    copy_pose(context, hg_pose)

    hg_rig.hide_set(False)
    hg_rig.hide_viewport = False

    context.view_layer.objects.active = hg_rig

    hg_pose.select_set(False)
    hg_rig.select_set(True)

    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.paste()

    bpy.ops.object.mode_set(mode='OBJECT')
    
    if not pref.debug_mode:
        bpy.data.objects.remove(hg_pose)

    # footwear = [child for child in hg_rig.children if 'shoe' in child]    
    # for shoe in footwear:
    #     set_high_heel_rotation(hg_rig, shoe)

# def set_high_heel_rotation(hg_rig, hg_shoe):
#     bones = hg_rig.pose.bones
#     print('setting high heel')
#     for foot in [bones[bone_name] for bone_name in ('foot.L', 'foot.R')]:
#         if 'foot_rot_x' in hg_shoe:
#             print('found foot rot')
#             foot.rotation_mode = 'XYZ'
#             print('before', foot.rotation_euler[0])
#             print(hg_shoe['foot_rot_x'])
            
#             foot.rotation_euler[0] += hg_shoe['foot_rot_x']
#             print('after', foot.rotation_euler[0])
#     for toe in [bones[bone_name] for bone_name in ('toe.L', 'toe.R')]:
#         if 'toe_rot_x' in hg_shoe:
#             toe.rotation_mode = 'XYZ'
#             toe.rotation_euler[0] += hg_shoe['toe_rot_x']
#         if 'toe_rot_z' in hg_shoe:
#             foot.rotation_euler[2] += hg_shoe['toe_rot_z']
