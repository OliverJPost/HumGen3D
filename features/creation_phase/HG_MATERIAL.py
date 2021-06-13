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
    
    mat['texture_library'] = library

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
    """Male and female humans of HumGen use the same shader, but one node 
    group is different. This function ensures the right nodegroup is connected
    
    Args:
        hg_body (Object)
    """
    mat = hg_body.data.materials[0]
    nodes = mat.node_tree.nodes

    gender_specific_node = nodes['Gender_Group']
    male_node_group = [ng for ng in bpy.data.node_groups if '.HG_Beard_Shadow' in ng.name][0]
    gender_specific_node.node_tree = male_node_group
