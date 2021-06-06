"""
Operators and functions used for clothing, outfits and footwear of the humans.
""" 

import bpy #type: ignore
import os
from pathlib import Path
from . HG_COMMON_FUNC import add_to_collection, find_human, apply_shapekeys 
from . HG_PCOLL import refresh_pcoll
from . HG_RANDOM import get_random_from_pcoll
from . HG_DEVTOOLS import HG_SHAPEKEY_CALCULATOR #create_shapekey_from_difference, build_distance_dict

#FIXME make sure new textures are not duplicated
#TODO make new outfit color random
def load_outfit(self,context, footwear = False):
    """
    loads the outfit that is the current active item in the outfit preview_collection
    """  
    pref = context.preferences.addons[__package__].preferences
    sett = context.scene.HG3D
    hg_rig = find_human(context.active_object)    
    hg_body = hg_rig.HG.body_obj
    hg_rig.hide_set(False)
    hg_rig.hide_viewport = False
    
    #returns immediately if the active item in the preview_collection is the 'click here to select' icon
    if (not footwear and sett.pcoll_outfit == 'none') or (footwear and sett.pcoll_footwear == 'none'):
        return

    mask_remove_list, tag = remove_old_outfits(pref, hg_rig, footwear)
    print('print1', [obj for obj in bpy.data.objects if 'hg_body' in obj])

    cloth_objs, distance_dict, collections = import_cloth_items(context, sett, pref, hg_rig, footwear)
    print('print2', [obj for obj in bpy.data.objects if 'hg_body' in obj])
    
    new_mask_list = []
    for obj in cloth_objs:     
        new_mask_list.extend(find_masks(obj))
        obj[tag] = 1 #adds a custom property to the cloth for identifying purposes

        #apply shapekeys if original clothing pack
        if obj.data.shape_keys:
            if 'Shorten' in obj.data.shape_keys.key_blocks:
                obj.data.shape_keys.key_blocks['Shorten'].value = .335
            apply_shapekeys(obj)

        backup_rig = hg_rig.HG.backup
        obj.parent = backup_rig


        backup_rig.HG.body_obj.hide_viewport = False
        backup_body = [obj for obj in backup_rig.children if 'hg_body' in obj][0]
        for sk in [sk for sk in backup_body.data.shape_keys.key_blocks if sk.name not in ['Basis', 'Male']]:
            sk.value = 0

        backup_body_copy = set_gender_sk(backup_body)
        print('print3', [obj for obj in bpy.data.objects if 'hg_body' in obj])
        distance_dict = HG_SHAPEKEY_CALCULATOR.build_distance_dict(self, backup_body_copy, obj, apply = False)    
        print('print4', [obj for obj in bpy.data.objects if 'hg_body' in obj])
        obj.parent = hg_rig
        deform_from_distance(distance_dict, hg_body, obj, context)
        print('print5', [obj for obj in bpy.data.objects if 'hg_body' in obj])
        context.view_layer.objects.active = obj
        set_armature(context, obj, hg_rig)
        print('print6', [obj for obj in bpy.data.objects if 'hg_body' in obj])
        context.view_layer.objects.active = hg_rig
        
        bpy.data.objects.remove(backup_body_copy)
        
        #collapse modifiers
        for mod in obj.modifiers:
            mod.show_expanded = False

    #remove collection that was imported along with the cloth objects
    for col in collections:
        bpy.data.collections.remove(col)

    set_geometry_masks(mask_remove_list, new_mask_list, hg_body)
    print('print7', [obj for obj in bpy.data.objects if 'hg_body' in obj])

    #refresh pcoll for consistent 'click here to select' icon
    refresh_pcoll(self, context, 'outfit')

    

def set_gender_sk(backup_body):
    copy = backup_body.copy()
    copy.data = backup_body.data.copy()
    bpy.context.scene.collection.objects.link(copy)    

    gender = backup_body.parent.HG.gender
    print(gender)
    if gender == 'male':
        try:
            sk = copy.data.shape_keys.key_blocks
            sk['Male'].value = 1
            apply_shapekeys(copy)
        except:
            pass

    return copy

def deform_from_distance(distance_dict, hg_body, cloth_obj, context):
    HG_SHAPEKEY_CALCULATOR.deform_obj_from_difference(None, 'test', distance_dict, hg_body, cloth_obj, as_shapekey = False)
    #cloth_obj.data.shape_keys.key_blocks['test'].value = 1  

def set_geometry_masks(mask_remove_list, new_mask_list, hg_body):
    #remove duplicates from mask lists
    mask_remove_list = list(set(mask_remove_list))
    new_mask_list = list(set(new_mask_list))

    #find the overlap between both lists, these will be ignored
    ignore_masks = list(set(mask_remove_list) & set(new_mask_list))
    for mask in ignore_masks:
        mask_remove_list.remove(mask)
        new_mask_list.remove(mask)

    #remove modifiers used by old clothes
    for mask in mask_remove_list:
        try:
            hg_body.modifiers.remove(hg_body.modifiers.get(mask))
        except:
            pass

    #add new masks used by new clothes
    for mask in new_mask_list:
        mod = hg_body.modifiers.new(mask, 'MASK')
        mod.vertex_group = mask
        mod.invert_vertex_group = True

