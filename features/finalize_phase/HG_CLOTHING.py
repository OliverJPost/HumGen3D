"""
Operators and functions used for clothing, outfits and footwear of the humans.
""" 

from pathlib import Path

import bpy  # type: ignore

from ...data.HG_COLORS import color_dict
from ...features.common.HG_COMMON_FUNC import (find_human, get_prefs,
                                               hg_delete, hg_log)
from ...features.common.HG_RANDOM import set_random_active_in_pcoll
from ...features.finalize_phase.HG_CLOTHING_LOAD import find_masks


class HG_BACK_TO_HUMAN(bpy.types.Operator):
    """Makes the rig the active object, changing the ui back to the default state
    
    API: False
    
    Operator type:
        Selection
        HumGen UI manipulation
    
    Prereq:
        Cloth object was active
    """
    bl_idname      = "hg3d.backhuman"
    bl_label       = "Back to Human"
    bl_description = "Makes the human the active object"
    
    def execute(self, context):    
        hg_rig = find_human(context.object)
        context.view_layer.objects.active = hg_rig
        return {'FINISHED'} 

class HG_DELETE_CLOTH(bpy.types.Operator):
    """Deletes the selected cloth object, also removes any mask modifiers this
    cloth was using
    
    Operator type:
        Object deletion
    
    Prereq:
        Active object is a HumGen clothing object
    """
    bl_idname = "hg3d.deletecloth"
    bl_label = "Delete cloth"
    bl_description = "Deletes this clothing object"
    
    def execute(self, context):    
        hg_rig  = find_human(context.object)
        hg_body = hg_rig.HG.body_obj

        cloth_obj = context.object
        remove_masks = find_masks(cloth_obj)
        hg_delete(cloth_obj)

        remove_mods = [mod for mod in hg_body.modifiers if mod.type == 'MASK' and mod.name in remove_masks]
        
        for mod in remove_mods:
            hg_body.modifiers.remove(mod)

        context.view_layer.objects.active = hg_rig
        return {'FINISHED'} 

class HG_OT_PATTERN(bpy.types.Operator):
    """
    Adds a pattern to the selected cloth material, adding the necessary nodes. Also used for removing the pattern
    """ 
    bl_idname = "hg3d.pattern"
    bl_label = "Cloth Pattern"
    bl_description = "Toggles pattern on and off"
    
    add: bpy.props.BoolProperty() #True means the pattern is added, False means the pattern will be removed

    def execute(self, context):    
        mat        = context.object.active_material
        self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links
        
        #finds the nodes, adding them if they don't exist
        img_node = self._create_node_if_doesnt_exist('HG_Pattern')
        mapping_node = self._create_node_if_doesnt_exist('HG_Pattern_Mapping')
        coord_node = self._create_node_if_doesnt_exist('HG_Pattern_Coordinates')

        #deletes the nodes
        if not self.add: 
            mat.node_tree.nodes.remove(img_node)
            mat.node_tree.nodes.remove(mapping_node)
            mat.node_tree.nodes.remove(coord_node)
            self.nodes['HG_Control'].inputs['Pattern'].default_value = (0,0,0,1)
            return {'FINISHED'} 
        
        set_random_active_in_pcoll(context, context.scene.HG3D, 'patterns')
        return {'FINISHED'} 

    def _create_node_if_doesnt_exist(self, name) -> bpy.types.ShaderNode:
        """Returns the node, creating it if it doesn't exist
        
        Args:
            name (str): name of node to check
        
        Return
            node (ShaderNode): node that was being searched for
        """ 
        #try to find the node, returns it if it already exists
        for node in self.nodes:
            if node.name == name:
                return node
        
        #adds the node, because it doesn't exist yet
        type_dict   = {
            'HG_Pattern'            : 'ShaderNodeTexImage',
            'HG_Pattern_Mapping'    : 'ShaderNodeMapping',
            'HG_Pattern_Coordinates': 'ShaderNodeTexCoord'
            }
        
        node      = self.nodes.new(type_dict[name])
        node.name = name
        
        link_dict = {
            'HG_Pattern'            : (0, 'HG_Control', 9),
            'HG_Pattern_Mapping'    : (0, 'HG_Pattern', 0),
            'HG_Pattern_Coordinates': (2, 'HG_Pattern_Mapping', 0)
          }
        target_node = self.nodes[link_dict[name][1]]
        self.links.new(node.outputs[link_dict[name][0]], target_node.inputs[link_dict[name][2]])

        return node

def load_pattern(self,context):
    """
    Loads the pattern that is the current active item in the patterns preview_collection
    """  
    pref = get_prefs()
    mat = context.object.active_material

    #finds image node, returns error if for some reason the node doesn't exist
    try:
        img_node = mat.node_tree.nodes['HG_Pattern']
    except:
        self.report({'WARNING'}, "Couldn't find pattern node, click 'Remove pattern' and try to add it again")

    filepath = str(pref.filepath) + str(Path(context.scene.HG3D.pcoll_patterns))
    images   = bpy.data.images
    pattern  = images.load(filepath, check_existing=True)
    
    img_node.image = pattern

def randomize_clothing_colors(context, cloth_obj):
    mat = cloth_obj.data.materials[0]
    if not mat:
        return
    nodes = mat.node_tree.nodes
    
    control_node = nodes.get('HG_Control')
    if not control_node:
        hg_log(f'Could not set random color for {cloth_obj.name}, control node not found', level = 'WARNING')
        return
    
    #TODO Rewrite color_random so it doesn't need to be called as operator
    old_active = context.view_layer.objects.active 
    
    for input in control_node.inputs:
        color_groups = tuple(['_{}'.format(name) for name in color_dict])     
        color_group = (
            input.name[-2:] 
            if input.name.endswith(color_groups) 
            else None
            )

        if not color_group:
            continue
        
        context.view_layer.objects.active = cloth_obj

        bpy.ops.hg3d.color_random(input_name = input.name, color_group = color_group)
    
    context.view_layer.objects.active = old_active
