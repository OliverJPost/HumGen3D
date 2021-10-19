#TODO document

'''
Texture baking operators
'''

import os
from pathlib import Path

import bpy  # type: ignore

from ...features.common.HG_COMMON_FUNC import find_human, get_prefs


#TODO progress bar
class HG_BAKE(bpy.types.Operator):
    """Bake all textures
    """
    bl_idname      = "hg3d.bake"
    bl_label       = "Bake"
    bl_description = "Bake all textures"
    bl_options     = {"UNDO"}
    
    def execute(self, context):      
        sett = context.scene.HG3D

        switched_to_cuda = False
        if context.preferences.addons['cycles'].preferences.compute_device_type == 'OPTIX':
            switched_to_cuda = True
            context.preferences.addons['cycles'].preferences.compute_device_type = 'CUDA'
        if context.scene.render.engine != 'CYCLES':
            self.report({'WARNING'}, 'You can only bake while in Cycles')
            return {'FINISHED'}             
            
        hg_rig = find_human(context.object)
        for obj in context.selected_objects:
            obj.select_set(False)        

        bake_dict   = self.make_baking_dict(hg_rig)
        old_samples = context.scene.cycles.samples
        context.scene.cycles.samples = int(sett.bake_samples)

        for naming, data in bake_dict.items():
            obj = data['obj']
            obj.select_set(True)
            context.view_layer.objects.active = obj

            slot           = data['slot']
            tex_types      = data['tex_types']
            solidify_state = self.solidify_state(obj, False)

            #update big slider
            print('baking', obj.name)
            
            image_dict = {}
            current_mat = obj.material_slots[slot].material
            for tex_type in tex_types:
                #update small slider
                print('baking texture ', tex_type)

                img_name = f'{hg_rig.name}_{naming}_{tex_type}'
                img = self.bake_texture(context, current_mat, tex_type, img_name, naming, obj)
                if not img:
                    continue
                image_dict[img] = tex_type
                
            new_mat = self.material_setup(obj, slot)
            for img,tex_type in image_dict.items():
                self.add_image_node(img, tex_type, new_mat)   
            
            self.solidify_state(obj, solidify_state)
            hg_rig['hg_baked'] = 1
            obj.select_set(False)

        context.scene.cycles.samples = old_samples
        if switched_to_cuda:
            context.preferences.addons['cycles'].preferences.compute_device_type = 'OPTIX'
        
        return {'FINISHED'} 

    def make_baking_dict(self, hg_rig):
        bake_dict = {
            'human': {
                'obj'      : hg_rig.HG.body_obj,
                'slot'     : 0,
                'tex_types': ['Base Color', 'Specular', 'Roughness', 'Normal'],
                },
            'eyes': {
                'obj'      : next(child for child in hg_rig.children if 'hg_eyes' in child),
                'slot'     : 1,
                'tex_types': ['Base Color'],
                },
        }


        cloth_objs = [child for child in hg_rig.children 
                      if 'cloth' in child
                      or 'shoe' in child]
        
        for cloth in cloth_objs:
            bake_dict[cloth.name] = {
                'obj'      : cloth,
                'slot'     : 0,
                'tex_types': ['Base Color', 'Roughness', 'Normal'],
                }
        
        return bake_dict
    
    def bake_texture(self, context, mat, bake_type, naming, obj_type, hg_rig):   
        pref  = get_prefs()
        sett  = context.scene.HG3D
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        ext   = sett.bake_file_type

        if obj_type == 'human':
            res = int(sett.bake_res_body)
        elif obj_type == 'eyes':
            res = int(sett.bake_res_eyes)
        else:
            res = int(sett.bake_res_clothes)

        image = bpy.data.images.new(naming + f'_{bake_type.lower()}', width=res, height=res)
        
        principled = [node for node in nodes if node.bl_idname == 'ShaderNodeBsdfPrincipled'][0]
        mat_output = [node for node in nodes if node.bl_idname == 'ShaderNodeOutputMaterial'][0]
        emit_node = nodes.new('ShaderNodeEmission')
        if bake_type == 'Normal':
            links.new(principled.outputs[0], mat_output.inputs[0])
        else:
            source_socket = self.follow_links(principled, bake_type)
            if not source_socket:
                return None
            links.new(source_socket, emit_node.inputs[0])
            links.new(emit_node.outputs[0], mat_output.inputs[0])

        node       = nodes.new('ShaderNodeTexImage')
        node.image = image
        for node2 in nodes: 
            node2.select = False
        node.select  = True
        nodes.active = node

        bake_type = 'NORMAL' if bake_type == 'Normal' else 'EMIT'
        bpy.ops.object.bake(type= bake_type)#, pass_filter={'COLOR'}
        
        folder_name = hg_rig.name# + str(datetime.datetime.now())
        if sett.bake_export_folder:
            filepath = sett.bake_export_folder + str(Path(f'/bake_results/{folder_name}'))
            if not os.path.exists(filepath):
                 os.makedirs(filepath)
        else:
            filepath = pref.filepath + str(Path(f'/bake_results/{folder_name}'))
            if not os.path.exists(filepath):
                 os.makedirs(filepath)
        image.filepath_raw = filepath + str(Path(f'/{image.name}')) + f'.{ext}'
        image.file_format  = ext.upper()
        image.save()

        return image
    
    def material_setup(self, obj, slot):
        org_name = obj.material_slots[slot].material.name
        mat = bpy.data.materials.new(f'{obj.name}_{org_name}_BAKED')    
        mat.use_nodes = True

        obj.material_slots[slot].material = mat

        return mat

    def add_image_node(self, image, input_type, mat):
        nodes      = mat.node_tree.nodes
        links      = mat.node_tree.links
        principled = nodes['Principled BSDF']

        img_node       = nodes.new('ShaderNodeTexImage')
        img_node.image = image
        img_node.name  = input_type
        
        node_locs = {
            'Base Color': (-600, 400),
            'Normal': (-600, -200),
            'Roughness': (-600, 100),
            'Metallic': (-1000, 300),
            'Specular': (-1000, -100)
        }
        img_node.location = node_locs[input_type]

        if input_type in ['Normal']:
            image.colorspace_settings.name = 'Non-Color'
            normal_node                    = nodes.new('ShaderNodeNormalMap')
            normal_node.location           = (-300, -200)
            links.new(img_node.outputs[0], normal_node.inputs[1])
            links.new(normal_node.outputs[0], principled.inputs[input_type])
        else:
            links.new(img_node.outputs[0], principled.inputs[input_type])

        return img_node

    def follow_links(self, target_node, target_socket):
        """
        finds out what node is connected to a certain socket
        """    

        try:
            source_socket = next(node_links.from_socket 
                                 for node_links 
                                 in target_node.inputs[target_socket].links)
        except:
            source_socket = None

        return source_socket

    def solidify_state(self, obj, state):
        return_value = False
        for mod in [m for m in obj.modifiers if m.type == 'SOLIDIFY']:
            if any((mod.show_viewport, mod.show_render)):
                return_value = True
            
            mod.show_viewport = mod.show_render = state

        return return_value
