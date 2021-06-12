"""
Operators and functions used for adding the base human and for reverting to creation phase
"""

import json
import bpy #type: ignore
import os
import random
from pathlib import Path

from .   HG_NAMEGEN import get_name
from ... features.finalize_phase.HG_POSE import apply_pose
from ... features.common.HG_COMMON_FUNC import ShowMessageBox, add_to_collection, find_human, get_prefs
from ... core.HG_PCOLL import refresh_pcoll

import time
import mathutils #type: ignore
from sys import platform

class HG_REVERT_CREATION(bpy.types.Operator):
    """
    Reverts to creation phase by deleting the current human and making the corresponding backup human the active human
    """
    bl_idname = "hg3d.revert"
    bl_label = "Revert: ALL changes made after creation phase will be discarded. This may break copied version of this human"
    bl_description = "Revert to the creation phase. This discards any changes made after the creation phase"
    bl_options = {"UNDO"}

    def execute(self,context):
        hg_rig    = find_human(context.active_object)
        hg_backup = hg_rig.HG.backup
        children  = [child for child in hg_rig.children]

        #remove current human, including all children of the current human
        for child in children:
            bpy.data.objects.remove(child)
        bpy.data.objects.remove(hg_rig)

        #backup human: rename, make visible, add to collection
        hg_backup.name          = hg_backup.name.replace('_Backup', '')
        hg_backup.hide_viewport = False
        hg_backup.hide_render   = False
        add_to_collection(context, hg_backup)
        
        #backup children: set correct body_obj property, add to collection, make visible
        hg_body = None
        for child in hg_backup.children:
            if 'hg_body' in child:
                hg_backup.HG.body_obj = child
                hg_body = child
            add_to_collection(context, child)
            child.hide_viewport = False
            child.hide_render   = False

        #point constraints to the correct rig
        p_bones= hg_backup.pose.bones
        for bone in [p_bones['jaw'], p_bones['jaw_upper']]:
            child_constraints = [c for c in bone.constraints if c.type == 'CHILD_OF' or c.type == 'DAMPED_TRACK']
            for c in child_constraints:
                c.target = hg_body

        context.view_layer.objects.active = hg_backup

        return {'FINISHED'}

    def invoke(self, context, event):
        #confirmation checkbox
        return context.window_manager.invoke_confirm(self, event)

class HG_START_CREATION(bpy.types.Operator):
    """
    imports human, setting the correct custom properties. Main function external because it will be used by batch operators too
    """
    bl_idname = "hg3d.startcreation"
    bl_label = "Generate New Human"
    bl_description = "Generate a new human"
    bl_options = {"UNDO"}

    @classmethod
    def poll (cls, context):
        return context.scene.HG3D.pcoll_humans != 'none'

    def execute(self,context):
        sett = context.scene.HG3D
        sett.ui_phase = 'body'

        hg_rig, _ = load_human_v2(context)
        hg_rig.select_set(True)
        context.view_layer.objects.active = hg_rig

        name = give_name(sett.gender, hg_rig)

        self.report({'INFO'}, "You've created: {}".format(name))
        
        return {'FINISHED'}


