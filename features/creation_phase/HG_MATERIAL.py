import os
import random
from pathlib import Path

import bpy  # type: ignore

from ...features.common.HG_COMMON_FUNC import (ShowMessageBox, find_human,
                                               get_prefs)


def load_textures(self, context):
    """Called by prop update. Loads selected texture set on human"""
    hg_rig  = find_human(context.object)
    hg_body = hg_rig.HG.body_obj
    gender  = hg_rig.HG.gender

    sett = context.scene.HG3D
    
    diffuse_texture = sett.pcoll_textures
    library         = sett.texture_library

    if diffuse_texture == 'none':
        return

    mat = hg_body.data.materials[0]
    nodes = mat.node_tree.nodes

    add_texture(nodes['Color'], diffuse_texture, 'Color')

    for node in nodes:
        for tx_type in ['skin_rough_spec', 'Normal']:
            if tx_type in node.name and node.bl_idname == 'ShaderNodeTexImage':
                add_texture(node, f'textures/{gender}/{library}/PBR/', tx_type)
    
    if library in ['Default 1K', 'Default 512px']:
        resolution_folder = 'MEDIUM_RES' if library == 'Default 1K' else 'LOW_RES'
        _change_peripheral_texture_resolution(resolution_folder, hg_rig, hg_body)
    
    mat['texture_library'] = library

def _change_peripheral_texture_resolution(resolution_folder, hg_rig, hg_body):
    for obj in hg_rig.children:
        for mat in obj.data.materials:
            for node in [node for node in mat.node_tree.nodes if node.bl_idname == 'ShaderNodeTexImage']:
                if node.name.startswith(('skin_rough_spec', 'Normal', 'Color')) and obj == hg_body:
                    continue
                current_image = node.image
                current_path = current_image.filepath
                
                if 'MEDIUM_RES' in current_path or 'LOW_RES' in current_path:
                    current_dir = Path(os.path.dirname(current_path)).parent
                else:
                    current_dir = os.path.dirname(current_path)
                    
                dir = os.path.join(current_dir, resolution_folder)
                fn, ext = os.path.splitext(os.path.basename(current_path))
                resolution_tag = resolution_folder.replace('_RES', '')
                corrected_fn = fn.replace('_4K', '').replace('_MEDIUM', '').replace('_LOW', '').replace('_2K', '')
                new_fn = corrected_fn+f'_{resolution_tag}'+ext
                new_path = os.path.join(dir, new_fn)
                
                old_color_mode = current_image.colorspace_settings.name
                node.image = bpy.data.images.load(new_path, check_existing=True)
                node.image.colorspace_settings.name = old_color_mode
    

def add_texture(node, sub_path, tx_type):
    """Adds correct image to the teximage node
    
    Args:
        node      (ShaderNode): TexImage node to add image to
        sub_path  (Path)      : Path relative to HumGen folder where the texture 
                               is located
        tx_type   (str)       : what kind of texture it is (Diffuse, Roughness etc.)
    """
    pref = get_prefs()

    filepath = str(pref.filepath) + str(Path(sub_path))

    if tx_type == 'Color':
        image_path = filepath
    else:
        if tx_type == 'Normal':
            tx_type = 'norm'
        for fn in os.listdir(filepath):
            if tx_type.lower() in fn.lower():
                image_path = filepath + str(Path('/{}'.format(fn)))

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

def set_gender_specific_shader(hg_body, gender):
    """Male and female humans of HumGen use the same shader, but one node 
    group is different. This function ensures the right nodegroup is connected
    
    Args:
        hg_body (Object)
    """
    mat = hg_body.data.materials[0]
    nodes = mat.node_tree.nodes

    uw_node = nodes.get('Underwear_Switch')
    if uw_node:
        uw_node.inputs[0].default_value = 1 if gender == 'female'else 0
        
    if gender == 'male':
        gender_specific_node = nodes['Gender_Group']
        male_node_group = [ng for ng in bpy.data.node_groups if '.HG_Beard_Shadow' in ng.name][0]
        gender_specific_node.node_tree = male_node_group


