'''
Operator and corresponding functions for finishing the cration phase
'''

import bpy  # type: ignore

from ...core.HG_PCOLL import refresh_pcoll
from ...features.common.HG_COMMON_FUNC import (ShowMessageBox,
                                               add_to_collection,
                                               apply_shapekeys, find_human,
                                               get_prefs, hg_delete, hg_log)
from ...features.common.HG_INFO_POPUPS import HG_OT_INFO
from .HG_LENGTH import apply_armature, apply_length_to_rig


class HG_FINISH_CREATION(bpy.types.Operator):
    """Finish the creation phase, going over:
        -applying body and face shapekeys
        -removing unused eyebrow styles
        -applying the length to the rig
        -correcting the origin after length change
        -adding a backup human for reverting to creation phase
        -changing constraints for posing 
        -removing stretch bones
        -probably more
    
    Operator type:
        HumGen phase change
    
    Prereq:
        Active object is part of a HumGen human
        That human is in creation phase
    """
    bl_idname = "hg3d.finishcreation"
    bl_label = "Click to confirm. You can't go back to previous tabs"
    bl_description = "Complete creation phase, moving on to finalizing phase"
    bl_options = {"UNDO"}

    def execute(self,context):
        pref = get_prefs()

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

        #TODO common func this
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
        pref = get_prefs()
        
        if pref.show_confirmation:
            return context.window_manager.invoke_confirm(self, event)

def finish_creation_phase(self, context, hg_rig, hg_body):
    """For full feature breakdown, see HG_FINISH_CREATION

    Args:
        hg_rig (Object): HumGen armature
        hg_body (Object): HumGen body object
    """
    HG= hg_rig.HG
    try:
        old_shading = context.space_data.shading.type
        context.space_data.shading.type = 'SOLID'
    except:
        pass
    context.view_layer.objects.active = hg_body
    _remove_unused_eyebrows(hg_body)
    context.view_layer.objects.active = hg_rig
    
    sk = hg_body.data.shape_keys.key_blocks if hg_body.data.shape_keys else []

    _create_backup_human(context, hg_rig)   

    context.view_layer.objects.active = hg_rig
    sk_dict, driver_dict = extract_shapekeys_to_keep(context, hg_body)

    apply_shapekeys(hg_body)
    apply_shapekeys(next(c for c in hg_rig.children if 'hg_eyes' in c))

    context.view_layer.objects.active = hg_rig
    hg_eyes  = next(child for child in hg_rig.children if 'hg_eyes'  in child)
    hg_teeth = [child for child in hg_rig.children if 'hg_teeth' in child]

    child_list = [hg_eyes, hg_body, hg_teeth[0], hg_teeth[1]]
    for obj in child_list: 
        apply_armature(obj)

    apply_length_to_rig(hg_rig, context)

    for obj in context.selected_objects:
        obj.select_set(False)
    context.view_layer.objects.active = hg_rig
    remove_stretch_bones(hg_rig)

    for obj in  [hg_eyes, hg_body, hg_teeth[0], hg_teeth[1]]: 
        _add_applied_armature(hg_rig, obj)     

    reapply_shapekeys(context, sk_dict, hg_body, driver_dict)

    context.view_layer.objects.active = hg_rig
    _remove_teeth_constraint(hg_rig)
    _set_teeth_parent(hg_rig)

    refresh_pcoll(self, context, 'poses')

    HG.length = hg_rig.dimensions[2]

    #force recalculation of shapekeys
    sk = hg_body.data.shape_keys.key_blocks
    sk['cor_ShoulderSideRaise_Lt'].mute = True
    sk['cor_ShoulderSideRaise_Lt'].mute = False
    try:
        context.space_data.shading.type = old_shading
    except:
        pass
