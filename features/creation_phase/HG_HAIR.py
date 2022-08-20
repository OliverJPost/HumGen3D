import json
import os
import random
from pathlib import Path

import bpy  # type: ignore

from ...features.common.HG_COMMON_FUNC import (apply_shapekeys, find_human,
                                               get_prefs, hg_delete)
from .HG_LENGTH import apply_armature


class HG_REMOVE_HAIR(bpy.types.Operator):
    """Removes the corresponding hair system
    
    Operator type:
        Particle systems
    
    Prereq:
        Hair_system passed, and hair system is present on active object
        Active object is part of a HumGen human
        
    """
    bl_idname      = "hg3d.removehair"
    bl_label       = "Remove hair system"
    bl_description = "Removes this specific hair system from your human"
    bl_options     = {"UNDO"}

    hair_system: bpy.props.StringProperty()

    def execute(self,context):
        hg_rig  = find_human(context.object)
        hg_body = hg_rig.HG.body_obj

        context.view_layer.objects.active = hg_body

        ps_idx = next(
            i for i, ps in enumerate(hg_body.particle_systems)
            if ps.name == self.hair_system
        )
        hg_body.particle_systems.active_index = ps_idx
        bpy.ops.object.particle_system_remove()  
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

class HG_TOGGLE_HAIR_CHILDREN(bpy.types.Operator):
    """Turn hair children to 1 or back to render amount

    Operator type:
        Particle system
    
    Prereq:
        Active object is part of HumGen human
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

class HG_EYEBROW_SWITCH(bpy.types.Operator):
    """Cycle trough all eyebrow particle systems on this object
    
    Operator type:
        Particle system
    
    Prereq:
        forward passed
        Active object is part of HumGen human
        At least 2 particle systems on this object starting with 'Eyebrows'
        
    Args:
        forward (bool): True if go forward in list, False if go backward
    """
    bl_idname      = "hg3d.eyebrowswitch"
    bl_label       = "Switch eyebrows"
    bl_description = "Next or previous eyebrow style"

    forward: bpy.props.BoolProperty()

    def execute(self,context):
        hg_rig  = find_human(context.object)
        hg_body = hg_rig.HG.body_obj

        _switch_eyebrows(self, hg_body, forward = self.forward)

        return {'FINISHED'}

def _switch_eyebrows(self, hg_body, forward = True, report = False):
    eyebrows = [mod for mod in hg_body.modifiers 
                if mod.type == 'PARTICLE_SYSTEM' 
                and mod.particle_system.name.startswith('Eyebrows')
                ]
    
    if not eyebrows:
        if report:
            self.report({'WARNING'}, 'No eyebrow particle systems found')
        return
    if len(eyebrows) == 1:
        if report:
            self.report({'WARNING'}, 'Only one eyebrow system found')
        return          
    
    idx, current_ps = next(
        ((i, mod) for i, mod in enumerate(eyebrows)
            if mod.show_viewport or mod.show_render),
            0
        )

    next_idx = idx + 1 if forward else idx - 1
    if next_idx >= len(eyebrows) or next_idx < 0:
        next_idx = 0

    next_ps = eyebrows[next_idx]
    next_ps.show_viewport = next_ps.show_render = True
    
    for ps in eyebrows:
        if ps != next_ps:
            ps.show_viewport = ps.show_render = False    


def load_hair(self,context, type):
    """Loads hair system the user selected by reading the json that belongs to
    the selected hairstyle

    Args:
        type (str): type of hair to load ('head' or 'facial_hair')
    """
    pref = get_prefs()
    sett = context.scene.HG3D

    hair_data = _get_hair_json(type, pref, sett)

    blendfile = hair_data['blend_file']
    json_systems = hair_data['hair_systems']

    hair_obj = _import_hair_obj(context, type, pref, blendfile)

    hg_rig  = find_human(context.active_object)
    hg_body = hg_rig.HG.body_obj
    hg_rig.hide_set(False)
    hg_rig.hide_viewport = False

    remove_fh = True if type == 'face' else False
    _remove_old_hair(hg_body, remove_fh)

    for mod in [mod for mod in hg_body.modifiers if mod.type == 'MASK']:
        mod.show_viewport = False

    #IMPORTANT: Hair systems do not transfer correctly if they are hidden in the viewport
    for mod in hair_obj.modifiers:
        if mod.type == 'PARTICLE_SYSTEM':
            mod.show_viewport = True
   
    context.view_layer.objects.active = hair_obj
    _morph_hair_obj_to_body_obj(context, hg_body, hair_obj)

    context.view_layer.objects.active = hair_obj 
    bpy.ops.particle.disconnect_hair(all=True) 

    for obj in context.selected_objects:
        obj.select_set(False)
    context.view_layer.objects.active = hair_obj
    hg_body.select_set(True)
    
    #iterate over hair systems that need to be transferred
    for ps_name in json_systems:
        _transfer_hair_system(json_systems, hair_obj, ps_name)

    for vg in hair_obj.vertex_groups:
        if vg.name.lower().startswith(('hair', 'fh')):
            _transfer_vertexgroup(hg_body, hair_obj, vg.name)

    new_hair_systems = _get_hair_systems_dict(hg_body, hair_obj)

    context.view_layer.objects.active = hg_body
    for mod in new_hair_systems:
        _reconnect_hair(hg_body, mod)
        add_quality_props_to_hair_system(mod)

    _set_correct_particle_vertexgroups(new_hair_systems, hair_obj, hg_body)
    _set_correct_hair_material(new_hair_systems, hg_body, type)

    for mod in [mod for mod in hg_body.modifiers if mod.type == 'PARTICLE_SYSTEM']:
        mod.show_expanded = False

    _move_modifiers_above_masks(hg_body, new_hair_systems)
    for mod in [mod for mod in hg_body.modifiers]:
        # Turn on masks again
        if mod.type == 'MASK':
            mod.show_viewport = True
        
        #Show all hair systems
        elif mod.type == 'PARTICLE_SYSTEM':
            ps_sett = mod.particle_system.settings
            ps_sett.child_nbr = ps_sett.rendered_child_count

    hg_delete(hair_obj)

def add_quality_props_to_hair_system(mod):
    ps = mod.particle_system.settings
    ps['steps'] = ps.render_step
    ps['children'] = ps.rendered_child_count
    ps['root'] = ps.root_radius
    ps['tip'] = ps.tip_radius

def _get_hair_json(type, pref, sett) -> dict:
    """Loads the data from the json that belongs to the selected hair system

    Args:
        type (str): type of hair to import ('facial_hair' or 'head')
        pref (AddonPreferences): HumGen preferences
        sett (PropertyGroup): addon props

    Returns:
        dict: 
            key 'blend_file':
                value (str): filename of .blend that contains the hair systems
            key 'hair_systems':
                value (dict):
                    key (str): name of particle system
                    value (dict):
                        key (str): name of setting prop
                        value (AnyType): value to set prop to 
    """
    if type == 'head':
        short_path = sett.pcoll_hair
    else:
        short_path = sett.pcoll_face_hair

    full_path = str(pref.filepath) + short_path
    with open(full_path) as f:
        data = json.load(f)
        
    return data

def _import_hair_obj(context, type, pref, blendfile) -> bpy.types.Object:
    """Imports the object that contains the hair systems named in the json file

    Args:
        context ([type]): [description]
        type (str): type of hair system ('facial hair' or 'head')
        pref (AddonPreferences): HumGen preferences
        blendfile (str): name of blendfile to open

    Returns:
        Object: body object that contains the hair systems
    """
    #import hair object, linking it to the scene and collection
    blendpath = (str(pref.filepath)
                 + str(Path('/hair/{}/{}'.format('head' if type == 'head' 
                                                 else 'face_hair',
                                                 blendfile
                                                 )
                            )
                       )
                 )
    
    with bpy.data.libraries.load(blendpath, link = False) as (data_from ,data_to):
        data_to.objects = ['HG_Body'] 
    
    hair_obj = data_to.objects[0]
    scene    = context.scene
    scene.collection.objects.link(hair_obj)
    
    return hair_obj

def _remove_old_hair(hg_body, remove_face_hair):
    """Removes old hair systems from body object
    
    Args:
        hg_body (Object)
        remove_face_hair (bool): True if facial hair needs to be removed, False
            if head hair needs to be removed
    """
    remove_list = []
    for ps in hg_body.particle_systems:
        if ps.name.lower().startswith('fh') and remove_face_hair:
            remove_list.append(ps.name)
        elif (not ps.name.lower().startswith(('fh', 'eye')) 
                  and not remove_face_hair):
            remove_list.append(ps.name)
            
    for ps_name in remove_list:    
        ps_idx = [i for i, ps in enumerate(hg_body.particle_systems) 
                  if ps.name == ps_name]
        hg_body.particle_systems.active_index = ps_idx[0]
        bpy.ops.object.particle_system_remove()

def _morph_hair_obj_to_body_obj(context, hg_body, hair_obj):
    """Gives the imported hair object the exact same shape as hg, to make sure
    the hair systems get transferred correctly

    Args:
        hg_body (Object): body object
        hair_obj (Oject): imported hair object
    """
    body_copy      = hg_body.copy()
    body_copy.data = body_copy.data.copy()
    context.scene.collection.objects.link(body_copy)

    apply_shapekeys(body_copy)
    apply_armature(body_copy)

    for obj in context.selected_objects:
        obj.select_set(False)

    hair_obj.select_set(True)
    body_copy.select_set(True)
    context.view_layer.objects.active = hair_obj
    bpy.ops.object.join_shapes()

    sk = hair_obj.data.shape_keys.key_blocks
    sk[body_copy.name].value = 1

    hg_delete(body_copy)

def _transfer_hair_system(json_systems, hair_obj, ps):
    ps_mods = [mod for mod in hair_obj.modifiers 
                    if mod.type == 'PARTICLE_SYSTEM']
    for mod in ps_mods:
        if mod.particle_system.name == ps:
            _set_particle_settings(json_systems, mod, ps)
            break
    override = bpy.context.copy()
    override['particle_system'] = hair_obj.particle_systems[ps]
    bpy.ops.particle.copy_particle_systems(override,
                                               remove_target_particles=False,
                                               use_active=True)

def _set_particle_settings(json_systems, mod, ps_name):
    """Sets the settings of this particle settings according to the json dict

    Args:
        json_systems (dict): 
            key (str): name of hair system
            value (dict):
                key (str): name of setting
                value (Anytype): value to set that setting to
        mod (bpy.types.modifier): modifier of this particle system
        ps_name (str): name of the particle system
    """
    psys = mod.particle_system.settings
    json_sett = json_systems[ps_name]
    if 'length' in json_sett:
        psys.child_length = json_sett['length']
    if 'children_amount' in json_sett: 
        psys.child_nbr            = json_sett['children_amount']
        psys.rendered_child_count = json_sett['children_amount']
    if "path_steps" in json_sett: 
        psys.display_step = json_sett['path_steps']
        psys.render_step  = json_sett['path_steps']

def _transfer_vertexgroup(to_obj, from_obj, vg_name):
    """Copies vertex groups from one object to the other

    Args:
        to_obj   (Object): object to transfer vertex groups to
        from_obj (Object): object to transfer vertex group from
        vg_name  (str)   : name of vertex group to transfer
    """

    vert_dict = {}
    for vert_idx, _ in enumerate(from_obj.data.vertices):
        try:
            vert_dict[vert_idx] = from_obj.vertex_groups[vg_name].weight(vert_idx)
        except:
            pass

    target_vg = to_obj.vertex_groups.new(name=vg_name)

    for v in vert_dict:
        target_vg.add([v,], vert_dict[v], 'ADD')   

def _get_hair_systems_dict(hg_body, hair_obj) -> dict:
    """Gets hair particle systems on passed object, including modifiers

    Args:
        hg_body (Object)
        hair_obj (Object): imported hair obj

    Returns:
        dict: 
            key   (bpy.types.modifier)       : Modifier of a particle system
            value (bpy.types.particle_system): Particle hair system
    """

    system_names = []

    for mod in [mod for mod in hair_obj.modifiers if mod.type == 'PARTICLE_SYSTEM']:
        system_names.append(mod.particle_system.name)

    new_mod_dict = {}
    for mod in [mod for mod in hg_body.modifiers if mod.type == 'PARTICLE_SYSTEM']:
        if mod.particle_system.name in system_names:
            new_mod_dict[mod] = mod.particle_system.name

    return new_mod_dict

def _reconnect_hair(hg_body, mod):
    """Reconnects the transferred hair systems to the skull

    Args:
        hg_body (Object): hg body object
        mod (bpy.types.modifier): Modifier of type particle system to reconnect
    """
    for i, ps in enumerate(hg_body.particle_systems):
        if ps.name == mod.particle_system.name:
            ps_idx = i
    hg_body.particle_systems.active_index = ps_idx
    bpy.ops.particle.connect_hair(all=False)

def _set_correct_particle_vertexgroups(new_systems, from_obj, to_obj):
    """Transferring particle systems results in the wrong vertex group being set,
    this corrects that

    Args:
        new_systems (dict): modifiers and particle_systems to correct vgs for
        from_obj (Object): Object to check correct particle vertex group on
        to_obj (Object): Object to rectify particle vertex groups on
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
  
        old_ps_sett = from_obj.particle_systems[ps_name]
        new_ps_sett = to_obj.particle_systems[ps_name]

        for vg_attr in vg_attributes:
            setattr(new_ps_sett, vg_attr, getattr(old_ps_sett, vg_attr))
        