def randomize_skin_shader(hg_body, gender):
    mat = hg_body.data.materials[0]
    nodes = mat.node_tree.nodes
    
    #Tone, redness, saturation
    for input_idx in [1,2,3]:
        if f'skin_tone_default_{input_idx}' in mat:
            default_value = mat[f'skin_tone_default_{input_idx}']
        else:
            default_value = nodes["Skin_tone"].inputs[input_idx].default_value
            mat[f'skin_tone_default_{input_idx}'] = default_value
            
        new_value = random.uniform(default_value*0.8, default_value*1.2)
        nodes["Skin_tone"].inputs[input_idx].default_value = new_value
    
    probability_list = [0,0,0,0,0,0,.2,.3,.5]
    
    #Freckles and splotches
    nodes["Freckles_control"].inputs[3].default_value = random.choice(probability_list)
    nodes["Splotches_control"].inputs[3].default_value = random.choice(probability_list)
    
    #Age
    age_value = random.choice([0,0,0,0,0,0,0,0,0,.2,.5]) * 2
    hg_body.data.shape_keys.key_blocks["age_old.Transferred"].value = age_value
    nodes["HG_Age"].inputs[1].default_value = age_value * 6
    
    if gender == 'male':
        beard_shadow_value = random.choice(probability_list) * 2
        nodes["Gender_Group"].inputs[2].default_value = beard_shadow_value
        nodes["Gender_Group"].inputs[3].default_value = beard_shadow_value

def toggle_sss(self, context):
    '''
    Turns subsurface on and off
    '''
    
    if context.scene.HG3D.update_exception:
        return

    toggle  = context.scene.HG3D.skin_sss
    hg_rig  = find_human(context.object)
    hg_body = hg_rig.HG.body_obj
    mat     = hg_body.data.materials[0]
    
    principled_bsdf = [node for node in mat.node_tree.nodes 
                       if node.type == 'BSDF_PRINCIPLED'][0]

    principled_bsdf.inputs['Subsurface'].default_value = (0.015 if toggle == 'on'
                                                          else 0)


def toggle_underwear(self, context):
    '''
    Turns underwear on and off
    '''
    if context.scene.HG3D.update_exception:
        return
   
    toggle  = context.scene.HG3D.underwear_switch
    hg_rig  = find_human(context.object)
    hg_body = hg_rig.HG.body_obj
    mat     = hg_body.data.materials[0]
    
    underwear_node = mat.node_tree.nodes.get('Underwear_Opacity')
    
    underwear_node.inputs[1].default_value = 1 if toggle == 'on' else 0   

def randomize_iris_color(hg_rig):
    eyes = next(c for c in hg_rig.children if 'hg_eyes' in c)
    inner_mat = eyes.data.materials[1]
    nodes = inner_mat.node_tree.nodes
    
    T_Class = [
        0x3F313B, #T50
        0x633935, #T30
        0x71533C, #T17
        0xB26D55, #T10  
        0x41282C, #T40
        0x6A4A47, #T20
        0x8F7459, #T15
        0xB37556 #T07
    ]
    
    D_Class = [
        0x988856, #D60
        0x8A815A, #D40
        0x7D8169, #D34
        0x52564B, #D20
        0xAE9B73, #D50
        0xAC9B74, #D37
        0x9E945C, #D30
        0x577377  #D10
    ]
    
    C_Class = [
        0x747C7F, #C40
        0x71858F, #C20
        0x9E9D95, #C30
    ]
    
    A_Class = [
        0x6E8699, #A60
        0x9AB4A4, #A30
        0x7FA7B3, #A20
        0x517BA6, #A50
        0x6EA0D1, #A40
        0x7699B7, #A17,
        0xA2C0D7  #A10
        
    ]
    
    # If you think the numers used here are incorrect, please contact us at 
    # support@humgen3d.com

    # Worldwide statistics, based on
    # https://www.worldatlas.com/articles/which-eye-color-is-the-most-common-in-the-world.html
    
    weighted_lists = {
        79 : T_Class, #Brown
        13 : D_Class, #Amber, Hazel and Green
        3: C_Class, #Grey
        9: A_Class  #Blue
    }
    
    pupil_color_hex = random.choice(random.choices(
        [list for _, list in weighted_lists.items()],
        weights= [weight for weight in weighted_lists]
        )[0])
    
    pupil_color_rgb = _hex_to_rgb(pupil_color_hex)
    
    nodes["HG_Eye_Color"].inputs[2].default_value = pupil_color_rgb
    
def _srgb_to_linearrgb(c):
    #Source: https://blender.stackexchange.com/questions/158896/how-set-hex-in-rgb-node-python?noredirect=1#comment269316_158896 
    if   c < 0:       return 0
    elif c < 0.04045: return c/12.92
    else:             return ((c+0.055)/1.055)**2.4

def _hex_to_rgb(h,alpha=1):
    #Source: https://blender.stackexchange.com/questions/158896/how-set-hex-in-rgb-node-python?noredirect=1#comment269316_158896
    r = (h & 0xff0000) >> 16
    g = (h & 0x00ff00) >> 8
    b = (h & 0x0000ff)
    return tuple([_srgb_to_linearrgb(c/0xff) for c in (r,g,b)] + [alpha])
