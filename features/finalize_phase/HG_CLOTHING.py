"""
Operators and functions used for clothing, outfits and footwear of the humans.
""" 

import bpy #type: ignore
import os
from pathlib import Path
from ... features.common.HG_COMMON_FUNC import add_to_collection, find_human, apply_shapekeys 
from ... core.HG_PCOLL import refresh_pcoll
from ... features.common.HG_RANDOM import get_random_from_pcoll
# from . HG_POSE import set_high_heel_rotation

class HG_BACK_TO_HUMAN(bpy.types.Operator):
    """
    makes the rig the active object, changing the ui back to the default state
    """
    bl_idname      = "hg3d.backhuman"
    bl_label       = "Back to Human"
    bl_description = "Makes the human the active object"
    
    def execute(self, context):    
        hg_rig = find_human(context.object)
        context.view_layer.objects.active = hg_rig
        return {'FINISHED'} 

class HG_DELETE_CLOTH(bpy.types.Operator):
    """
    Deletes the selected cloth object, also removes any mask modifiers this cloth was using
    """
    bl_idname = "hg3d.deletecloth"
    bl_label = "Delete cloth"
    bl_description = "Deletes this clothing object"
    
    def execute(self, context):    
        hg_rig  = find_human(context.object)
        hg_body = hg_rig.HG.body_obj

        cloth_obj = context.object
        remove_masks = find_masks(cloth_obj)
        bpy.data.objects.remove(cloth_obj)

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
        img_node = self.check_node('HG_Pattern')
        mapping_node = self.check_node('HG_Pattern_Mapping')
        coord_node = self.check_node('HG_Pattern_Coordinates')

        #deletes the nodes
        if not self.add: 
            mat.node_tree.nodes.remove(img_node)
            mat.node_tree.nodes.remove(mapping_node)
            mat.node_tree.nodes.remove(coord_node)
            self.nodes['HG_Control'].inputs['Pattern'].default_value = (0,0,0,1)
            return {'FINISHED'} 
        
        get_random_from_pcoll(context, context.scene.HG3D, 'patterns')
        return {'FINISHED'} 

    def check_node(self, name):
        """
        returns the node, creating it if it doesn't exist
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
        node        = self.nodes.new(type_dict[name])
        node.name   = name
        link_dict   = {
            'HG_Pattern'            : (0, 'HG_Control', 9),
            'HG_Pattern_Mapping'    : (0, 'HG_Pattern', 0),
            'HG_Pattern_Coordinates': (2, 'HG_Pattern_Mapping', 0)
          }
        target_node = self.nodes[link_dict[name][1]]
        self.links.new(node.outputs[link_dict[name][0]], target_node.inputs[link_dict[name][2]])

        return node

def load_pattern(self,context):
    """
    loads the pattern that is the current active item in the patterns preview_collection
    """  
    pref = context.preferences.addons[__package__].preferences
    mat = context.object.active_material

    #finds image node, returns error if for some reason the node doesn't exist
    try:
        img_node = mat.node_tree.nodes['HG_Pattern']
    except:
        self.report({'WARNING'}, "Couldn't find pattern node, click 'Remove pattern' and try to add it again")

    filepath       = str(pref.filepath) + str(Path(context.scene.HG3D.pcoll_patterns))
    images         = bpy.data.images
    pattern        = images.load(filepath, check_existing=True)
    img_node.image = pattern


#REMOVE
def load_outfit(self,context, footwear = False):
    """
    loads the outfit that is the current active item in the outfit preview_collection
    """  
    pref             = context.preferences.addons[__package__].preferences
    mask_remove_list = []
    scene            = context.scene
    sett             = scene.HG3D
    hg_rig           = find_human(context.active_object)
    hg_body          = hg_rig.HG.body_obj
    
    hg_rig.hide_set(False)
    hg_rig.hide_viewport = False
    
    #returns immediately if the active item in the preview_collection is the 'click here to select' icon
    if (not footwear and sett.pcoll_outfit == 'none') or (footwear and sett.pcoll_footwear == 'none'):
        return

    #removes previous outfit/shoes if the preferences option is True
    tag = 'shoe' if footwear else 'cloth'
    if pref.remove_clothes:  
        for child in [child for child in hg_rig.children]:
            if tag in child:
                mask_remove_list.extend(find_masks(child))
                bpy.data.objects.remove(child)

    #load the whole collection from the outfit file. It loads collections instead of objects because this allows loading of linked objects
    pcoll_item = sett.pcoll_footwear if footwear else sett.pcoll_outfit
    blendfile  = str(pref.filepath) + str(Path(pcoll_item))
    with bpy.data.libraries.load(blendfile, link = False) as (data_from ,data_to):
        data_to.collections = data_from.collections
        
    #appends all collections and objects to scene
    collections = data_to.collections
    cloth_objs = []
    for col in collections:
        context.scene.collection.children.link(col)
        for obj in col.objects:
            cloth_objs.append(obj)

    for obj in context.selected_objects:
        obj.select_set(False)

    #loads cloth objects in the humgen collection and sets the rig as their parent. This also makes sure their rotation and location is correct
    for obj in cloth_objs:
        add_to_collection(context, obj)
        obj.parent = hg_rig
        obj.select_set(True)

    #makes linked objects/textures/nodes local
    bpy.ops.object.make_local(type='SELECT_OBDATA_MATERIAL')
    bpy.ops.object.make_local(type='ALL')


    new_mask_list = []
    for obj in cloth_objs:     
        new_mask_list.extend(find_masks(obj))
        obj[tag] = 1 #adds a custom property to the cloth for identifying purposes
        
        try:
            sk = obj.data.shape_keys.key_blocks
        except:
            print('could not get shape keys for ', obj.name)
            continue
        
        set_cloth_shapekeys(sk, hg_rig)
        set_cloth_corrective_drivers(hg_body, sk)

        #checks if the cloth object already has an armature modifier, adds one if it doesnt
        armature_mods = [mod for mod in obj.modifiers if mod.type == 'ARMATURE']
        if not armature_mods:
            armature_mods.append(obj.modifiers.new("Armature", 'ARMATURE'))
        armature_mods[0].object = hg_rig
        context.view_layer.objects.active = obj
        for mod in armature_mods:
            if (2, 90, 0) > bpy.app.version: #use old method for versions older than 2.90
                while obj.modifiers.find(mod.name) != 0:
                    bpy.ops.object.modifier_move_up({'object': obj}, modifier=mod.name)
            else:
                bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)

        context.view_layer.objects.active = hg_rig

        obj.parent = hg_rig
        
        #collapse modifiers
        for mod in obj.modifiers:
            mod.show_expanded = False

        # if footwear:
        #     set_high_heel_rotation(hg_rig, obj)

    #remove collection that was imported along with the cloth objects
    for col in collections:
        bpy.data.collections.remove(col)

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
        mod.vertex_group        = mask
        mod.invert_vertex_group = True

    #refresh pcoll for consistent 'click here to select' icon
    refresh_pcoll(self, context, 'outfit')

def set_cloth_shapekeys(sk, hg_rig):
    """
    sets the cloth shapekeys to the same value as the human
    """  
    sk_names = ['Muscular', 'Overweight', 'Skinny']

    for i, sk_name in enumerate(sk_names): 
        sk[sk_name].mute  = False
        sk[sk_name].value = hg_rig.HG.body_shape[i]
    
    if 'Chest' in sk: 
        sk['Chest'].mute  = False
        sk['Chest'].value = (hg_rig.HG.body_shape[3] * 3) - 2.5

    sk['Shorten'].mute  = False
    sk['Shorten'].value = (-1.9801 * hg_rig.HG.length) + 3.8989

def set_cloth_corrective_drivers(hg_body, sk):
    """
    sets up the drivers of the corrective shapekeys on the clothes
    """  
    for driver in hg_body.data.shape_keys.animation_data.drivers:
        target_sk = driver.data_path.replace('key_blocks["', '').replace('"].value', '')
        if target_sk in [shapekey.name for shapekey in sk]:
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

def find_masks(obj):
    """
    looks at the custom properties of the object, searching for custom tags that indicate mesh masks added for this cloth
    """  
    mask_list = []
    for i in range(10):
        try:
            mask_list.append(obj['mask_{}'.format(i)])
        except:
            continue
    
    return mask_list


