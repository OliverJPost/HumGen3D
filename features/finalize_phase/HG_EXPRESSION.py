"""
Operators and functions for adding and managing expressions
"""

from ... features.creation_phase.HG_NEXTPHASE import add_driver, build_driver_dict
import bpy #type: ignore
import os
from pathlib import Path
from ... features.common.HG_COMMON_FUNC import find_human, apply_shapekeys
from ... features.creation_phase.HG_LENGTH import apply_armature, apply_length_to_rig, add_applied_armature

class HG_REMOVE_SHAPEKEY(bpy.types.Operator):
    """
    Removes the corresponding shapekey
    """
    bl_idname      = "hg3d.removesk"
    bl_label       = "Remove this shapekey"
    bl_description = "Remove this shapekey"
    bl_options     = {"UNDO"}

    shapekey: bpy.props.StringProperty()

    def execute(self,context):        
        hg_rig = find_human(context.active_object)
        hg_body = hg_rig.HG.body_obj

        sk_delete = hg_body.data.shape_keys.key_blocks[self.shapekey]
        hg_body.shape_key_remove(sk_delete)

        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


def load_expression(self, context):
    """
    loads the active expression in the preview collection
    """
    
    pref = context.preferences.addons[__package__].preferences

    item = context.scene.HG3D.pcoll_expressions
    sk_name, _ = os.path.splitext(os.path.basename(item))
    
    sett_dict = {}

    filepath  = str(pref.filepath) + str(item)
    sett_file = open(filepath)
    for line in sett_file:
        key, value = line.split()
        sett_dict[key] = value

    hg_rig = find_human(context.active_object)
    hg_body = hg_rig.HG.body_obj
    if 'expr_{}'.format(sk_name) in [sk.name for sk in hg_body.data.shape_keys.key_blocks]:
        new_key = hg_body.data.shape_keys.key_blocks['expr_{}'.format(sk_name)]
        exists  = True
    else:
        backup_rig  = hg_rig.HG.backup
        backup_body = [child for child in backup_rig.children if 'hg_body' in child]
        transfer_as_one_shapekey(context, backup_body[0], hg_body, sett_dict, backup_rig)

        exists = False
        new_key = None

    for sk in hg_body.data.shape_keys.key_blocks:
        if not sk.name.startswith(('expr', 'cor')) and sk.name != 'Basis':
            new_key = sk
        else:
            sk.value = 0

    if not exists:
        new_key.name = 'expr_{}'.format(sk_name)
    new_key.mute = False
    new_key.value = 1


def transfer_as_one_shapekey(context, source, target, sk_dict, backup_rig):
    """
    transfers a shapekey 
    """
    backup_rig_copy      = backup_rig.copy()
    backup_rig_copy.data = backup_rig_copy.data.copy()
    context.scene.collection.objects.link(backup_rig_copy)
    source_copy      = source.copy()
    source_copy.data = source_copy.data.copy()
    context.scene.collection.objects.link(source_copy)

    sks = source_copy.data.shape_keys.key_blocks

    for sk in sks:
        if sk.name.startswith('expr'):
            sk.mute = True
    for key in sk_dict:
        sks[key].mute = False
        sks[key].value = float(sk_dict[key])

    apply_shapekeys(source_copy)

    context.view_layer.objects.active = backup_rig_copy
    backup_rig_copy.hide_viewport     = False
    source_copy.hide_viewport         = False
    backup_rig_copy.HG.body_obj       = source_copy
    apply_armature(backup_rig_copy, source_copy)
    apply_length_to_rig(backup_rig_copy)


    for obj in context.selected_objects:
        obj.select_set(False)

    context.view_layer.objects.active = target
    source_copy.hide_viewport = False
    source_copy.select_set(True)

    bpy.ops.object.join_shapes()

    bpy.data.objects.remove(source_copy)
    bpy.data.objects.remove(backup_rig_copy)