def set_armature(context, obj, hg_rig):
    #checks if the cloth object already has an armature modifier, adds one if it doesnt
    armature_mods = [mod for mod in obj.modifiers if mod.type == 'ARMATURE']
    if not armature_mods:
        armature_mods.append(obj.modifiers.new("Armature", 'ARMATURE'))
    armature_mods[0].object = hg_rig
    context.view_layer.objects.active = obj
    for mod in armature_mods:
        if (2, 90, 0) > bpy.app.version: #use old method for versions older than 2.90
            while obj.modifiers.find(mod.name) != 0:
                bpy.ops.object.modifier_move_up({'object': obj}, modifier=mod.name)
        else:
            bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)

def import_cloth_items(context, sett, pref, hg_rig, footwear):
    #load the whole collection from the outfit file. It loads collections instead of objects because this allows loading of linked objects
    pcoll_item = sett.pcoll_footwear if footwear else sett.pcoll_outfit
    blendfile = str(pref.filepath) + str(Path(pcoll_item))
    with bpy.data.libraries.load(blendfile, link = False) as (data_from ,data_to):
        data_to.collections = data_from.collections
        data_to.texts = data_from.texts

    #appends all collections and objects to scene
    collections = data_to.collections
    distance_dict = None #data_to.texts['hg_cloth_distance_dict']
        
    cloth_objs = []
    for col in collections:
        context.scene.collection.children.link(col)
        for obj in col.objects:
            cloth_objs.append(obj)

    for obj in context.selected_objects:
        obj.select_set(False)

    #loads cloth objects in the humgen collection and sets the rig as their parent. This also makes sure their rotation and location is correct
    for obj in cloth_objs:
        add_to_collection(context, obj)
        obj.parent = hg_rig
        obj.select_set(True)

    #makes linked objects/textures/nodes local
    bpy.ops.object.make_local(type='SELECT_OBDATA_MATERIAL')
    bpy.ops.object.make_local(type='ALL')

    return cloth_objs, distance_dict, collections

def remove_old_outfits(pref, hg_rig, footwear):
    #removes previous outfit/shoes if the preferences option is True
    mask_remove_list = []
    
    tag = 'shoe' if footwear else 'cloth'
    if pref.remove_clothes:  
        for child in [child for child in hg_rig.children]:
            if tag in child:
                mask_remove_list.extend(find_masks(child))
                bpy.data.objects.remove(child)

    return mask_remove_list, tag

def set_cloth_shapekeys(sk, hg_rig):
    """
    sets the cloth shapekeys to the same value as the human
    """  
    sk_names = ['Muscular', 'Overweight', 'Skinny']

    for i, sk_name in enumerate(sk_names):
        sk[sk_name].mute = False
        sk[sk_name].value = hg_rig.HG.body_shape[i]
    
    if 'Chest' in sk:
        sk['Chest'].mute = False
        sk['Chest'].value = (hg_rig.HG.body_shape[3] * 3) - 2.5

    sk['Shorten'].mute = False
    sk['Shorten'].value = (-1.9801 * hg_rig.HG.length) + 3.8989

def set_cloth_corrective_drivers(hg_body, sk):
    """
    sets up the drivers of the corrective shapekeys on the clothes
    """  
    for driver in hg_body.data.shape_keys.animation_data.drivers:
        target_sk = driver.data_path.replace('key_blocks["', '').replace('"].value', '')
        if target_sk in [shapekey.name for shapekey in sk]:
            new_driver = sk[target_sk].driver_add('value')
            new_var = new_driver.driver.variables.new()
            new_var.type = 'TRANSFORMS'
            new_target = new_var.targets[0]
            old_var = driver.driver.variables[0]
            old_target = old_var.targets[0]
            new_target.id = hg_body.parent

            new_driver.driver.expression = driver.driver.expression
            new_target.bone_target = old_target.bone_target
            new_target.transform_type = old_target.transform_type
            new_target.transform_space = old_target.transform_space

def find_masks(obj):
    """
    looks at the custom properties of the object, searching for custom tags that indicate mesh masks added for this cloth
    """  
    mask_list = []
    for i in range(10):
        try:
            mask_list.append(obj['mask_{}'.format(i)])
        except:
            continue
    
    return mask_list


'''
fix outfits:

stylish casual - tshirt
new intern- shirt collar
relaxed dresscode - shirt
stock exchange - shirt
bbq barry - tshirt
office excursion - shirt
frosty evening - tshirt
'''