def _set_correct_hair_material(new_systems, hg_body, hair_type):
    """Sets face hair material for face hair systems and head head material for 
    head hair

    Args:
        new_systems (dict): Dict of modifiers and particle_systems of hair systems
        hg_body (Object): 
        hair_type (str): 'head' for normal, 'facial_hair' for facial hair
    """
    search_mat = '.HG_Hair_Face' if hair_type == 'face' else '.HG_Hair_Head'
    mat_name   = [mat.name for mat in hg_body.data.materials 
                  if mat.name.startswith(search_mat)]
    
    for ps in new_systems:
        ps.particle_system.settings.material_slot = mat_name[0]

def _move_modifiers_above_masks(hg_body, new_systems):
    lowest_mask_index = next(
        (i for i, mod in enumerate(hg_body.modifiers)
         if mod.type == 'MASK'),
        None
        )
    if not lowest_mask_index:
        return
        
    for mod in new_systems:
        if (2, 90, 0) > bpy.app.version: #use old method when older than 2.90
            while hg_body.modifiers.find(mod.name) > lowest_mask_index:
                bpy.ops.object.modifier_move_up({'object': hg_body},
                                                modifier=mod.name)
        
        elif hg_body.modifiers.find(mod.name) > lowest_mask_index:
            bpy.ops.object.modifier_move_to_index(modifier=mod.name,
                                                  index=lowest_mask_index)