def _remove_unused_eyebrows(hg_body):
    """ Remove unused eyebrow particle systems
    
    Args:
        hg_body (Object)
    """
    eyebrows = [mod for mod in hg_body.modifiers 
                if mod.type == 'PARTICLE_SYSTEM' 
                and mod.particle_system.name.startswith('Eyebrows')
                ]
    
    remove_list = [mod.particle_system.name for mod in eyebrows if not mod.show_render]

    if len(eyebrows) == len(remove_list):
        ShowMessageBox(message = """All eyebrow systems are hidden (render), 
                       please manually remove particle systems you aren't using
                       """)
        return
    
    #TODO common func this
    for remove_name in remove_list:   
        ps_idx = [i for i, ps in enumerate(hg_body.particle_systems)
                  if ps.name == remove_name]
        hg_body.particle_systems.active_index = ps_idx[0]
        bpy.ops.object.particle_system_remove()  

def _create_backup_human(context, hg_rig):
    """To give the users the option to switch back to the creation phase, a copy
    of the human is made in a disabled collection. Also used by expression import

    Args:
        hg_rig (Object): 
    """
    hg_backup        = hg_rig.copy()
    hg_rig.HG.backup = hg_backup
    hg_backup.data   = hg_backup.data.copy()
    hg_backup.name   = hg_rig.name + '_Backup'
    

    context.collection.objects.link(hg_backup)
    hg_backup.hide_viewport = True
    hg_backup.hide_render = True
    add_to_collection(context,
                      hg_backup,
                      collection_name="HumGen_Backup [Don't Delete]"
                      )
    
    for obj in hg_rig.children:
        obj_copy = obj.copy()
        obj_copy.data = obj_copy.data.copy()
        context.collection.objects.link(obj_copy)
        
        add_to_collection(context,
                          obj_copy,
                          collection_name="HumGen_Backup [Don't Delete]")
        obj_copy.parent = hg_backup
        
        armatures = [mod for mod in obj_copy.modifiers 
                     if mod.type == 'ARMATURE']
        if armatures:
            armatures[0].object = hg_backup
        obj_copy.hide_viewport = True
        obj_copy.hide_render   = True

    hg_backup.matrix_parent_inverse = hg_rig.matrix_world.inverted()
    hg_backup.select_set(False)

def extract_shapekeys_to_keep(context, hg_body, apply_armature = True
                                  ) -> 'tuple[list, dict]':
    """All shapekeys need to be removed in order to apply the armature. To keep
    certain shapekeys, this function extracts them as separate objects to be 
    added to hg_body again after armature apply

    Args:
        hg_body (Object)        
        apply_armature (bool, optional): True if armature should be applied.
                                         Defaults to True.

    Returns:
        tuple[list, dict]: 
            list (bpy.types.object): Pointers to extracted shapekeys
            dict: see build_driver_dict for documentation 
    """
    pref = get_prefs()
    
    #TODO what does this do
    try:
        test = hg_body.data.shape_keys.animation_data.drivers
    except Exception as e:
        hg_log('Returning None for ', hg_body, e, level = 'WARNING')
        return None, None

    driver_dict = build_driver_dict(hg_body)
        
    sk = hg_body.data.shape_keys.key_blocks if hg_body.data.shape_keys else []
    obj_list = []
    for shapekey in sk:
        if (not shapekey.name.startswith(('cor_', 'eyeLook'))
            and not pref.keep_all_shapekeys):
            continue
        ob = hg_body.copy()
        ob.data = ob.data.copy()
        context.collection.objects.link(ob)
        ob.name = shapekey.name
        obj_list.append(ob)

        face_sk       = ob.data.shape_keys.key_blocks[shapekey.name]
        face_sk.mute  = False
        face_sk.value = 1
        apply_shapekeys(ob)
        if apply_armature:
            bpy.ops.object.modifier_apply(modifier="HG_Armature")  

    return obj_list, driver_dict

