import bpy #type: ignore
import json
import os
import time
from ... features.common.HG_COMMON_FUNC import find_human, apply_shapekeys, get_prefs
from . HG_LENGTH import apply_armature
from pathlib import Path

class HG_REMOVE_HAIR(bpy.types.Operator):
    """
    Removes the corresponding hair system
    """
    bl_idname      = "hg3d.removehair"
    bl_label       = "Remove hair system"
    bl_description = "Removes this specific hair system from your human"
    bl_options     = {"REGISTER", "UNDO"}

    hair_system: bpy.props.StringProperty()

    def execute(self,context):
        hg_rig  = find_human(context.object)
        hg_body = hg_rig.HG.body_obj

        ps_idx = [i for i, ps in enumerate(hg_body.particle_systems) if ps.name == self.hair_system]
        hg_body.particle_systems.active_index = ps_idx[0]
        bpy.ops.object.particle_system_remove()  
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

class HG_EYEBROW_SWITCH(bpy.types.Operator):
    """
    Removes the corresponding hair system
    """
    bl_idname      = "hg3d.eyebrowswitch"
    bl_label       = "Switch eyebrows"
    bl_description = "Next or previous eyebrow style"

    forward: bpy.props.BoolProperty()

    def execute(self,context):
        hg_rig  = find_human(context.object)
        hg_body = hg_rig.HG.body_obj

        eyebrows = [mod for mod in hg_body.modifiers if mod.type == 'PARTICLE_SYSTEM' and mod.particle_system.name.startswith('Eyebrows')]
        if not eyebrows:
            self.report({'WARNING'}, 'No eyebrow particle systems found')
            return {'FINISHED'}
        if len(eyebrows) == 1:
            self.report({'WARNING'}, 'Only one eyebrow system found')
            return {'FINISHED'}            
        
        idx, current_ps = next(((i, mod) for i, mod in enumerate(eyebrows) if mod.show_viewport or mod.show_render), 0)
        print(idx, current_ps, current_ps.particle_system.name)

        next_idx = idx + 1 if self.forward else idx - 1
        print('next_idx1', next_idx)
        if next_idx >= len(eyebrows) or next_idx < 0:
            next_idx = 0

        print('next_idx2', next_idx)

        next_ps = eyebrows[next_idx]
        next_ps.show_viewport = next_ps.show_render = True
        
        for ps in eyebrows:
            if ps != next_ps:
                ps.show_viewport = ps.show_render = False
        

        return {'FINISHED'}