def load_human_v2(context, creator = False):
    sett = context.scene.HG3D
    pref = get_prefs()

    #import from HG_Human file
    blendfile = str(pref.filepath) + str(Path('/models/HG_HUMAN.blend'))
    with bpy.data.libraries.load(blendfile, link = False) as (data_from ,data_to):
        data_to.objects = ['HG_Rig', 'HG_Body', 'HG_Eyes', 'HG_TeethUpper', 'HG_TeethLower'] 

    gender = sett.gender if not creator else 'female'
    
    #link to scene
    hg_rig          = data_to.objects[0]
    hg_rig.location = context.scene.cursor.location
    hg_body         = data_to.objects[1]
    hg_eyes         = data_to.objects[2]
    scene           = context.scene
    for obj in data_to.objects: 
        scene.collection.objects.link(obj)
        add_to_collection(context, obj)

    #set custom properties for identifying
    hg_body['hg_body'] = 1
    hg_eyes['hg_eyes'] = 1
    hg_teeth = [obj for obj in data_to.objects if 'Teeth' in obj.name]
    for tooth in hg_teeth:
        tooth['hg_teeth'] = 1

    #custom properties
    HG          = hg_rig.HG
    HG.ishuman  = True
    HG.gender   = sett.gender
    HG.phase    = 'body' if not creator else 'creator'
    HG.body_obj = hg_body
    HG.length   = hg_rig.dimensions[2]

    load_external_shapekeys(context, pref, hg_body)

    context.view_layer.objects.active = hg_rig
    if not creator: #skip this for creator human       
        set_gender_shapekeys_v2(hg_body, gender)
        context.view_layer.objects.active = hg_body
        delete_gender_hair(hg_body, gender)
        context.view_layer.objects.active = hg_rig
 
        if platform == 'darwin':
            nodes = hg_body.data.materials[0].node_tree.nodes
            links = hg_body.data.materials[0].node_tree.links
            links.new(nodes['Mix_reroute_1'].outputs[0], nodes['Mix_reroute_2'].inputs[1])

        #set correct gender specific node group
        if gender == 'male':
            male_specific_shader(hg_body)
        mat   = hg_body.data.materials[0]
        nodes = mat.node_tree.nodes
        mat.node_tree.nodes.remove(nodes['Delete_node'])
        
        json_path = pref.filepath + sett.pcoll_humans.replace('jpg', 'json')
        with open(json_path) as json_file:
            preset_data = json.load(json_file)

        context.view_layer.objects.active = hg_rig
        if preset_data['experimental']:
            bpy.ops.hg3d.experimental()
        
        sett.human_length = preset_data['body_proportions']['length']*100
        sett.chest_size = preset_data['body_proportions']['chest']  

        sks = hg_body.data.shape_keys.key_blocks
        missed_shapekeys = 0
        for sk_name, sk_value in preset_data['shapekeys'].items():
            try:
                sks[sk_name].value = sk_value
            except KeyError:
                missed_shapekeys += 1

        refresh_pcoll(None, context, 'textures')
        texture_name         = preset_data['material']['diffuse']
        texture_library      = preset_data['material']['texture_library']
        sett.texture_library = preset_data['material']['texture_library']
        sett.pcoll_textures  = str(Path(f'/textures/{gender}/{texture_library}/{texture_name}'))

        nodes = hg_body.data.materials[0].node_tree.nodes
        for node_name, input_dict in preset_data['material']['node_inputs'].items():
            node = nodes[node_name]
            for input_name, value in input_dict.items():
                node.inputs[input_name].default_value = value

        eye_nodes = hg_eyes.data.materials[1].node_tree.nodes
        for node_name, value in preset_data['material']['eyes'].items():
            eye_nodes[node_name].inputs[2].default_value = value

        if 'eyebrows' in preset_data:           
            eyebrows = [mod for mod in hg_body.modifiers if mod.type == 'PARTICLE_SYSTEM' and mod.particle_system.name.startswith('Eyebrows')]
            for mod in eyebrows:
                mod.show_viewport = mod.show_render = False

            preset_eyebrows = next((mod for mod in eyebrows if mod.particle_system.name == preset_data['eyebrows']), None)
            if not preset_eyebrows:
                ShowMessageBox(message = 'Could not find eyebrows named ' + preset_data['eyebrows'])
            else:
                preset_eyebrows.show_viewport = preset_eyebrows.show_render = True

    #collapse modifiers
    for mod in hg_body.modifiers:
        mod.show_expanded = False

    return hg_rig, hg_body

#REMOVE
def load_human(context, creator = False):
    sett = context.scene.HG3D
    pref = get_prefs()

    #import from HG_Human file
    blendfile = str(pref.filepath) + str(Path('/models/HG_HUMAN.blend'))
    with bpy.data.libraries.load(blendfile, link = False) as (data_from ,data_to):
        data_to.objects = ['HG_Rig', 'HG_Body', 'HG_Eyes', 'HG_TeethUpper', 'HG_TeethLower'] 

    gender = sett.gender if not creator else 'female'
    ethnicity = os.path.splitext(os.path.basename(sett.pcoll_humans))[0] if not creator else 'Caucasian'

    #link to scene
    hg_rig          = data_to.objects[0]
    hg_rig.location = context.scene.cursor.location
    hg_body         = data_to.objects[1]
    hg_eyes         = data_to.objects[2]
    scene           = context.scene
    for obj in data_to.objects:
        scene.collection.objects.link(obj)
        add_to_collection(context, obj)

    #set custom properties for identifying
    hg_body['hg_body'] = 1
    hg_eyes['hg_eyes'] = 1
    hg_teeth = [obj for obj in data_to.objects if 'Teeth' in obj.name]
    for tooth in hg_teeth:
        tooth['hg_teeth'] = 1

    load_external_shapekeys(context, pref, hg_body)
    
    context.view_layer.objects.active = hg_rig
    if not creator: #skip this for creator human
        set_ethnicity_gender_shapekeys(hg_body, gender, ethnicity)      
        context.view_layer.objects.active = hg_body
        delete_gender_hair(hg_body, gender)
        context.view_layer.objects.active = hg_rig
 
        if platform == 'darwin':
            nodes = hg_body.data.materials[0].node_tree.nodes
            links = hg_body.data.materials[0].node_tree.links
            links.new(nodes['Mix_reroute_1'].outputs[0], nodes['Mix_reroute_2'].inputs[1])

        #set correct gender specific node group
        if gender == 'male':
            male_specific_shader(hg_body)
        mat = hg_body.data.materials[0]
        nodes = mat.node_tree.nodes
        mat.node_tree.nodes.remove(nodes['Delete_node'])
        nodes['Skin_tone'].inputs['Tone'].default_value = 2 if ethnicity == 'Caucasian' else 1
        hair_children_to_1(hg_body)

    #custom properties
    HG          = hg_rig.HG
    HG.ishuman  = True
    HG.gender   = sett.gender
    HG.phase    = 'body' if not creator else 'creator'
    HG.body_obj = hg_body
    HG.length   = hg_rig.dimensions[2]

    refresh_pcoll(None, context, 'textures')
    sett.textures_censoring = 'censored'
    texture_name            = '/female_skin_light_col_4k_b.png'
    sett.texture_library    = 'Default'
    sett.pcoll_textures     = str(Path(f'/textures/{gender}/Default/{texture_name}'))

    #collapse modifiers
    for mod in hg_body.modifiers:
        mod.show_expanded = False

    return hg_rig, hg_body