def build_driver_dict(obj, remove = True) -> dict:
    """Builds a dictionary of drivers on this object, saving their settings to 
    be re-used later

    Args:
        obj    (Object)        : object to index drivers from
        remove (bool, optional): Remove the drivers after saving their settings.
                                 Defaults to True.

    Returns:
        dict: 
            key (str): name of the shapekey this driver was controlling
            value (dict):
                key (str): name of setting that was copied
                value (AnyType): value of this setting
    """
    driver_dict = {}
    remove_list = []
    
    for driver in obj.data.shape_keys.animation_data.drivers:
        
        target_sk       = driver.data_path.replace('key_blocks["', '').replace('"].value', '')
        expression      = driver.driver.expression
        var             = driver.driver.variables[0]
        target          = var.targets[0]
        target_bone     = target.bone_target
        transform_type  = target.transform_type
        transform_space = target.transform_space
        
        driver_dict[target_sk] = {
            'expression': expression,
            'target_bone': target_bone,
            'transform_type': transform_type,
            'transform_space': transform_space
        }
        remove_list.append(driver)
    if remove:
        for driver in remove_list:
            obj.data.shape_keys.animation_data.drivers.remove(driver)
    
    return driver_dict

def remove_stretch_bones(hg_rig):
    """Removes all bones on this rig that have a stretch_to constraint

    Args:
        hg_rig (Object): HumGen human armature
    """
    bpy.ops.object.mode_set(mode='POSE')
    for bone in hg_rig.pose.bones:
        stretch_constraints = [
            c for c in bone.constraints 
            if c.type == 'STRETCH_TO' 
            ]
        
        for c in stretch_constraints:
            bone.constraints.remove(c) 
            
    bpy.ops.object.mode_set(mode='EDIT')
    remove_list = []
    for bone in hg_rig.data.edit_bones:
        if bone.name.startswith('stretch'):
            remove_list.append(bone)   
               
    for bone in remove_list:
        hg_rig.data.edit_bones.remove(bone)
        
    bpy.ops.object.mode_set(mode='OBJECT')    

def _add_applied_armature(hg_rig, obj):
    """Adds an armature modifier to the passed object, linking it to the passed
    rig

    Args:
        hg_rig (Object): HumGen armature
        obj (Object): object to add armature modifier to
    """
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

def reapply_shapekeys(context, sk_objects, hg_body, driver_dict):
    """Adds the extracted shapekeys back to the HumGen body

    Args:
        sk_objects  (dict)  : dictionary of extracted shapekeys (objects)
        hg_body     (Object): HumGen body object
        driver_dict (dict)  : dict containing settings of drivers that were on the
                              body before shapekey extraction
    """
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
        hg_delete(ob)

def add_driver(hg_body, target_sk, sett_dict):
    """Adds a new driver to the passed shapekey, using the passed dict as settings

    Args:
        hg_body (Object): object the shapekey is on
        target_sk (bpy.types.key_block): shapekey to add driver to
        sett_dict (dict): dict containing copied settings of old drivers
    """
    driver    = target_sk.driver_add('value').driver
    var       = driver.variables.new()
    var.type  = 'TRANSFORMS'
    target    = var.targets[0]
    target.id = hg_body.parent

    driver.expression      = sett_dict['expression']
    target.bone_target     = sett_dict['target_bone']
    target.transform_type  = sett_dict['transform_type']
    target.transform_space = sett_dict['transform_space']
    
    return driver

def _remove_teeth_constraint(hg_rig):
    """Remove child_of constraints from the teeth

    Args:
        hg_rig (Object): HumGen armature
    """
    p_bones = hg_rig.pose.bones
    p_bones["jaw"].constraints["Damped Track"].mute = False
    
    for bone in [p_bones['jaw'], p_bones['jaw_upper']]:
        child_constraints = [
            c for c in bone.constraints 
            if c.type == 'CHILD_OF']
        for c in child_constraints:
            bone.constraints.remove(c)
        
def _set_teeth_parent(hg_rig):
    """Sets the head bone as parent of the jaw bones

    Args:
        hg_rig (Object): HumGen armature
    """
    bpy.ops.object.mode_set(mode='EDIT')
    e_bones = hg_rig.data.edit_bones
    for b_name in ['jaw', 'jaw_upper']:
        e_bones[b_name].parent = e_bones['head']
    bpy.ops.object.mode_set(mode='OBJECT')