def convert_to_new_hair_shader(hg_body):
    hair_mats = hg_body.data.materials[1:3]
    
    group_nodes = []
    for mat in hair_mats:
        group_nodes.append(next((n for n in mat.node_tree.nodes if n.name == 'HG_Hair'), None))
    
    #check if there is at least one 
    if not any(group_nodes):
        return    
        
    addon_folder = Path(Path(os.path.dirname(__file__)).parent).parent
    blendfile = os.path.join(addon_folder, 'data', 'hair_shader_v3.blend')

    if 'HG_Hair_V3' in [ng.name for ng in bpy.data.node_groups]:
        new_hair_group = bpy.data.node_groups['HG_Hair_V3']
    else:
        with bpy.data.libraries.load(blendfile, link = False) as (data_from ,data_to):
            data_to.node_groups = data_from.node_groups
            
        new_hair_group = data_to.node_groups[0]
    
    for node in group_nodes:
        node.node_tree = new_hair_group
        node.name = 'HG_Hair_V3'
        
def update_hair_shader_type(self, context):
    shader_type = self.hair_shader_type
    value = 0 if shader_type == 'fast' else 1
    
    hg_rig = find_human(context.object)
    hg_body = hg_rig.HG.body_obj
    
    for mat in hg_body.data.materials[1:3]:
        hair_group = mat.node_tree.nodes.get('HG_Hair_V3')
        if not hair_group:
            continue
        
        hair_group.inputs['Fast/Accurate'].default_value = value