def load_external_shapekeys(context, pref, hg_body):
    context.view_layer.objects.active = hg_body
    walker = os.walk(str(pref.filepath) + str(Path('/models/shapekeys')))
    print('start walking in ', str(pref.filepath) + str(Path('/models/shapekeys')))
    for root, _, filenames in walker:
        for fn in filenames:
            print(f'found {fn} in {root}')
            if not os.path.splitext(fn)[1] == '.blend':
                continue

            blendfile = root + str(Path(f'/{fn}'))
            with bpy.data.libraries.load(blendfile, link = False) as (data_from ,data_to):
                data_to.objects = data_from.objects
            
            print('objects', data_to.objects)
            imported_body = [obj for obj in data_to.objects if obj.name.lower() == 'hg_shapekey'][0] 
            context.scene.collection.objects.link(imported_body)

            for obj in context.selected_objects:
                obj.select_set(False)
            hg_body.select_set(True)
            imported_body.select_set(True)
            for idx, sk in enumerate(imported_body.data.shape_keys.key_blocks):
                if sk.name in ['Basis', 'Male']:
                    continue
                imported_body.active_shape_key_index = idx
                bpy.ops.object.shape_key_transfer()
            imported_body.select_set(False)
            bpy.data.objects.remove(imported_body)
    hg_body.show_only_shape_key = False

def hair_children_to_1(hg_body):
    for mod in hg_body.modifiers:
        if mod.type == 'PARTICLE_SYSTEM':
            ps_sett = mod.particle_system.settings
            if ps_sett.child_nbr > 1:
                ps_sett.child_nbr = 1

def delete_gender_hair(hg_body, gender):
    ps_delete_dict = {
        'female': ('Eyebrows_Male', 'Eyelashes_Male'),
        'male': ('Eyebrows_Female', 'Eyelashes_Female')
    }
    
    for ps_name in ps_delete_dict[gender]:
        ps_idx = [i for i, ps in enumerate(hg_body.particle_systems) if ps.name == ps_name]
        hg_body.particle_systems.active_index = ps_idx[0]
        bpy.ops.object.particle_system_remove()  


def set_gender_shapekeys_v2(hg_body, gender):
    for sk in [sk for sk in hg_body.data.shape_keys.key_blocks]:
        if sk.name.lower().startswith(gender):
            if sk.name != 'Male':
                sk.name = sk.name.replace('{}_'.format(gender.capitalize()), '')
        opposite_gender = 'male' if gender == 'female' else 'female'    
        if sk.name.lower().startswith(opposite_gender) and sk.name != 'Male':
            hg_body.shape_key_remove(sk)

def set_ethnicity_gender_shapekeys(hg_body, gender, ethnicity):
    for sk in [sk for sk in hg_body.data.shape_keys.key_blocks]:
        if sk.name.lower().startswith(gender):
            if sk.name != 'Male':
                sk.name = sk.name.replace('{}_'.format(gender.capitalize()), '')
        opposite_gender = 'male' if gender == 'female' else 'female'    
        if sk.name.lower().startswith(opposite_gender):
            hg_body.shape_key_remove(sk)

        elif sk.name in ['Caucasian', 'Black', 'Asian']:
            if sk.name == ethnicity:
                sk.mute = False
                sk.value = 1
            else:
                sk.mute = False
                sk.value = 0      

def load_textures(self, context):
    hg_rig  = find_human(context.object)
    hg_body = hg_rig.HG.body_obj
    gender  = hg_rig.HG.gender

    sett            = context.scene.HG3D
    diffuse_texture = sett.pcoll_textures
    library         = sett.texture_library

    if diffuse_texture == 'none':
        print('tex is none')
        return

    pref = get_prefs()
    mat = hg_body.data.materials[0]
    nodes = mat.node_tree.nodes

    add_texture(nodes['Color'], diffuse_texture, 'Color')

    for node in nodes:
        for tx_type in ['skin_rough_spec', 'Normal']:
            if tx_type in node.name and node.bl_idname == 'ShaderNodeTexImage':
                add_texture(node, f'textures/{gender}/{library}/PBR/', tx_type)
    
    mat['texture_library'] = library

