'''
Randomize operator for sliders and pcolls
'''

import random
from typing import Any

import bpy # type: ignore
from ...features.creation_phase.HG_MATERIAL import randomize_skin_shader  

from ...core.HG_PCOLL import refresh_pcoll
from .HG_COMMON_FUNC import find_human


class HG_COLOR_RANDOM(bpy.types.Operator):
    """
    Sets the color slot to a random color from the color dicts from HG_COLORS
    
    Operator type:
        Material
    
    Prereq:
        Passed arguments
        Active material of active object is a HumGen clothing material
        
    Args:
        input_name (str): Name of HG_Control node input to randomize the color for
        color_group (str):  Name of the color groups stored in HG_COLOR to pick
            colors from
    """
    bl_idname      = "hg3d.color_random"
    bl_label       = "Random Color"
    bl_description = "Randomize this property"
    bl_options     = {"UNDO", 'INTERNAL'}

    input_name : bpy.props.StringProperty()
    color_group: bpy.props.StringProperty()

    def execute(self,context):
        from ...data.HG_COLORS import \
            color_dict  # TODO make color dict into json?
        
        color_hex       = random.choice(color_dict[self.color_group])
        color_rgba = self._hex_to_rgba(color_hex)
        
        nodes = context.object.active_material.node_tree.nodes
        input = nodes['HG_Control'].inputs[self.input_name]
        
        input.default_value = tuple(color_rgba)
        
        return {'FINISHED'}

    def _hex_to_rgba(self, color_hex) -> 'tuple[float, float, float, 1]':
        """Build rgb color from this hex code

        Args:
            color_hex (str): Hexadecimal color code, withhout # in front

        Returns:
            tuple[float, float, float, 1]: rgba color
        """
        color_rgb       = [int(color_hex[i:i+2], 16) for i in (0, 2, 4)]
        float_color_rgb = [x / 255.0 for x in color_rgb]
        float_color_rgb.append(1)
        
        return float_color_rgb

class HG_RANDOM(bpy.types.Operator):
    """randomizes this specific property, may it be a slider or a pcoll

    API: True

    Operator type:
        Prop setter
        Pcoll manipulation
    
    Prereq:
        Passed random_type
        Active object is part of HumGen human

    Args:
        random_type (str): internal name of property to randomize
    """
    bl_idname      = "hg3d.random"
    bl_label       = "Redraw Random"
    bl_description = "Randomize this property"
    bl_options     = {"UNDO", 'INTERNAL'}

    random_type : bpy.props.StringProperty()

    def execute(self,context):
        random_type = self.random_type
        sett = context.scene.HG3D
        hg_rig = find_human(context.active_object)

        if random_type == 'body_type':
            random_body_type(hg_rig)
        elif random_type in ('poses', 'expressions', 'outfit', 'patterns', 'footwear', 'hair'):
            set_random_active_in_pcoll(context, sett, random_type)
        elif random_type == 'skin':
            randomize_skin_shader(hg_rig.HG.body_obj, hg_rig.HG.gender)
        elif random_type.startswith('face'):
            ff_subcateg = random_type[5:] #facial subcategories follow the pattern face_{category}
                                #where face_all does all facial features
            hg_body = hg_rig.HG.body_obj
            self.randomize_facial_feature_categ(hg_body, ff_subcateg)

        
        return {'FINISHED'}

    def randomize_facial_feature_categ(self, hg_body, ff_subcateg):
        """Randomizes the sliders of the passed facial features category

        Args:
            hg_body (Object): body object of a HumGen human
            ff_subcateg (str): subcategory of facial features to randomize, 'all'
                for randomizing all features
        """
        prefix_dict = self._get_ff_prefix_dict()
        face_sk = [sk for sk in hg_body.data.shape_keys.key_blocks 
                       if sk.name.startswith(prefix_dict[ff_subcateg])
                       ] 
        for sk in face_sk:
            sk.value = random.uniform(sk.slider_min, sk.slider_max)

    def _get_ff_prefix_dict(self) -> dict:
        """Returns facial features prefix dict

        Returns:
            dict: key: internal naming of facial feature category
                value: naming prefix of shapekeys that belong to that category
        """
        prefix_dict = {
                'all'    : 'ff',
                'u_skull': ('ff_a', 'ff_b'),
                'eyes'   : 'ff_c',
                'l_skull': 'ff_d',
                'nose'   : 'ff_e',
                'mouth'  : 'ff_f',
                'chin'   : 'ff_g',
                'cheeks' : 'ff_h',
                'jaw'    : 'ff_i',
                'ears'   : 'ff_j',
                'custom' : 'ff_x'
                }
            
        return prefix_dict


def random_body_type(hg_rig):
    """Randomizes the body type sliders of the active human

    Args:
        hg_rig (Object): HumGen armature
    """
    hg_body = hg_rig.HG.body_obj
    sks = hg_body.data.shape_keys.key_blocks
    
    for sk in [sk for sk in sks if sk.name.startswith('bp_')]:
        sk.value = random.random()

def set_random_active_in_pcoll(context, sett, pcoll_name, searchterm = None):
    """Sets a random object in this preview colleciton as active

    Args:
        sett (PropertyGRoup): HumGen props
        pcoll_name (str): internal name of preview collection to pick random for
        searchterm (str): filter to only look for items in the pcoll that include this string
    """
    
    refresh_pcoll(None, context, pcoll_name)
    
    current_item = sett['pcoll_{}'.format(pcoll_name) ]
    
    pcoll_list = sett['previews_list_{}'.format(pcoll_name)]
    random_item = get_random_from_list(pcoll_list, current_item, searchterm)

    #TODO implement set_attr
    if pcoll_name == 'poses':
        sett.pcoll_poses = random_item
    elif pcoll_name == 'expressions':
        sett.pcoll_expressions = random_item
    elif pcoll_name == 'outfit':
        sett.pcoll_outfit = random_item
    elif pcoll_name == 'humans':
        sett.pcoll_humans = random_item
    elif pcoll_name == 'hair':
        sett.pcoll_hair = random_item
    elif pcoll_name == 'footwear':
        sett.pcoll_footwear = random_item
    elif pcoll_name == 'patterns':
        sett.pcoll_patterns = random_item
    
def get_random_from_list(list, current_item, searchterm) -> Any:
    """Gets a random item from passed list, trying max 6 times to prevent choosing
    the currently active item

    Args:
        list (list): list to choose item from
        current_item (AnyType): currently active item
        searchterm (str): filter to only look for items in the pcoll that include this string

    Returns:
        Any: randomly chosen item
    """
    
    corrected_list = [item for item in list if searchterm in item.lower()] if searchterm else list
    if not corrected_list:
        print('ERROR: Searchterm not found in pcoll: ', searchterm)
        corrected_list = list
    
    try:
        random_item = random.choice(corrected_list)
    except IndexError:
        return None
    
    i = 0
    while random_item == current_item and i <5:
        random_item = random.choice(corrected_list)
        i+=1

    return random_item