def set_hair_quality(context, hair_type, hair_quality):
    hg_body = find_human(context.object).HG.body_obj
    
    for mod in [m for m in hg_body.modifiers if m.type == 'PARTICLE_SYSTEM']:
        ps = mod.particle_system.settings
        max_steps = ps['steps']
        max_children = ps['children']
        max_root = ps['root']
        max_tip = ps['tip']
        
        ps.render_step = ps.display_step = _get_steps_amount(hair_quality, max_steps)
        ps.rendered_child_count = ps.child_nbr = _get_child_amount(hair_quality, max_children)
        ps.root_radius, ps.tip_radius = _get_root_and_tip(hair_quality, max_root, max_tip)


def _get_steps_amount(hair_quality, max_steps):
    min_steps = 1 if max_steps <= 2 else 2 if max_steps <= 4 else 3
    deduction_dict = {
            'high': 0,
            'medium': 1,
            'low': 2,
            'ultralow': 3
        }
    new_steps = max_steps - deduction_dict[hair_quality]
    if new_steps < min_steps:
        new_steps = min_steps
        
    return new_steps

def _get_child_amount(hair_quality, max_children):
    division_dict = {
        'high': 1,
        'medium': 2,
        'low': 4,
        'ultralow': 10
    }        
    new_children = max_children / division_dict[hair_quality]
    
    return int(new_children)