def add_texture(node, sub_path, tx_type):
    """
    Adds correct image to the teximage node
    """
    pref = get_prefs()

    filepath = str(pref.filepath) + str(Path(sub_path))

    if tx_type == 'Color':
        image_path = filepath
    else:
        print('searching', filepath)
        for fn in os.listdir(filepath):
            print(f'found {fn} in {filepath}')
            if tx_type[:4].lower() in fn.lower():
                image_path = filepath + str(Path('/{}'.format(fn)))
    print('adding', image_path)
    image = bpy.data.images.load(image_path, check_existing=True)
    node.image = image
    if tx_type != 'Color':
        if pref.nc_colorspace_name:
            image.colorspace_settings.name = pref.nc_colorspace_name
            return
        found = False
        for color_space in ['Non-Color', 'Non-Colour Data', 'Utility - Raw']:
            try:
                image.colorspace_settings.name = color_space
                found = True
                break
            except TypeError:
                pass
        if not found:
            ShowMessageBox(message = 'Could not find colorspace alternative for non-color data, default colorspace used')


def male_specific_shader(hg_body):
    """
    Male and female humans of HumGen use the same shader, but one node group is different.
    This function ensures the right nodegroup is connected
    """
    mat = hg_body.data.materials[0]
    nodes = mat.node_tree.nodes

    gender_specific_node = nodes['Gender_Group']
    male_node_group = [ng for ng in bpy.data.node_groups if '.HG_Beard_Shadow' in ng.name][0]
    gender_specific_node.node_tree = male_node_group

#RELEASE new human file make scale independent of parent
def scale_bones(self, context, bone_type):
    """
    Scales the bones based on the user input
    """
    hg_rig       = find_human(context.object)
    experimental = hg_rig.HG.experimental
    sett         = context.scene.HG3D

    size_dict= {
        'head'     : sett.head_size,
        'neck'     : sett.neck_size,
        'shoulder' : sett.shoulder_size,
        'chest'    : sett.chest_size,
        'breast'   : sett.breast_size,
        'forearm'  : sett.forearm_size,
        'upper_arm': sett.upper_arm_size,
        'hips'     : sett.hips_size,
        'thigh'    : sett.thigh_size,
        'shin'     : sett.shin_size,
        'foot'     : sett.foot_size,
        'hand'     : sett.hand_size,
    }

    s = size_dict[bone_type]
    scaling_dict = {
        'head'     : {'x': s/5+0.9,   'y': 'copy', 'z': 'copy', 'bones': ['head']},
        'neck'     : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['neck']},
        'chest'    : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['spine.002', 'spine.003']},
        'shoulder' : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['shoulder.L', 'shoulder.R']},
        'breast'   : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['breast.L', 'breast.R']},
        'forearm'  : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['forearm.L', 'forearm.R']},
        'upper_arm': {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['upper_arm.L', 'upper_arm.R']},
        'hips'     : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['spine.001', 'spine']},
        'thigh'    : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['thigh.L', 'thigh.R']},
        'shin'     : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['shin.L', 'shin.R']},
        'foot'     : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['foot.L', 'foot.R']},
        'hand'     : {'x': (s+2.5)/3, 'y': 'copy', 'z': 'copy', 'bones': ['hand.L', 'hand.R']},
    }

    # if experimental:
    #     size = (context.scene.HG3D.chest_size + 0.5)
    # else:
    #     size = (context.scene.HG3D.chest_size + 2.5)/3

    sc = scaling_dict[bone_type]
    for bone_name in sc['bones']:
        bone = hg_rig.pose.bones[bone_name]
        x = sc['x']
        y = sc['x'] if sc['y'] == 'copy' else sc['y']
        z = sc['x'] if sc['z'] == 'copy' else sc['z']
        
        bone.scale = (
            x if sc['x'] else bone.scale[0],
            y if sc['y'] else bone.scale[1],
            z if sc['z'] else bone.scale[2]
            )
    

def give_name(gender, hg_rig):
    """
    Gives a name to the newly created human
    """
    #get a list of names that are already taken in this scene
    taken_names = []
    for obj in bpy.data.objects:
        if not obj.HG.ishuman:
            continue
        taken_names.append(obj.name[4:])
    
    #generate name
    name = get_name(gender)

    #get new name if it's already taken
    i=0
    while i<10 and name in taken_names:
        name = get_name(gender)
        i+=1
    
    hg_rig.name = 'HG_' + name

    return name
 