def load_hair(self,context, type):
    """
    loads the active hairstyle in the hair preview collection
    """
    pref = get_prefs()

    sett = context.scene.HG3D

    if type == 'head':
        short_path = sett.pcoll_hair
    else:
        short_path = sett.pcoll_face_hair

    full_path = str(pref.filepath) + short_path

    with open(full_path) as f:
        data = json.load(f)

    blendfile = data['blend_file']
    json_systems = data['hair_systems']

    #import hair object, linking it to the scene and collection
    blendpath = str(pref.filepath) + str(Path('/hair/{}/{}'.format('head' if type == 'head' else 'face_hair', blendfile)))
    with bpy.data.libraries.load(blendpath, link = False) as (data_from ,data_to):
        data_to.objects = ['HG_Body'] 
    hair_obj = data_to.objects[0]
    scene    = context.scene
    scene.collection.objects.link(hair_obj)

    hg_rig  = find_human(context.active_object)
    hg_body = hg_rig.HG.body_obj
    hg_rig.hide_set(False)
    hg_rig.hide_viewport = False

    remove_fh = True if type == 'face' else False
    remove_old_hair(hg_body, remove_fh)

    for mod in [mod for mod in hg_body.modifiers if mod.type == 'MASK']:
        mod.show_viewport = False

    sk_body = hg_body.data.shape_keys.key_blocks

    #IMPORTANT: Hair systems do not transfer correctly if they are hidden in the viewport
    for mod in hair_obj.modifiers:
        if mod.type == 'PARTICLE_SYSTEM':
            mod.show_viewport = True
   

    context.view_layer.objects.active = hair_obj
    morph_to_shape(context, hg_body, hair_obj)

    context.view_layer.objects.active = hair_obj 
    bpy.ops.particle.disconnect_hair(all=True) 

    for obj in context.selected_objects:
        obj.select_set(False)

    context.view_layer.objects.active = hair_obj
    
    hg_body.select_set(True)
    
    #iterate over hair systems that need to be transferred
    for ps in json_systems:
        for mod in [mod for mod in hair_obj.modifiers if mod.type == 'PARTICLE_SYSTEM']:
            if mod.particle_system.name == ps:
                psys = mod.particle_system.settings
                json_sett = json_systems[ps]
                if 'length' in json_sett:
                    psys.child_length = json_sett['length']
                if 'children_amount' in json_sett: 
                    psys.child_nbr            = json_sett['children_amount']
                    psys.rendered_child_count = json_sett['children_amount']
                if "path_steps" in json_sett: 
                    psys.display_step = json_sett['path_steps']
                    psys.render_step  = json_sett['path_steps']

        override = bpy.context.copy()
        override['particle_system'] = hair_obj.particle_systems[ps]
        bpy.ops.particle.copy_particle_systems(override, remove_target_particles=False, use_active=True)  

    for vg in hair_obj.vertex_groups:
        if vg.name.lower().startswith(('hair', 'fh')):
            copy_vg(hg_body, hair_obj, vg.name)

    new_systems = find_systems(hg_body, hair_obj)

    context.view_layer.objects.active = hg_body
    for mod in new_systems:
        for i, ps in enumerate(hg_body.particle_systems):
            if ps.name == mod.particle_system.name:
                ps_idx = i
        hg_body.particle_systems.active_index = ps_idx
        bpy.ops.particle.connect_hair(all=False)

    set_correct_vg(new_systems, hair_obj, hg_body)
    set_correct_material(new_systems, hg_body, type)

    for mod in [mod for mod in hg_body.modifiers if mod.type == 'PARTICLE_SYSTEM']:
        mod.show_expanded = False

    move_modifiers_above_masks(hg_body, new_systems)
    for mod in [mod for mod in hg_body.modifiers if mod.type == 'MASK']:
        mod.show_viewport = True

    bpy.data.objects.remove(hair_obj)

def move_modifiers_above_masks(hg_body, new_systems):
    lowest_mask_index = next((i for i, mod in enumerate(hg_body.modifiers) if mod.type == 'MASK'), None)
    if not lowest_mask_index:
        return
        
    for mod in new_systems:
        if (2, 90, 0) > bpy.app.version: #use old method for versions older than 2.90
            while hg_body.modifiers.find(mod.name) > lowest_mask_index:
                bpy.ops.object.modifier_move_up({'object': hg_body}, modifier=mod.name)
        elif hg_body.modifiers.find(mod.name) > lowest_mask_index:
            bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=lowest_mask_index)


def morph_to_shape(context, hg_body, hair_obj):
    body_copy      = hg_body.copy()
    body_copy.data = body_copy.data.copy()
    context.scene.collection.objects.link(body_copy)

    apply_shapekeys(body_copy)
    apply_armature(None, body_copy)

    for obj in context.selected_objects:
        obj.select_set(False)

    hair_obj.select_set(True)
    body_copy.select_set(True)
    context.view_layer.objects.active = hair_obj
    bpy.ops.object.join_shapes()

    sk = hair_obj.data.shape_keys.key_blocks
    sk[body_copy.name].value = 1

    bpy.data.objects.remove(body_copy)

def set_sk_values(sk_body, sk_hair_obj):
    for sk in sk_body:
        if not sk.mute:
            try:
                sk_hair_obj[sk.name].mute = False
                sk_hair_obj[sk.name].value = sk.value
            except:
                pass

def copy_vg(target_obj, source_obj, vg_name):
    """
    copies vertex group from one to the other object
    """    
    vert_dict = {}
    for vert_idx, _ in enumerate(source_obj.data.vertices):
        try:
            vert_dict[vert_idx] = source_obj.vertex_groups[vg_name].weight(vert_idx)
        except RuntimeError:
            pass

    target_vg = target_obj.vertex_groups.new(name=vg_name)

    for v in vert_dict:
        target_vg.add([v,], vert_dict[v], 'ADD')   

