import bpy #type: ignore
import os
from pathlib import Path

from ... features.common.HG_COMMON_FUNC import (
    ShowMessageBox,
    find_human,
    get_prefs
)

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
                corrected_fn = fn.replace('_4K', '').replace('_MEDIUM', '').replace('_LOW', '')
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
