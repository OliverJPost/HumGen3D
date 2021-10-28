"""UNDER CONSTRUCTION"""

from pathlib import Path

import bmesh  # type: ignore
import bpy  # type: ignore
import numpy as np
from mathutils import Vector

from ...features.common.HG_COMMON_FUNC import (find_human, get_prefs, hg_log,
                                               print_context)


class HG_CONVERT_HAIRCARDS(bpy.types.Operator):
    """
    Removes the corresponding hair system
    """
    bl_idname      = "hg3d.haircards"
    bl_label       = "Convert to hair cards"
    bl_description = "Converts this system to hair cards"
    bl_options     = {"REGISTER", "UNDO"}

    def execute(self,context):
        pref = get_prefs()
        
        hg_rig = find_human(context.object)
        hg_body = hg_rig.HG.body_obj

        for ps in hg_body.particle_systems:
            context.view_layer.objects.active = hg_body
            if ps.name.startswith('Eye') or 'fh' not in ps.name:
                continue
            ps_sett = ps.settings
            p_amount = len(ps.particles)

            ps_sett.child_nbr = 0
            if ps_sett.display_step == 3:
                ps_sett.display_step = 4
            steps = ps_sett.display_step

            for mod in [mod for mod in hg_body.modifiers if mod.type == 'PARTICLE_SYSTEM']:
                if mod.particle_system.name == ps.name:
                    bpy.ops.object.modifier_convert(modifier=mod.name)

                    hc_obj = context.object
            for obj in [obj for obj in context.selected_objects if obj != hc_obj]:
                obj.select_set(False)
 
            bpy.ops.object.convert(target='CURVE')
            hc_obj.data.extrude = 0.008 
            
            spline_distances = build_hair_spline_distance_enum(hc_obj, hg_body)
            
            bpy.ops.object.mode_set(mode='EDIT')
            for spline in hc_obj.data.splines:
                for point in spline.points:
                    point.select = False
                    
            points = []
            for spline_idx, distance_to_center in enumerate(spline_distances):
                spline = hc_obj.data.splines[spline_idx]
                
                negative = distance_to_center < 0
                
                tilt = -666 * abs(distance_to_center) + 70
                
                if tilt <=0:
                    continue
                
                for point in spline.points:
                    point.select = True
                if negative:
                    points.append(point)
                bpy.ops.transform.tilt(value= tilt * -1 if negative else 1)
                for point in spline.points:
                    point.select = False
                    
            for point in points:
                point.select = True

            continue
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.convert(target='MESH')
            
            continue
            blendpath = str(pref.filepath) + str(Path('/hair/haircards/haircards_material.blend'))
            with bpy.data.libraries.load(blendpath, link = False) as (data_from ,data_to):
                data_to.materials = ['HG_Haircards'] 
            
            if hc_obj.data.materials:
                # assign to 1st material slot
                hc_obj.data.materials[0] = data_to.materials[0]
            else:
                # no slots
                hc_obj.data.materials.append(data_to.materials[0])

            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all()
            uv_islands = self.get_uv_islands2(hc_obj, steps)

            self.set_uvs(hc_obj, uv_islands)
            hc_obj.select_set(False)
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def get_uv_islands(self, context, haircard_obj):
        start_uv_sync_mode = context.scene.tool_settings.use_uv_select_sync
        
        bm = bmesh.from_edit_mesh(haircard_obj.data)
        bm.faces.ensure_lookup_table()
        uv_layer = bm.loops.layers.uv.active

        found_list = []
        all_islands = []

        for f in bm.faces:
            if f.index in found_list:
                continue
        
            bpy.ops.uv.select_all(action='DESELECT')
            for loop in f.loops:
                loop[uv_layer].select = True
            bpy.ops.uv.select_linked()

            island = [f.index for f in bm.faces if f.loops[0][uv_layer].select]
            
            found_list.extend(island)
            all_islands.append(island)
            if f.index > 10:
                break

        context.scene.tool_settings.use_uv_select_sync = start_uv_sync_mode
        return all_islands

    def get_uv_islands2(self, haircard_obj, steps):
        bm = bmesh.from_edit_mesh(haircard_obj.data)
        bm.faces.ensure_lookup_table()

        faces = [f.index for f in bm.faces]
        n = pow(2,steps)
        islands = [faces[i:i + n] for i in range(0, len(faces), n)]
        
        #for i in range(0, len(faces), pow(2,steps)):
        #    yield faces[i:i + n]

        return islands

    def set_uvs(self, hc_obj, islands):
        me = hc_obj.data
        uv_layer = me.uv_layers.active.data

        island = [me.polygons[i] for i in islands[0]]
        for poly in island:
            for loop_index in poly.loop_indices:
                uv_layer[loop_index].uv = (0,0)
            break


def build_hair_spline_distance_enum(hair_obj, body_obj) -> list:
    spline_distance_enum = []
    
    #RELEASE check if these vert numbers are still correct
    middle_vert_converted_loc = get_vert_loc_in_matrix_of_target_object(hair_obj, body_obj, 9663)
    right_vert_converted_loc = get_vert_loc_in_matrix_of_target_object(hair_obj, body_obj, 9669)
    left_vert_converted_loc = get_vert_loc_in_matrix_of_target_object(hair_obj, body_obj, 9660)
    
    splines = hair_obj.data.splines 
    for spline in splines:
        distance_list = []
        for point in spline.points:
            distance = find_distance_to_control_vert(point, middle_vert_converted_loc)
            distance_list.append(distance)
    
        assert distance_list
    
        closest_point_index = np.argmin(distance_list)
        closest_point = spline.points[closest_point_index]
        side_of_head = get_side_of_head(closest_point, right_vert_converted_loc, left_vert_converted_loc)

        positive_negative = -1 if side_of_head == 'right' else 1

        spline_distance_enum.append(distance_list[closest_point_index] * positive_negative)

    return spline_distance_enum

def get_vert_loc_in_matrix_of_target_object(target_object, object_of_passed_vert, index):
    control_vert = object_of_passed_vert.data.vertices[index]
    control_vert_local_loc = control_vert.co
    control_vert_global_loc = object_of_passed_vert.matrix_world @ control_vert_local_loc
    control_node_converted_loc = target_object.matrix_world.inverted() @ control_vert_global_loc
    return np.array(control_node_converted_loc)
        
    # verts_within_distance = []
    # for vert in hair_obj.data.vertices:
    #     loc = vert.co
    #     squared_dist = np.sum((loc-control_vert_loc)**2, axis=0)
    #     dist = np.sqrt(squared_dist)
        
    #     if dist < max_distance:
    #         verts_within_distance.append(vert)
    
def find_distance_to_control_vert(point, control_node_converted_loc):
    loc = np.array(point.co[:3])
    squared_dist = np.sum((loc-control_node_converted_loc)**2, axis=0)
    return np.sqrt(squared_dist)    

def get_side_of_head(point_on_spline, right_vert, left_vert):
    distance_right = find_distance_to_control_vert(point_on_spline, right_vert)
    distance_left = find_distance_to_control_vert(point_on_spline, left_vert)
    
    if distance_right > distance_left:
        return 'left'
    else:
        return 'right'
