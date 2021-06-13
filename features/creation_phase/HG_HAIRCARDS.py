"""UNDER CONSTRUCTION"""

import bpy #type: ignore
import bmesh #type: ignore
from ... features.common.HG_COMMON_FUNC import find_human, get_prefs
from pathlib import Path

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
            if ps.name.startswith('Eye'):
                continue
            ps_sett = ps.settings
            p_amount = len(ps.particles)
            print(p_amount)
            ps_sett.child_nbr = 2
            if ps_sett.display_step == 3:
                ps_sett.display_step = 4
            steps = ps_sett.display_step

            for mod in [mod for mod in hg_body.modifiers if mod.type == 'PARTICLE_SYSTEM']:
                if mod.particle_system.name == ps.name:
                    bpy.ops.object.modifier_convert(modifier=mod.name)
                    print(f'converting {mod.name}, {context.object}')
                    hc_obj = context.object
            for obj in [obj for obj in context.selected_objects if obj != hc_obj]:
                obj.select_set(False)
 
            bpy.ops.object.convert(target='CURVE')
            hc_obj.data.extrude = 0.008 
            
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.transform.tilt(value=1.5708)
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.convert(target='MESH')
            
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
            print(uv_islands)
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
        print(f'uv_layer {uv_layer}')
        island = [me.polygons[i] for i in islands[0]]
        for poly in island:
            for loop_index in poly.loop_indices:
                uv_layer[loop_index].uv = (0,0)
            break