def _get_root_and_tip(hair_quality, max_root, max_tip):
    multiplication_dict = {
        'high': 1,
        'medium': 2,
        'low': 6,
        'ultralow': 12
    }
    
    new_root = max_root * multiplication_dict[hair_quality]
    new_tip = max_tip * multiplication_dict[hair_quality]
    
    return new_root, new_tip

def randomize_eyebrows(hg_body):
    for i in random.randrange(0, 8):
        _switch_eyebrows(None, hg_body, forward = True)
        
def random_hair_color(hg_body):
    #TODO make system more elaborate
    hair_color_dict= {
        'blonde' : (4.0, 0.8, 0.0),
        'black' : (0.0, 1.0, 0.0),
        'dark_brown' : (0.5, 1.0, 0.0),
        'brown' : (1.0, 1.0, 0.0),
        'red' : (3.0, 1.0, 0.0)
    }
    
    hair_color = hair_color_dict[random.choice([name for name in hair_color_dict])]
    
    for mat in hg_body.data.materials[1:]:
        nodes = mat.node_tree.nodes
        hair_node = next(n for n in nodes if n.name.startswith('HG_Hair'))
        hair_node.inputs['Hair Lightness'].default_value = hair_color[0]
        hair_node.inputs['Hair Redness'].default_value = hair_color[1]
        hair_node.inputs['Pepper & Salt'].default_value = hair_color[2]
    