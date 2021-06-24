import bpy #type: ignore
import mathutils #type:ignore
from mathutils import Vector #type: ignore
from .. features.common.HG_COMMON_FUNC import apply_shapekeys, find_human
from .. features.creation_phase.HG_LENGTH import apply_armature
import numpy as np #type: ignore


#TODO keep
def build_distance_dict(source_org, target, apply = True):
    """
    Returns a dict with a key for each vertex of the source and the value the closest vertex of the target and the distance to it
    """        
    source = source_org.copy()
    source.data = source.data.copy()
    bpy.context.scene.collection.objects.link(source)
    
    apply_shapekeys(source)
    hg_rig = find_human(bpy.context.object)
    if apply:
        apply_armature(source)

    v_source = source.data.vertices
    v_target = target.data.vertices

    size = len(v_source)
    kd = mathutils.kdtree.KDTree(size)

    for i, v in enumerate(v_source):
        kd.insert(v.co, i)

    kd.balance()
    distance_dict = {}
    for vt in v_target:
        vt_loc = target.matrix_world @ vt.co

        co_find = source.matrix_world.inverted() @ vt_loc

        for (co, index, _) in kd.find_n(co_find, 1):
            v_dist = np.subtract(co, co_find)

            distance_dict[vt.index] = (index, Vector(v_dist))  

    bpy.data.objects.remove(source)
    return distance_dict

#TODO keep
def deform_obj_from_difference(name, distance_dict, source, target, as_shapekey = True):
    """
    Creates a shapekey from the difference between the distance_dict value and the current distance to that corresponding vertex
    """
    source_copy      = source.copy()
    source_copy.data = source_copy.data.copy()
    bpy.context.scene.collection.objects.link(source_copy)
    
    for sk in [sk for sk in source_copy.data.shape_keys.key_blocks if sk.name.startswith('cor_')]:
        source_copy.shape_key_remove(sk)
        
    apply_shapekeys(source_copy)
    hg_rig = find_human(bpy.context.object)
    #apply_armature(source_copy)

    if 'Female_' in name or 'Male_' in name:
        name = name.replace('Female_', '')
        name = name.replace('Male_', '')

    sk = None
    if as_shapekey:
        sk = target.shape_key_add(name = name)
        sk.interpolation = 'KEY_LINEAR'
    elif target.data.shape_keys:
        sk = target.data.shape_keys.key_blocks['Basis']

    for vertex_index in distance_dict:
        source_new_vert_loc = source_copy.matrix_world @ source_copy.data.vertices[distance_dict[vertex_index][0]].co
        distance_to_vert    = distance_dict[vertex_index][1]
        world_new_loc       = source_new_vert_loc - distance_to_vert
        if vertex_index == 24:
            print('test', world_new_loc, distance_to_vert)

        if sk:
            sk.data[vertex_index].co = target.matrix_world.inverted() @ world_new_loc
        else:
            target.data.vertices[vertex_index].co = target.matrix_world.inverted() @ world_new_loc

    bpy.data.objects.remove(source_copy)