class FRIG_DATA:
    def get_frig_bones(self):
        return [
            "brow_inner_up",
            "pucker",
            "mouth_shrug_roll_upper",
            "mouth_lt_rt_funnel",
            "mouth_roll_lower",
            "jaw_dwn_mouth_clsd",
            "jaw_open_lt_rt_frwd",
            "brow_dwn_L",
            "eye_blink_open_L",
            "eye_squint_L",
            "brow_outer_up_L",
            "nose_sneer_L",
            "cheek_squint_L",
            "mouth_dimple_L",
            "mouth_smile_frown_L",
            "mouth_upper_up_L",
            "mouth_lower_down_L",
            "mouth_stretch_L",
            "brow_dwn_R",
            "brow_outer_up_R",
            "eye_blink_open_R",
            "eye_squint_R",
            "cheek_squint_R",
            "mouth_dimple_R",
            "mouth_lower_down_R",
            "mouth_upper_up_R",
            "mouth_smile_frown_R",
            "mouth_stretch_R",
            "nose_sneer_R"
        ]

class HG_ADD_FRIG(bpy.types.Operator, FRIG_DATA):
    """
    Removes the corresponding shapekey
    """
    bl_idname      = "hg3d.addfrig"
    bl_label       = "Add facial rig"
    bl_description = "Adds facial rig"
    bl_options     = {"UNDO"}

    def execute(self,context):        
        hg_rig = find_human(context.active_object)
        hg_body = hg_rig.HG.body_obj
  
        frig_bones = self.get_frig_bones()
        for b_name in frig_bones:
            b = hg_rig.pose.bones[b_name]
            b.bone.hide= False
        
        self.load_FACS_sks(context, hg_body)

        hg_body['facial_rig'] = 1
        return {'FINISHED'}

    def load_FACS_sks(self, context, hg_body):
        pref = context.preferences.addons[__package__].preferences
        context.view_layer.objects.active = hg_body

        blendfile = pref.filepath + str(Path('/models/FACS/HG_FACS.blend'))
        with bpy.data.libraries.load(blendfile, link = False) as (data_from ,data_to):
            data_to.objects = data_from.objects
        
        print('objects', data_to.objects)
        hg_facs = next(obj for obj in data_to.objects if obj.type == 'MESH')
        context.scene.collection.objects.link(hg_facs)

        #normalize objects
        driver_dict = build_driver_dict(hg_facs, remove = False)

        for obj in context.selected_objects:
            obj.select_set(False)
        hg_body.select_set(True)
        hg_facs.select_set(True)
        for idx, sk in enumerate(hg_facs.data.shape_keys.key_blocks):
            if sk.name in ['Basis', 'Male']:
                continue
            hg_facs.active_shape_key_index = idx
            bpy.ops.object.shape_key_transfer()

        body_sks = hg_body.data.shape_keys.key_blocks
        for driver_shapekey in driver_dict:
            if driver_shapekey in body_sks:
                sk = hg_body.data.shape_keys.key_blocks[driver_shapekey]
                add_driver(hg_body, sk, driver_dict[driver_shapekey])

        hg_facs.select_set(False)
        bpy.data.objects.remove(hg_facs)
        hg_body.show_only_shape_key = False
        


class HG_REMOVE_FRIG(bpy.types.Operator, FRIG_DATA):
    """
    Removes the corresponding shapekey
    """
    bl_idname      = "hg3d.removefrig"
    bl_label       = "Remove facial rig"
    bl_description = "Remove facial rig"
    bl_options     = {"UNDO"}

    def execute(self,context):        
        hg_rig = find_human(context.active_object)
        hg_body = hg_rig.HG.body_obj

        frig_bones = self.get_frig_bones()
        for b_name in frig_bones:
            b = hg_rig.pose.bones[b_name]
            b.bone.hide= True
        
        #TODO make it only delete Frig sks instead of all outside naming scheme
        for sk in [sk for sk in hg_body.data.shape_keys.key_blocks if not sk.name.startswith(('Basis', 'cor_', 'expr_'))]:
            hg_body.shape_key_remove(sk)

        del hg_body["facial_rig"]

        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)