"""
Operators and functions used for clothing, outfits and footwear of the humans.
""" 


import os
from pathlib import Path

import bpy  # type: ignore

from ...core.HG_PCOLL import refresh_pcoll
from ...core.HG_SHAPEKEY_CALCULATOR import (build_distance_dict,
                                            deform_obj_from_difference)
from ...features.common.HG_COMMON_FUNC import (add_to_collection,
                                               apply_shapekeys, find_human,
                                               get_prefs, hg_delete, hg_log)


#FIXME make sure new textures are not duplicated
#TODO make new outfit color random
def load_outfit(self,context, footwear = False):
    """Gets called by pcoll_outfit or pcoll_footwear to load the selected outfit
    
    Args:
        footwear (boolean): True if called by pcoll_footwear, else loads as outfit
    """ 
    pref    = get_prefs()
    sett    = context.scene.HG3D
    hg_rig  = find_human(context.active_object)
    hg_body = hg_rig.HG.body_obj

    hg_rig.hide_set(False)
    hg_rig.hide_viewport = False
    
    #returns immediately if the active item in the preview_collection is the 
    # 'click here to select' icon
    if ((not footwear and sett.pcoll_outfit == 'none')
        or (footwear and sett.pcoll_footwear == 'none')):
        return

    tag = 'shoe' if footwear else 'cloth'
    mask_remove_list = remove_old_outfits(pref, hg_rig, tag)

    cloth_objs, collections = _import_cloth_items(context, sett, pref, hg_rig,
                                                  footwear)
    
    new_mask_list = []
    for obj in cloth_objs:     
        new_mask_list.extend(find_masks(obj))
        obj[tag] = 1 #adds a custom property to the cloth for identifying purposes

        _deform_cloth_to_human(self, context, hg_rig, hg_body, obj)
        
        for mod in obj.modifiers:
            mod.show_expanded = False #collapse modifiers
         
        set_cloth_corrective_drivers(hg_body, obj, obj.data.shape_keys.key_blocks)
         
    #remove collection that was imported along with the cloth objects
    for col in collections:
        bpy.data.collections.remove(col)
    _set_geometry_masks(mask_remove_list, new_mask_list, hg_body)

    #refresh pcoll for consistent 'click here to select' icon
    refresh_pcoll(self, context, 'outfit')

def _deform_cloth_to_human(self, context, hg_rig, hg_body, obj):
    """Deforms the cloth object to the shape of the active HumGen human by using
    HG_SHAPEKEY_CALCULATOR

    Args:
        hg_rig (Object): HumGen armature
        hg_body (Object): HumGen body
        obj (Object): cloth object to deform
    """
    backup_rig = hg_rig.HG.backup
    obj.parent = backup_rig

    backup_rig.HG.body_obj.hide_viewport = False
    backup_body = [obj for obj in backup_rig.children 
                   if 'hg_body' in obj][0]

    backup_body_copy = _copy_backup_with_gender_sk(backup_body)
    distance_dict = build_distance_dict(
        backup_body_copy,
        obj,
        apply=False
    )
    
    obj.parent = hg_rig
    
    deform_obj_from_difference(
        'Body Proportions',
        distance_dict,
        hg_body,
        obj,
        as_shapekey=True
    )
    
    obj.data.shape_keys.key_blocks['Body Proportions'].value = 1
    
    context.view_layer.objects.active = obj
    _set_armature(context, obj, hg_rig)
    context.view_layer.objects.active = hg_rig
    
    hg_delete(backup_body_copy)  
 
def _copy_backup_with_gender_sk(backup_body) -> bpy.types.Object:
    """Creates a copy of the backup human with the correct gender settings and
    all other shapekeys set to 0

    Args:
        backup_body (Object): body of the hidden backup human

    Returns:
        bpy.types.Object: copy of the backup body
    """
    copy      = backup_body.copy()
    copy.data = backup_body.data.copy()
    bpy.context.scene.collection.objects.link(copy)    

    for sk in [sk for sk in copy.data.shape_keys.key_blocks 
               if sk.name not in ['Basis', 'Male']]:
        sk.value = 0

    gender = backup_body.parent.HG.gender

    if gender == 'female':
        return copy
    
    try:
        sk = copy.data.shape_keys.key_blocks
        sk['Male'].value = 1
        apply_shapekeys(copy)
    except:
        pass

    return copy

def _set_geometry_masks(mask_remove_list, new_mask_list, hg_body):
    """Adds geometry mask modifiers to hg_body based on custom properties on the
    imported clothing

    Args:
        mask_remove_list (list): list of masks to remove from the human, that
                                 were added by previous outfits
        new_mask_list (list): list of masks to add that were not on theh human
                              before
        hg_body (Object): HumGen body to add the modifiers on
    """
    #remove duplicates from mask lists
    mask_remove_list = list(set(mask_remove_list))
    new_mask_list    = list(set(new_mask_list))

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

def _set_armature(context, obj, hg_rig):
    """Adds an armature modifier to this cloth object

    Args:
        obj (Object): cloth object to add armature to
        hg_rig (Object): HumGen armature
    """
    #checks if the cloth object already has an armature modifier, adds one if it doesnt
    armature_mods = [mod for mod in obj.modifiers 
                     if mod.type == 'ARMATURE']
    
    if not armature_mods:
        armature_mods.append(obj.modifiers.new("Armature", 'ARMATURE'))
        
    armature_mods[0].object = hg_rig
    _move_armature_to_top(context, obj, armature_mods)

