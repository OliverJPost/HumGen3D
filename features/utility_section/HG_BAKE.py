#TODO document

'''
Texture baking operators
'''

import os
from pathlib import Path

import bpy  # type: ignore

from ...features.common.HG_COMMON_FUNC import (ShowMessageBox, find_human,
                                               get_prefs, hg_log,
                                               print_context)


def status_text_callback(header, context):  
    sett   = context.scene.HG3D
    layout = header.layout

    layout.separator_spacer()
    layout.alignment = 'EXPAND'
    
    row = layout.row(align=False)
    row.alignment = 'CENTER'
    
    layout.label(text=f'Rendering texture {sett.bake_idx}/{sett.bake_total}', icon='TIME')
    
    col         = layout.column()
    col.scale_x = 1.6
    col.prop(sett, "bake_progress")

    layout.label(text='Press ESC to cancel', icon='EVENT_ESC')
    
    layout.separator_spacer()
    

#TODO progress bar
class HG_BAKE(bpy.types.Operator):
    """Bake all textures
    """
    bl_idname      = "hg3d.bake"
    bl_label       = "Bake"
    bl_description = "Bake all textures"
    bl_options     = {"UNDO"}

    def __init__(self):
        self.timer = None
        self.bake_idx = 0
        self.image_dict = {}
        self.finish_modal = False
        
    def invoke(self, context, event):
        sett = context.scene.HG3D
        selected_humans = set([find_human(obj) for obj in context.selected_objects if find_human(obj)])
        self.bake_enum = generate_bake_enum(context, selected_humans)
        sett.bake_total = len(self.bake_enum)
        sett.bake_idx = 1
 
        cancelled, self.switched_to_cuda, self.old_samples, _ = check_bake_render_settings(
            context, samples = int(sett.bake_samples), force_cycles = False)

        if cancelled:
            return {'FINISHED'}

        wm = context.window_manager
        wm.modal_handler_add(self)

        self.timer = wm.event_timer_add(0.01, window=context.window)
        context.workspace.status_text_set(status_text_callback)
        
        return {'RUNNING_MODAL'}

    def modal(self, context, event):      
        sett = context.scene.HG3D      

        if self.finish_modal:
            context.area.tag_redraw()
            context.workspace.status_text_set(text=None)
            sett.bake_idx = 0
            
            if self.switched_to_cuda:
                context.preferences.addons['cycles'].preferences.compute_device_type = 'OPTIX'            
            
            context.scene.cycles.samples = self.old_samples
            
            return {'FINISHED'}
        
        elif event.type in ['ESC']:
            hg_log('Cancelling baking modal')
            
            self.finish_modal = True
            return {'RUNNING_MODAL'}
        
        elif event.type == 'TIMER':
            #Check if all textures in the list are already baked
            if self.bake_idx == sett.bake_total:   
                self.finish_modal = True
                return {'RUNNING_MODAL'}
            
            bake_enum_dict = self.bake_enum[self.bake_idx-1] 
            
            human_name, texture_name, bake_obj, mat_slot, tex_type = [v for _,v in bake_enum_dict.items()]
            hg_rig = bpy.data.objects.get(human_name)
            hg_log(f"Started baking object {bake_obj.name}, texture {texture_name}", level = 'DEBUG')

            bake_obj.select_set(True)
            context.view_layer.objects.active = bake_obj

            solidify_state = get_solidify_state(bake_obj, False) 
            current_mat = bake_obj.data.materials[mat_slot]
            
            img_name = f'{human_name}_{texture_name}_{tex_type}'
            
            if texture_name == 'body':
                resolution = int(sett.bake_res_body)
            elif texture_name == 'eyes':
                resolution = int(sett.bake_res_eyes)
            else:
                resolution = int(sett.bake_res_clothes)
                
            export_path = get_bake_export_path(sett, hg_rig.name)
            
            hg_rig.select_set(False)
            img = bake_texture(context, current_mat, tex_type, img_name, sett.bake_file_type, resolution, export_path)
            
            assert img
            
            self.image_dict[img] = tex_type

            #check if next texture belongs to another object
            last_texture = True if self.bake_enum[self.bake_idx]["texture_name"] != texture_name else False

            if last_texture:
                new_mat = material_setup(bake_obj, mat_slot)
                for img,tex_type in self.image_dict.items():
                    add_image_node(img, tex_type, new_mat)   
                self.image_dict.clear()
            
            get_solidify_state(bake_obj, solidify_state)
            hg_rig['hg_baked'] = 1

            
            self.bake_idx += 1
            sett.bake_idx += 1
            
            if self.bake_idx > 0:
                progress = self.bake_idx / (sett.bake_total)
                sett.bake_progress =  int(progress * 100)
            
            context.workspace.status_text_set(status_text_callback)
         
            return {'RUNNING_MODAL'}
        
        else:
            return {'RUNNING_MODAL'}

