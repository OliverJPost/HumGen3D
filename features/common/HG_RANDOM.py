'''
Randomize operator for sliders and pcolls
'''

import bpy #type: ignore
import random
from .   HG_COMMON_FUNC import find_human
from ... core.HG_PCOLL import preview_collections, refresh_pcoll
from ..  creation_phase.HG_LENGTH import random_length
from ... data.HG_COLORS import color_dict

class HG_COLOR_RANDOM(bpy.types.Operator):
    """
    sets the color slot to a random color from the color dicts from HG_COLORS
    """
    bl_idname      = "hg3d.colorrandom"
    bl_label       = "Random Color"
    bl_description = "Randomize this property"
    bl_options     = {"UNDO", 'INTERNAL'}

    input_name : bpy.props.StringProperty()
    color_group: bpy.props.StringProperty()

    def execute(self,context):
        color_hex       = random.choice(color_dict[self.color_group])
        color_rgb       = [int(color_hex[i:i+2], 16) for i in (0, 2, 4)]
        float_color_rgb = [x / 255.0 for x in color_rgb]
        float_color_rgb.append(1)
        input               = context.object.active_material.node_tree.nodes['HG_Control'].inputs[self.input_name]
        input.default_value = tuple(float_color_rgb)
        
        return {'FINISHED'}

class HG_RANDOM(bpy.types.Operator):
    """
    randomizes this specific property, may it be a slider of a pcoll
    """
    bl_idname      = "hg3d.random"
    bl_label       = "Redraw Random"
    bl_description = "Randomize this property"
    bl_options     = {"UNDO", 'INTERNAL'}

    type : bpy.props.StringProperty()

    def execute(self,context):
        type = self.type
        sett = context.scene.HG3D
        hg_rig = find_human(context.active_object)

        if type == 'body_type':
            random_body_type(hg_rig)
        elif type == 'length':
            random_length(context,hg_rig)
        elif type in ('poses', 'expressions', 'outfit', 'patterns', 'footwear', 'hair'):
            get_random_from_pcoll(context, sett, type)
        elif type == 'skin':
            randomize_skin(context, hg_rig.HG.body_obj)
        elif type.startswith('face'):
            key = type[5:]
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
            face_sk = [sk for sk in hg_rig.HG.body_obj.data.shape_keys.key_blocks if sk.name.startswith(prefix_dict[key])] 
            for sk in face_sk:
                sk.value = random.uniform(sk.slider_min, sk.slider_max)
        
        return {'FINISHED'}

def randomize_skin(context, hg_body):
    mat = hg_body.data.materials[0]
    nodes = mat.node_tree.nodes
    node_randomize_dict= {
        nodes['Lighten_hsv'].inputs['Value']     : (0,2),
        nodes['Darken_hsv'].inputs['Value']      : (0,2),
        nodes['Skin_tone'].inputs[1]             : (.1, 3),
        nodes['Skin_tone'].inputs[2]             : (-1, 1),
        nodes['Freckles_control'].inputs['Pos2'] : None
    }

def random_body_type(hg_rig):
    hg_body = hg_rig.HG.body_obj
    sks = hg_body.data.shape_keys.key_blocks
    for sk in [sk for sk in sks if sk.name.startswith('bp_')]:
        sk.value = random.random()

def get_random_from_pcoll(context, sett, pcoll_name):
    refresh_pcoll(None, context, pcoll_name)
    current_item = sett['pcoll_{}'.format(pcoll_name) ]
    pcoll_list = sett['previews_list_{}'.format(pcoll_name)]
    random_item = get_random_from_list(pcoll_list, current_item)

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
    
def get_random_from_list(list, current_item):
    try:
        random_item = random.choice(list)
    except IndexError:
        return None
    except:
        raise
    i = 0
    while random_item == current_item and i <5:
        random_item = random.choice(list)
        i+=1

    return random_item