def _move_armature_to_top(context, obj, armature_mods):
    """Moves the armature modifier to the top of the stack

    Args:
        context ([type]): [description]
        obj (Object): object the armature mod is on
        armature_mods (list): list of armature modifiers on this object
    """
    context.view_layer.objects.active = obj
    for mod in armature_mods:
        if (2, 90, 0) > bpy.app.version: #use old method for versions older than 2.90
            while obj.modifiers.find(mod.name) != 0:
                bpy.ops.object.modifier_move_up({'object': obj},
                                                modifier=mod.name)
        else:
            bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)

def _import_cloth_items(context, sett, pref, hg_rig, footwear) -> 'tuple[list, list]':
    """Imports the cloth objects from an external file

    Args:
        context ([type]): [description]
        sett (PropertyGroup): HumGen props
        pref (AddonPreferences): HumGen preferences
        hg_rig (Object): HumGen armature object
        footwear (bool): True if import footwear, False if import clothing

    Returns:
        tuple[list, list]: 
            cloth_objs: list with imported clothing objects
            collections: list with imported collections the cloth objs were in     
    """
    #load the whole collection from the outfit file. It loads collections 
    # instead of objects because this allows loading of linked objects
    pcoll_item = sett.pcoll_footwear if footwear else sett.pcoll_outfit
    blendfile  = str(pref.filepath) + str(Path(pcoll_item))
    with bpy.data.libraries.load(blendfile, link = False) as (data_from ,data_to):
        data_to.collections = data_from.collections
        data_to.texts = data_from.texts

    #appends all collections and objects to scene
    collections = data_to.collections
        
    cloth_objs = []
    for col in collections:
        context.scene.collection.children.link(col)
        for obj in col.objects:
            cloth_objs.append(obj)

    for obj in context.selected_objects:
        obj.select_set(False)

    #loads cloth objects in the humgen collection and sets the rig as their 
    # parent. This also makes sure their rotation and location is correct
    for obj in cloth_objs:
        add_to_collection(context, obj)
        obj.location = (0,0,0)
        obj.parent = hg_rig
        obj.select_set(True)

    #makes linked objects/textures/nodes local
    bpy.ops.object.make_local(type='SELECT_OBDATA_MATERIAL')
    bpy.ops.object.make_local(type='ALL')

    return cloth_objs, collections

def remove_old_outfits(pref, hg_rig, tag) -> list:
    """Removes the cloth objects that were already on the human

    Args:
        pref (AddonPreferences): preferences of HumGen
        hg_rig (Object): HumGen armature
        tag (str): tag for identifying cloth and shoe objects

    Returns:
        list: list of geometry masks that need to be removed
    """
    #removes previous outfit/shoes if the preferences option is True
    mask_remove_list = []
    
    if pref.remove_clothes:  
        for child in [child for child in hg_rig.children]:
            if tag in child:
                mask_remove_list.extend(find_masks(child))
                hg_delete(child)

    return mask_remove_list

def set_cloth_corrective_drivers(hg_body, hg_cloth, sk):
    """Sets up the drivers of the corrective shapekeys on the clothes
    
    Args:
        hg_body (Object): HumGen body object
        sk (list): List of cloth object shapekeys #CHECK
    """  
    try:
        for driver in hg_cloth.data.shape_keys.animation_data.drivers[:]:
            hg_cloth.data.shape_keys.animation_data.drivers.remove(driver)
    except AttributeError:
        pass
    
    for driver in hg_body.data.shape_keys.animation_data.drivers:
        target_sk = driver.data_path.replace('key_blocks["', '').replace('"].value', '') #TODO this is horrible
        
        if target_sk not in [shapekey.name for shapekey in sk]:
            continue
        
        new_driver    = sk[target_sk].driver_add('value')
        new_var       = new_driver.driver.variables.new()
        new_var.type  = 'TRANSFORMS'
        new_target    = new_var.targets[0]
        old_var       = driver.driver.variables[0]
        old_target    = old_var.targets[0]
        new_target.id = hg_body.parent

        new_driver.driver.expression = driver.driver.expression
        new_target.bone_target       = old_target.bone_target
        new_target.transform_type    = old_target.transform_type
        new_target.transform_space   = old_target.transform_space

def find_masks(obj) -> list:
    """Looks at the custom properties of the object, searching for custom tags 
    that indicate mesh masks added for this cloth.
    
    Args:
        obj (Object): object to look for masks on
        
    Retruns:
        mask_list (list): list of str names of masks on this object
    """  
    mask_list = []
    for i in range(10):
        try:
            mask_list.append(obj['mask_{}'.format(i)])
        except:
            continue
    return mask_list

def set_clothing_texture_resolution(clothing_item, resolution_category):
    if resolution_category == 'performance':
        resolution_tag = 'low'
    elif resolution_category == 'optimised':
        resolution_tag = 'medium'
    
    mat = clothing_item.data.materials[0]
    nodes = mat.node_tree.nodes
    
    for node in [n for n in nodes if n.bl_idname == 'ShaderNodeTexImage']:
        image = node.image

        if not image:
            continue
        
        old_color_setting = image.colorspace_settings.name
        
        dir = os.path.dirname(image.filepath)
        filename, ext = os.path.splitext(os.path.basename(image.filepath))
        
        if filename.endswith('_MEDIUM'):
            filename = filename[:-7]
        elif filename.endswith('_LOW'):
            filename = filename[:-4]
            
        if resolution_category == 'high':
            new_filename = filename+ext
        else:
            new_filename = filename + f'_{resolution_tag.upper()}' + ext
        
        new_path = os.path.join(dir, new_filename)    
            
        if not os.path.isfile(new_path):
            hg_log("Could not find other resolution for outfit texture: ", new_path, level = 'WARNING')
            return
        
        new_image = bpy.data.images.load(new_path, check_existing = True)
        node.image = new_image
        new_image.colorspace_settings.name = old_color_setting
        
    