def check_bake_render_settings(context, samples = 4, force_cycles = False):
    switched_to_cuda = False
    switched_from_eevee = False
    if context.preferences.addons['cycles'].preferences.compute_device_type == 'OPTIX':
        switched_to_cuda = True
        context.preferences.addons['cycles'].preferences.compute_device_type = 'CUDA'
    if context.scene.render.engine != 'CYCLES':
        if force_cycles:
            switched_from_eevee = True
            context.scene.render.engine = 'CYCLES'
        else:       
            ShowMessageBox(message = 'You can only bake while in Cycles')
            return True, None, None, None             

    old_samples = context.scene.cycles.samples
    context.scene.cycles.samples = samples    

    return False, switched_to_cuda, old_samples, switched_from_eevee

def material_setup(obj, slot):
    org_name = obj.material_slots[slot].material.name
    mat = bpy.data.materials.new(f'{obj.name}_{org_name}_BAKED')    
    mat.use_nodes = True

    obj.material_slots[slot].material = mat

    return mat

def add_image_node(image, input_type, mat):
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

def get_solidify_state(obj, state):
    return_value = False
    for mod in [m for m in obj.modifiers if m.type == 'SOLIDIFY']:
        if any((mod.show_viewport, mod.show_render)):
            return_value = True
        
        mod.show_viewport = mod.show_render = state

    return return_value

def bake_texture(context, mat, bake_type, naming, image_ext, resolution, export_path):   
    pref  = get_prefs()
    sett  = context.scene.HG3D
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    #image_ext   = sett.bake_file_type

    image = bpy.data.images.new(naming + f'_{bake_type.lower()}', width=resolution, height=resolution)
    
    principled = [node for node in nodes if node.bl_idname == 'ShaderNodeBsdfPrincipled'][0]
    mat_output = [node for node in nodes if node.bl_idname == 'ShaderNodeOutputMaterial'][0]
    emit_node = nodes.new('ShaderNodeEmission')
    if bake_type == 'Normal':
        links.new(principled.outputs[0], mat_output.inputs[0])
    else:
        source_socket = follow_links(principled, bake_type)
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
    print_context(context)
    bpy.ops.object.bake(type= bake_type)#, pass_filter={'COLOR'}

    image.filepath_raw = export_path + str(Path(f'/{image.name}')) + f'.{image_ext}'
    image.file_format  = image_ext.upper()
    image.save()

    return image

def follow_links(target_node, target_socket):
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

def generate_bake_enum(context, selected_humans) -> list:
    bake_enum = []

    for human in selected_humans:
        for tex_type in ['Base Color', 'Specular', 'Roughness', 'Normal']:
            bake_enum.append({
                "human_name": human.name,
                "texture_name": "body",
                "object": human.HG.body_obj,
                "material_slot": 0,
                "tex_type": tex_type
            })
        
        hg_eyes =  next(child for child in human.children if 'hg_eyes' in child)
        bake_enum.append({
            "human_name": human.name,
            "texture_name": "eyes",
            "object": hg_eyes,
            "material_slot": 1,
            "tex_type": "Base Color"
        })

        cloth_objs = [child for child in human.children 
                    if 'cloth' in child
                    or 'shoe' in child]
        
        for cloth in cloth_objs:
            for tex_type in ['Base Color', 'Roughness', 'Normal']:
                bake_enum.append({
                    "human_name": human.name,
                    "texture_name": cloth.name,
                    "object": cloth,
                    "material_slot": 0,
                    "tex_type": tex_type
                })

    return bake_enum

def get_bake_export_path(sett, folder_name) -> str:
    if sett.bake_export_folder:
        export_path = sett.bake_export_folder + str(Path(f'/bake_results/{folder_name}'))
        if not os.path.exists(export_path):
                os.makedirs(export_path)
    else:
        export_path = get_prefs().filepath + str(Path(f'/bake_results/{folder_name}'))
        if not os.path.exists(export_path):
                os.makedirs(export_path)
                
    return export_path