def remove_old_hair(hg_body, remove_face_hair):
    """
    removes old hair systems from body object
    """
    remove_list = []
    for ps in hg_body.particle_systems:
        if ps.name.lower().startswith('fh') and remove_face_hair:
            remove_list.append(ps.name)
        elif not ps.name.lower().startswith(('fh', 'eye')) and not remove_face_hair:
            remove_list.append(ps.name)

    for ps_name in remove_list:    
        ps_idx = [i for i, ps in enumerate(hg_body.particle_systems) if ps.name == ps_name]
        hg_body.particle_systems.active_index = ps_idx[0]
        bpy.ops.object.particle_system_remove()

            
def find_systems(hg_body, hair_obj):
    """
    returns particle systems in a dict of the modifier and the name
    """

    system_names = []

    for mod in [mod for mod in hair_obj.modifiers if mod.type == 'PARTICLE_SYSTEM']:
        system_names.append(mod.particle_system.name)

    new_mod_dict = {}
    for mod in [mod for mod in hg_body.modifiers if mod.type == 'PARTICLE_SYSTEM']:
        if mod.particle_system.name in system_names:
            new_mod_dict[mod] = mod.particle_system.name

    return new_mod_dict

def set_correct_vg(new_systems, source_obj, new_obj):
    """
    transferring particle systems results in the wrong vertex group being set, this corrects that
    """
    for ps_name in [new_systems[mod] for mod in new_systems]:

        vg_attributes = [
            'vertex_group_clump',
            'vertex_group_density',
            'vertex_group_field',
            'vertex_group_kink',
            'vertex_group_length',
            'vertex_group_rotation',
            'vertex_group_roughness_1',
            'vertex_group_roughness_2',
            'vertex_group_roughness_end',
            'vertex_group_size',
            'vertex_group_tangent',
            'vertex_group_twist',
            'vertex_group_velocity'
            ]
  
        old_ps_sett = source_obj.particle_systems[ps_name]
        new_ps_sett = new_obj.particle_systems[ps_name]

        for vg_attr in vg_attributes:
            setattr(new_ps_sett, vg_attr, getattr(old_ps_sett, vg_attr))
        
        # new_ps_sett.vertex_group_clump =
        # new_ps_sett.vertex_group_density =
        # new_ps_sett.vertex_group_field =
        # new_ps_sett.vertex_group_kink =
        # new_ps_sett.vertex_group_length =
        # new_ps_sett.vertex_group_rotation =
        # new_ps_sett.vertex_group_roughness_1 =
        # new_ps_sett.vertex_group_roughness_2 =
        # new_ps_sett.vertex_group_roughness_end =
        # new_ps_sett.vertex_group_size =
        # new_ps_sett.vertex_group_tangent =
        # new_ps_sett.vertex_group_twist =
        # new_ps_sett.vertex_group_velocity =
  
def set_correct_material(new_systems, hg_body, hair_type):
    """
    sets face hair material for face hair systems and head head material for head hair
    """
    search_mat = '.HG_Hair_Face' if hair_type == 'face' else '.HG_Hair_Head'
    mat_name   = [mat.name for mat in hg_body.data.materials if mat.name.startswith(search_mat)]
    for ps in new_systems:
        ps.particle_system.settings.material_slot = mat_name[0]

class HG_TOGGLE_HAIR_CHILDREN(bpy.types.Operator):
    """
    toggles visibility of hair children in viewport
    """
    bl_idname      = "hg3d.togglechildren"
    bl_label       = "Toggle hair children"
    bl_description = "Toggle between hidden and visible hair children"
    bl_options     = {"REGISTER", "UNDO"}

    def execute(self,context):
        hg_rig = find_human(context.active_object)
        hg_body = hg_rig.HG.body_obj

        hair_systems= []
        make_zero = False
        for mod in hg_body.modifiers:
            if mod.type == 'PARTICLE_SYSTEM':
                ps = mod.particle_system
                hair_systems.append(ps)
                if ps.settings.child_nbr > 1:
                    make_zero = True
        for ps in hair_systems:
            if make_zero:
                ps.settings.child_nbr =  1
            else:
                render_children = ps.settings.rendered_child_count
                ps.settings.child_nbr = render_children

        return {'FINISHED'}