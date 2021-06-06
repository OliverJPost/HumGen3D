"""
Operators and functions for experimental features and QoL automations
"""

from . HG_CLOTHING import set_cloth_corrective_drivers
from . HG_INFO_POPUPS import HG_OT_INFO
from . HG_LENGTH import apply_armature
import re
from . HG_DEVTOOLS import HG_SHAPEKEY_CALCULATOR
import json
import time
from pathlib import Path
import pathlib
import platform
import subprocess
from . HG_NEXTPHASE import corrective_shapekey_copy, reapply_shapekeys
import bpy #type: ignore
import os
from . HG_COMMON_FUNC import ShowMessageBox, apply_shapekeys, find_human, get_prefs
from . HG_UTILITY_FUNC import build_object_list, refresh_outfit_ul, refresh_shapekeys_ul, refresh_modapply, refresh_hair_ul

class Utility_tools:
    def show_message(self, msg):
        print(msg)
        self.report({'WARNING'}, msg)
        ShowMessageBox(message = msg)

    def overwrite_warning(self):
        layout = self.layout
        col = layout.column(align = True)
        col.label(text = f'"{self.name}" already exists in:')
        col.label(text = self.folder)
        col.separator()
        col.label(text = 'Overwrite?')

    def save_thumb(self, folder, current_name, save_name):
        img = bpy.data.images[current_name]
        if current_name != 'Render Result':    
            try:
                img.filepath_raw = str(Path(f'{folder}/{save_name}.jpg'))
                img.file_format = 'JPEG'
                img.save()
            except RuntimeError as e:
                self.show_message("Thumbnail image doesn't have any image data")
                print(e)
        else:
            try:
                img.save_render(str(Path(f'{self.folder}/{self.name}.jpg')))
            except RuntimeError:
                self.show_message("[Cancelled] Saving render as thumbnail, but render is empty")

    def save_objects_optimized(self, context, objs, folder, filename, clear_sk = True, clear_materials = True, clear_vg = True, clear_ps = True, run_in_background = True):
        for obj in objs:
            if clear_materials:
                obj.data.materials.clear()
            if clear_vg:
                obj.vertex_groups.clear()  
            if clear_sk:
                for sk in [sk for sk in obj.data.shape_keys.key_blocks if sk.name != 'Basis']:
                    obj.shape_key_remove(sk)
                if obj.data.shape_keys:
                    obj.shape_key_remove(obj.data.shape_keys.key_blocks['Basis'])
            if clear_ps:
                context.view_layer.objects.active= obj
                for i, ps in enumerate(obj.particle_systems):   
                    obj.particle_systems.active_index = i
                    bpy.ops.object.particle_system_remove()

        new_scene = bpy.data.scenes.new(name='test_scene')
        new_col = bpy.data.collections.new(name='HG')
        new_scene.collection.children.link(new_col)
        for obj in objs:
            new_col.objects.link(obj)    

        if not os.path.exists(folder):
            os.makedirs(folder)  

        blend_filepath = os.path.join(folder, f'{filename}.blend')
        bpy.data.libraries.write(blend_filepath, {new_scene})
        
        python_file = os.path.join(Path(__file__).parent.absolute(), 'hg_purge.py')
        if run_in_background:
            subprocess.Popen([bpy.app.binary_path, blend_filepath, "--background", "--python", python_file])
        else:
            subprocess.Popen([bpy.app.binary_path, blend_filepath, "--python", python_file])
            
        bpy.data.scenes.remove(new_scene)
        for obj in objs:
            bpy.data.objects.remove(obj)
        
    def remove_number_suffix(self, name):
        re_suffix = re.search(r'.\d\d\d', name)
        if not re_suffix or not name.endswith(re_suffix.group(0)):
            return name
        else:
            return name.replace(re_suffix.group(0), '')

class HG_MAKE_EXPERIMENTAL(bpy.types.Operator, Utility_tools):
    """
    Makes human experimental, loosening limits on shapekeys and sliders
    """
    bl_idname = "hg3d.experimental"
    bl_label = "Make human experimental"
    bl_description = "Makes human experimental, loosening limits on shapekeys and sliders"
    bl_options = {"UNDO"}

    def execute(self,context):        
        hg_rig = find_human(context.active_object)
        HG = hg_rig.HG
        hg_body = hg_rig.HG.body_obj

        is_experimental = HG.experimental

        s_max = 1 if is_experimental else 2
        s_min_ff = -1 if is_experimental else -2
        s_min_bd = 0 if is_experimental else -.5

        for sk in hg_body.data.shape_keys.key_blocks: 
            if sk.name.startswith('ff_'):
                sk.slider_min = s_min_ff
                sk.slider_max = s_max
            elif sk.name.startswith('bp_'):
                sk.slider_min = s_min_bd
                sk.slider_max = s_max              
            elif sk.name.startswith('pr_'):
                sk.slider_min = s_min_bd
                sk.slider_max = s_max 
                                
        HG.experimental = False if is_experimental else True
        if not is_experimental:
            HG_OT_INFO.ShowMessageBox(None, 'experimental')
        return {'FINISHED'}

class HG_OT_MODAPPLY(bpy.types.Operator, Utility_tools):
    bl_idname = "hg3d.modapply"
    bl_label = "Apply selected modifiers"
    bl_description = "Apply selected modifiers"
    bl_options = {"UNDO"}

    def execute(self,context):        
        sett = context.scene.HG3D
        col = context.scene.modapply_col

        objs = build_object_list(context, sett)
        print('objs1', objs)

        sk_dict = {}
        driver_dict = {}

        for obj in objs:
            if sett.modapply_keep_shapekeys:
                sk_dict, driver_dict = self.copy_shapekeys(context, col, sk_dict, driver_dict, obj)
            apply_shapekeys(obj)
        
        objs_to_apply = objs.copy()
        for sk_list in sk_dict.values():
            if sk_list:
                print('extending with', sk_list)
                objs_to_apply.extend(sk_list)

        self.apply_modifiers(context, sett, col, sk_dict, objs_to_apply)

        for obj in context.selected_objects:
            obj.select_set(False)

        if sett.modapply_keep_shapekeys:
            self.add_shapekeys_again(context, objs, sk_dict, driver_dict)

        refresh_modapply(self, context)
        return {'FINISHED'}

    def copy_shapekeys(self, context, col, sk_dict, driver_dict, obj):
        apply = False
        for item in col:
            if item.mod_type == 'ARMATURE' and (item.count or item.object == obj) and item.enabled:
                apply = True
        sk_dict[obj.name], driver_dict[obj.name] = corrective_shapekey_copy(context, obj, apply_armature = apply)
        return sk_dict, driver_dict

    def apply_modifiers(self, context, sett, col, sk_dict, objs_to_apply):
        if sett.modapply_search_modifiers == 'summary':
            mod_types = [item.mod_type for item in col if item.enabled and item.mod_name != 'HEADER']
            for obj in objs_to_apply:
                for mod in reversed(obj.modifiers):
                    if mod.type in mod_types:
                        self.apply(context, sett, mod, obj)
        else:
            for item in [item for item in col if item.enabled]:
                try:
                    obj = item.object
                    mod = obj.modifiers[item.mod_name]
                    self.apply(context, sett, mod, obj)
                    if sett.modapply_keep_shapekeys:
                        for obj in sk_dict[obj.name]:
                            self.apply(context, sett, mod, obj)
                except Exception as e: 
                    print(f'Error while applying modifier {item.mod_name} on {item.object}, with error as {e}')

    def add_shapekeys_again(self, context, objs, sk_dict, driver_dict):
        for obj in objs:
            if not sk_dict[obj.name]: 
                continue
            context.view_layer.objects.active = obj
            obj.select_set(True)
            reapply_shapekeys(context, sk_dict[obj.name], obj, driver_dict[obj.name])
            obj.select_set(False)

    def apply(self, context, sett, mod, obj):
        apply = False if sett.modapply_apply_hidden and not all((mod.show_viewport, mod.show_render)) else True
        if apply:
            context.view_layer.objects.active = obj
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except Exception as e: 
                print(f'Error while applying modifier {mod.name} on {obj.name}, with error as {e}')

class HG_OT_REFRESH_UL(bpy.types.Operator):
    bl_idname = "hg3d.ulrefresh"
    bl_label = "Refresh list"
    bl_description = "Refresh list"

    type: bpy.props.StringProperty()

    def execute(self,context):        
        if self.type == 'modapply':
            refresh_modapply(self, context)
        elif self.type == 'shapekeys':
            refresh_shapekeys_ul(self, context)
        elif self.type == 'hair':
            refresh_hair_ul(self, context)
        elif self.type == 'outfit':
            refresh_outfit_ul(self, context)
        return {'FINISHED'}

class HG_OT_SELECTMODAPPLY(bpy.types.Operator):
    bl_idname = "hg3d.selectmodapply"
    bl_label = "Select all/none modifiers"
    bl_description = "Select all/none modifiers"
    bl_options = {"UNDO"}

    all: bpy.props.BoolProperty()

    def execute(self,context):        
        col = context.scene.modapply_col

        refresh_modapply(self, context)

        for item in col:
            item.enabled = self.all

        return {'FINISHED'}

class HG_OT_OPEN_FOLDER(bpy.types.Operator):
    bl_idname = "hg3d.openfolder"
    bl_label = "Open folder"
    bl_description = "Opens the folder that belongs to this type of content"

    subpath: bpy.props.StringProperty()

    def execute(self,context):        
        pref = context.preferences.addons[__package__].preferences
        path = pref.filepath + str(Path(self.subpath))

        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

        return {'FINISHED'}

class HG_OT_SAVE_SHAPEKEY(bpy.types.Operator, Utility_tools):
    bl_idname = "hg3d.saveshapekey"
    bl_label = "Save shapekeys"
    bl_description = "Save shapekeys"

    name: bpy.props.StringProperty()

    def execute(self,context):        
        hg_rig = find_human(context.object)

        data = [item.sk_name for item in self.collection if item.enabled]
   
        sk_obj = hg_rig.HG.body_obj.copy()
        sk_obj.data = sk_obj.data.copy()
        sk_obj.name = 'hg_shapekey'
        context.collection.objects.link(sk_obj)
        
        for sk in [sk for sk in sk_obj.data.shape_keys.key_blocks if sk.name not in data and sk.name != 'Basis']:
            sk_obj.shape_key_remove(sk)
    
        with open((os.path.join(self.folder, f'{self.name}.json')), 'w') as f:
            json.dump(data, f, indent = 4)
        
        self.save_objects_optimized(context, sk_obj, self.folder, self.name, clear_sk = False)

        msg = f'Saved {len(data)} shapekeys to {self.folder}'
        self.report({'INFO'}, msg)
        ShowMessageBox(message = msg)
        return {'FINISHED'}

    def draw(self, context):
        self.overwrite_warning()

    def invoke(self, context, event):
        pref = context.preferences.addons[__package__].preferences
        self.sett = context.scene.HG3D
        self.collection = context.scene.shapekeys_col

        has_selected = next((True for item in self.collection if item.enabled), False)
        if not has_selected:
            self.show_message('No shapekeys selected')
            return {'CANCELLED'}

        if not self.sett.shapekey_col_name:
            self.show_message('No name given for collection file')
            return {'CANCELLED'}

        self.folder = pref.filepath + str(Path('/models/shapekeys/'))
        self.name = self.sett.shapekey_col_name
        if os.path.isfile(str(Path(f'{self.folder}/{self.name}.blend'))):
            return context.window_manager.invoke_props_dialog(self)

        return self.execute(context)

class HG_OT_SAVEPRESET(bpy.types.Operator, Utility_tools):
    bl_idname = "hg3d.savepreset"
    bl_label = "Save as starting human"
    bl_description = "Save as starting human"

    name: bpy.props.StringProperty()

    def execute(self,context):        
        hg_rig = self.hg_rig
        folder = self.folder

        hg_body = hg_rig.HG.body_obj
        hg_eyes = [obj for obj in hg_rig.children if 'hg_eyes' in obj]
        
        self.save_thumb(self.folder, self.thumb, self.name)

        preset_data = {}
        preset_data['gender'] = hg_rig.HG.gender
        preset_data['experimental'] = True if hg_rig.HG.experimental else False
        eyebrows = [mod for mod in hg_body.modifiers if mod.type == 'PARTICLE_SYSTEM' and mod.particle_system.name.startswith('Eyebrows')]
        preset_data['eyebrows'] = next((mod.particle_system.name for mod in eyebrows if (mod.show_viewport or mod.show_render)), f'Eyebrows_{hg_rig.HG.gender.capitalize()}')
        preset_data = self.add_body_proportions(preset_data, hg_rig)
        preset_data = self.add_shapekeys(preset_data, hg_body)
        preset_data = self.add_material_data(preset_data, hg_body, hg_eyes)
        
        with open(str(Path(f'{folder}/{self.name}.json')), 'w') as f:
            json.dump(preset_data, f, indent = 4)
        
        self.report({'INFO'}, f'Saved starting human {self.name} to {folder}')
        ShowMessageBox(message = f'Saved starting human {self.name} to {folder}')        
        return {'FINISHED'}

    def draw(self, context):
        self.overwrite_warning()

    def invoke(self, context, event):
        pref = context.preferences.addons[__package__].preferences
        self.sett = context.scene.HG3D
        self.hg_rig = find_human(context.object)

        self.thumb = self.sett.preset_thumbnail_enum
        if not self.thumb:
            self.show_message('No thumbnail selected')
            return {'CANCELLED'}
        if not self.sett.preset_name:
            self.show_message('No name given for starting human')
            return {'CANCELLED'}

        self.folder = pref.filepath + str(Path(f'/models/{self.hg_rig.HG.gender}/'))
        self.name = self.sett.preset_name
        if os.path.isfile(str(Path(f'{self.folder}/{self.name}.json'))):
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)

    def add_body_proportions(self, preset_data, hg_rig):
        bp_dict = {}
        bp_dict['length'] = hg_rig.dimensions[2]
        
        size = hg_rig.pose.bones['breast.L'].scale[0]
        bp_dict['chest'] = 3*size -2.5
  
        preset_data['body_proportions'] = bp_dict

        return preset_data

    def add_shapekeys(self, preset_data, hg_body):
        sks = hg_body.data.shape_keys.key_blocks
        sk_dict = {sk.name:sk.value for sk in sks if sk.value != 0 and not sk.name.startswith(('expr', 'cor', 'Basis'))}
        preset_data['shapekeys'] = sk_dict
        return preset_data

    def add_material_data(self, preset_data, hg_body, hg_eyes):
        mat_dict = {}
        mat = hg_body.data.materials[0]
        nodes = mat.node_tree.nodes
        
        mat_dict['texture_library'] = mat['texture_library'] if getattr(mat, "texture_library", None) else 'Default 4K' #CHECK if this fixes it
        img_name = nodes['Color'].image.name
        if img_name[-1].isdigit(): #check if ends with duplicate numbers
            img_name = img_name[:-4]
        mat_dict['diffuse'] = img_name
        nodegroup_dict = {}
        for node in [node for node in nodes if node.bl_idname == 'ShaderNodeGroup']:
            input_dict = {}
            for input in [inp for inp in node.inputs if not inp.links]:
                print(input.name, str(type(input.default_value)))
                input_dict[input.name] = tuple(input.default_value) if str(type(input.default_value)) == "<class 'bpy_prop_array'>" else input.default_value
                
            print(node.name, input_dict)    
            nodegroup_dict[node.name] = input_dict
        
        for nodename, input_name in {'Bump': 'Strength', 'Normal Map': 'Strength', 'Darken_hsv': 'Value', 'Lighten_hsv': 'Value'}.items():
            nodegroup_dict[nodename] = {input_name: nodes[nodename].inputs[input_name].default_value,}
        
        mat_dict['node_inputs'] = nodegroup_dict

        eye_mat = hg_eyes[0].data.materials[1]
        eye_nodes = eye_mat.node_tree.nodes
        mat_dict['eyes'] = {'HG_Eye_Color': tuple(eye_nodes['HG_Eye_Color'].inputs[2].default_value), 'HG_Scelera_Color': tuple(eye_nodes['HG_Scelera_Color'].inputs[2].default_value)}

        preset_data['material'] = mat_dict

        return preset_data

class HG_OT_SAVEHAIR(bpy.types.Operator, Utility_tools):
    bl_idname = "hg3d.savehair"
    bl_label = "Save as starting human"
    bl_description = "Save as starting human"

    name: bpy.props.StringProperty()

    def execute(self,context):        
        sett = self.sett
        pref = context.preferences.addons[__package__].preferences

        hg_rig = self.hg_rig
        hg_body = hg_rig.HG.body_obj
        col = context.scene.savehair_col

        hair_obj = hg_body.copy()
        hair_obj.data = hair_obj.data.copy()
        hair_obj.name = 'HG_Body'
        context.collection.objects.link(hair_obj)

        context.view_layer.objects.active = hair_obj
        hair_obj.select_set(True)
        self.remove_other_systems(hair_obj, [item.ps_name for item in col if item.enabled])

        keep_vgs = self.find_vgs_used_by_hair(hair_obj)
        for vg in [vg for vg in hair_obj.vertex_groups if vg.name not in keep_vgs]:
                hair_obj.vertex_groups.remove(vg)

        for gender in [gd for gd, enabled in {'male': sett.savehair_male, 'female': sett.savehair_female }.items() if enabled]:
            hair_type = sett.save_hairtype
            if hair_type == 'face_hair' and gender == 'female':
                continue

            folder = pref.filepath + str(Path('hair/{}/{}Custom/'.format(hair_type, f'{gender}/' if hair_type == 'head' else '')))  
            if not os.path.exists(folder):
                os.makedirs(folder)     
            self.save_thumb(folder, self.thumb, self.name)  
            self.make_hair_json(context, hair_obj, folder, self.name)
            
        self.save_objects_optimized(context, hair_obj, self.folder, self.name, clear_ps = False, clear_vg = False) 
        
        context.view_layer.objects.active= hg_rig
        msg = f'Saved {self.name} to {self.folder}'
        self.report({'INFO'}, msg)
        ShowMessageBox(message = msg)
        return {'FINISHED'}

    def find_vgs_used_by_hair(self, hair_obj):
        all_vgs = [vg.name for vg in hair_obj.vertex_groups]
        keep_vgs = []
        for ps in [ps for ps in hair_obj.particle_systems]:
            vg_types = [
                ps.vertex_group_clump,
                ps.vertex_group_density,
                ps.vertex_group_field,
                ps.vertex_group_kink,
                ps.vertex_group_length,
                ps.vertex_group_rotation,
                ps.vertex_group_roughness_1,
                ps.vertex_group_roughness_2,
                ps.vertex_group_roughness_end,
                ps.vertex_group_size,
                ps.vertex_group_tangent,
                ps.vertex_group_twist,
                ps.vertex_group_velocity
                ]
            for used_vg in vg_types:
                if used_vg in all_vgs:
                    keep_vgs.append(used_vg)
        return keep_vgs

    def draw(self, context):
        self.overwrite_warning()

    def invoke(self, context, event):
        pref = context.preferences.addons[__package__].preferences
        self.sett = context.scene.HG3D
        self.hg_rig = find_human(context.object)

        self.thumb = self.sett.preset_thumbnail_enum
        if not self.thumb:
            self.show_message('No thumbnail selected')
            return {'CANCELLED'}
        if not (self.sett.savehair_male or self.sett.savehair_female):
            self.show_message('Select at least one gender')
            return {'CANCELLED'}
        if not self.sett.hairstyle_name:
            self.show_message('No name given for hairstyle')
            return {'CANCELLED'}

        self.folder = pref.filepath + str(Path(f'/hair/{self.sett.save_hairtype}/'))
        self.name = self.sett.hairstyle_name
        if os.path.isfile(str(Path(f'{self.folder}/{self.name}.blend'))):
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)

    def remove_other_systems(self, obj, keep_list):
        remove_list = [ps.name for ps in obj.particle_systems if ps.name not in keep_list]
           
        for ps_name in remove_list:    
            ps_idx = [i for i, ps in enumerate(obj.particle_systems) if ps.name == ps_name]
            obj.particle_systems.active_index = ps_idx[0]
            bpy.ops.object.particle_system_remove()

    def make_hair_json(self, context, hair_obj, folder, style_name):
        ps_dict = {}
        for mod in hair_obj.modifiers:
            if mod.type == 'PARTICLE_SYSTEM':
                ps = mod.particle_system
                ps_length = ps.settings.child_length
                ps_children = ps.settings.child_nbr
                ps_steps = ps.settings.display_step
                ps_dict[ps.name]= {"length": ps_length, "children_amount": ps_children, "path_steps": ps_steps}

        json_data = {"blend_file": f'{style_name}.blend', "hair_systems": ps_dict}

        full_path = os.path.join(folder, f'{style_name}.json')
        with open(full_path, 'w') as f:
            json.dump(json_data, f, indent = 4)
            print('dumped data to', full_path)

#FIXME male to female not working, other way?
#FIXME texture saving
#FIXME shoes corrective shapekeys
class HG_OT_SAVEOUTFIT(bpy.types.Operator, Utility_tools):
    bl_idname = "hg3d.saveoutfit"
    bl_label = "Save as outfit"
    bl_description = "Save as outfit"
    bl_options = {"UNDO"}

    name: bpy.props.StringProperty()
    alert: bpy.props.StringProperty()

    def execute(self,context):        
        sett = self.sett
        pref = context.preferences.addons[__package__].preferences
        col = self.col
        objs = [bpy.data.objects[item.obj_name] for item in col]
                  
        genders = []
        if sett.saveoutfit_female:
            genders.append('female')
        if sett.saveoutfit_male:
            genders.append('male')

        for gender in genders:
            gender_folder = self.folder + str(Path(f'/{gender}/Custom'))
            self.save_thumb(gender_folder, self.thumb, self.name)
        
        body_copy = self.hg_rig.HG.body_obj.copy()
        body_copy.data = body_copy.data.copy()
        context.collection.objects.link(body_copy)
        apply_shapekeys(body_copy)
        apply_armature(self.hg_rig, body_copy)
        
        self.save_material_textures(objs)
        obj_distance_dict = {}
        for obj in objs:
            distance_dict = HG_SHAPEKEY_CALCULATOR.build_distance_dict(self, body_copy, obj, apply = False) 
            obj_distance_dict[obj.name] = distance_dict
        
 
        for gender in genders:
            export_list = []
            backup_human = next((obj for obj in self.hg_rig.HG.backup.children if 'hg_body' in obj))
            if gender == 'male':
                backup_human = backup_human.copy()
                backup_human.data = backup_human.data.copy()
                context.collection.objects.link(backup_human)
                sks = backup_human.data.shape_keys.key_blocks
                for sk in sks:
                    sk.value = 0
                sks['Male'].mute = False
                sks['Male'].value = 1
                apply_shapekeys(backup_human)
            backup_human.hide_viewport = False
            
            for obj in objs:           
                obj_copy = obj.copy()
                obj_copy.data = obj_copy.data.copy()
                if 'cloth' in obj_copy:
                    del obj_copy['cloth']
                context.collection.objects.link(obj_copy)
                distance_dict = obj_distance_dict[obj.name]
                HG_SHAPEKEY_CALCULATOR.deform_obj_from_difference(self, '', distance_dict, backup_human, obj_copy, as_shapekey= False)
                export_list.append(obj_copy)
            
            if gender == 'male':
                bpy.data.objects.remove(backup_human)    
                
            gender_folder = self.folder + str(Path(f'/{gender}/Custom'))
            self.save_objects_optimized(context, export_list, gender_folder, self.name, clear_sk = False, clear_materials= False, clear_vg= False, run_in_background= not sett.open_exported_outfits)
        bpy.data.objects.remove(body_copy)

        self.show_message('Succesfully exported outfits')
        return {'FINISHED'}

    def draw(self, context):
        self.overwrite_warning()

    def invoke(self, context, event):
        self.pref = context.preferences.addons[__package__].preferences
        self.sett = context.scene.HG3D
        self.hg_rig = find_human(self.sett.saveoutfit_human)
        self.col = context.scene.saveoutfit_col

        self.thumb = self.sett.preset_thumbnail_enum
        if not self.thumb:
            self.show_message('No thumbnail selected')
            return {'CANCELLED'}    
        if not self.hg_rig:
            self.show_message('No human selected as reference')
            return {'CANCELLED'}
        if not (self.sett.savehair_male or self.sett.savehair_female):
            self.show_message('Select at least one gender')
            return {'CANCELLED'}
        if not self.sett.saveoutfit_name:
            self.show_message('No name given for outfit')
            return {'CANCELLED'}
        if len(self.col) == 0:
            self.show_message('No objects in list')
            return {'CANCELLED'}
        obj_list_without_suffix = [self.remove_number_suffix(item.obj_name) for item in self.col]
        if len(obj_list_without_suffix) != len(set(obj_list_without_suffix)):
            self.show_message('There are objects in the list which have the same names if suffix like .001 is removed')
            return {'CANCELLED'}            

        self.folder = os.path.join(self.pref.filepath, self.sett.saveoutfit_categ)
        self.name = self.sett.saveoutfit_name
        if os.path.isfile(str(Path(f'{self.folder}/{self.hg_rig.HG.gender}/Custom/{self.name}.blend'))):
            self.alert = 'overwrite'
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)

    #CHECK naming adds .004 to file names, creating duplicates
    def save_material_textures(self, objs):
        saved_images = {}

        for obj in objs:
            for mat in obj.data.materials:
                nodes= mat.node_tree.nodes
                for img_node in [n for n in nodes if n.bl_idname == 'ShaderNodeTexImage']:
                    img = img_node.image
                    colorspace = img.colorspace_settings.name 
                    if not img:
                        continue
                    img_path, saved_images = self.save_img(img, saved_images)
                    if img_path:
                        new_img = bpy.data.images.load(img_path)
                        img_node.image = new_img
                        new_img.colorspace_settings.name = colorspace
    
    def save_img(self, img, saved_images):
        img_name = self.remove_number_suffix(img.name)
        print('img_name', img_name)
        if img_name in saved_images:
            return saved_images[img_name], saved_images
        
        path = self.pref.filepath + str(Path(f'{self.sett.saveoutfit_categ}/textures/'))
        if not os.path.exists(path):
            os.makedirs(path)  

        full_path = os.path.join(path, img_name)
        img.filepath_raw = full_path
        try:
            img.save()
            saved_images[img_name] = full_path
        except RuntimeError as e:
            print(f'failed to save {img.name} with error {e}')
            return None, saved_images
            
        return full_path, saved_images
        
class MESH_TO_CLOTH_TOOLS(Utility_tools):
    def invoke(self, context, event):
        self.sett= context.scene.HG3D
        self.hg_rig = self.sett.mtc_armature
        
        if not self.hg_rig:
            self.show_message('No armature selected in the field above')
            return {'CANCELLED'}
        return self.execute(context)
            
#TODO make compatible with non-standard poses
class HG_OT_AUTOWEIGHT(bpy.types.Operator, MESH_TO_CLOTH_TOOLS):
    bl_idname = "hg3d.autoweight"
    bl_label = "Auto weight paint"
    bl_description = "Automatic weight painting"
    bl_options = {"UNDO"}

    def execute(self,context):     
        cloth_obj = context.object
        for obj in context.selected_objects:
            if obj != cloth_obj:
                obj.select_set(False)
        
        for mod in self.hg_rig.HG.body_obj.modifiers:
            if mod.type == 'MASK':
                mod.show_viewport = False
                mod.show_render = False
        
        if self.sett.mtc_add_armature_mod:
            armature = next((mod for mod in cloth_obj.modifiers if mod.type == 'ARMATURE'), None) 
            if not armature:
                cloth_obj.modifiers.new(name = 'Cloth Armature', type = 'ARMATURE')
            armature.object = self.hg_rig
            if (2, 90, 0) > bpy.app.version: #use old method for versions older than 2.90
                while cloth_obj.modifiers.find(armature.name) != 0:
                    bpy.ops.object.modifier_move_up({'object': cloth_obj}, modifier=armature.name)
            else:
                bpy.ops.object.modifier_move_to_index(modifier=armature.name, index=0)

        if self.sett.mtc_parent:
            cloth_obj.parent = self.hg_rig

        context.view_layer.objects.active = self.hg_rig.HG.body_obj
        self.hg_rig.select_set(True)
            
        bpy.ops.object.data_transfer(data_type='VGROUP_WEIGHTS', vert_mapping='NEAREST', layers_select_src='ALL', layers_select_dst='NAME', mix_mode='REPLACE')
        bpy.ops.object.data_transfer(layers_select_src='ACTIVE', layers_select_dst='ACTIVE', mix_mode='REPLACE', mix_factor=1.0)
        bone_names = [b.name for b in self.hg_rig.pose.bones]
        for vg in [vg for vg in cloth_obj.vertex_groups if vg.name not in bone_names and not vg.name.startswith('mask')]:
            cloth_obj.vertex_groups.remove(vg)
        
        self.hg_rig.select_set(False)
        context.view_layer.objects.active = cloth_obj

        for mod in self.hg_rig.HG.body_obj.modifiers:
            if mod.type == 'MASK':
                mod.show_viewport = True
                mod.show_render = True

        return {'FINISHED'}

class HG_OT_ADDCORRECTIVE(bpy.types.Operator, Utility_tools):
    bl_idname = "hg3d.addcorrective"
    bl_label = "Add corrective shapekeys"
    bl_description = "Automatic weight painting"
    bl_options = {"UNDO"}

    def execute(self,context):   
        self.sett = context.scene.HG3D
        hg_rig = self.sett.mtc_armature
        sett = self.sett
        cloth_obj = context.object
        
        body_copy = hg_rig.HG.body_obj.copy()
        body_copy.data = body_copy.data.copy()
        context.collection.objects.link(body_copy)
        
        if not context.object or context.object.type != 'MESH':
            self.show_message('Active object is not a mesh')
            return {'FINISHED'}
        
        remove_list = [driver for driver in body_copy.data.shape_keys.animation_data.drivers]
        for driver in remove_list:
            body_copy.data.shape_keys.animation_data.drivers.remove(driver)
        
        distance_dict = HG_SHAPEKEY_CALCULATOR.build_distance_dict(self, body_copy, cloth_obj, apply = False) 
        
        if cloth_obj.data.shape_keys:
            for sk in [sk for sk in cloth_obj.data.shape_keys.key_blocks if sk.name.startswith('cor')]:
                cloth_obj.shape_key_remove(sk)
        
        if not cloth_obj.data.shape_keys:
            sk = cloth_obj.shape_key_add(name = 'Basis')
            sk.interpolation = 'KEY_LINEAR'
        
        shapekey_list = []
        if sett.shapekey_calc_type == 'pants':
            shapekey_list.extend(['cor_LegFrontRaise_Rt', 'cor_LegFrontRaise_Lt', 'cor_FootDown_Lt', 'cor_FootDown_Rt'])
        elif sett.shapekey_calc_type == 'top':
            shapekey_list.extend(['cor_ElbowBend_Lt', 'cor_ElbowBend_Rt', 'cor_ShoulderSideRaise_Lt', 'cor_ShoulderSideRaise_Rt', 'cor_ShoulderFrontRaise_Lt', 'cor_ShoulderFrontRaise_Rt'])
        elif sett.shapekey_calc_type == 'shoe':
            shapekey_list.extend(['cor_FootDown_Lt', 'cor_FootDown_Rt'])
        else:
            shapekey_list.extend(['cor_ElbowBend_Lt', 'cor_ElbowBend_Rt', 'cor_ShoulderSideRaise_Lt', 'cor_ShoulderSideRaise_Rt', 'cor_ShoulderFrontRaise_Lt', 'cor_ShoulderFrontRaise_Rt', 'cor_LegFrontRaise_Rt', 'cor_LegFrontRaise_Lt', 'cor_FootDown_Lt', 'cor_FootDown_Rt'])
        
        sks = body_copy.data.shape_keys.key_blocks
        for sk in sks:
            if sk.name.startswith('cor'):
                sk.value = 0
            
        for sk in shapekey_list:
            sks[sk].value = 1
            HG_SHAPEKEY_CALCULATOR.deform_obj_from_difference(self, sk, distance_dict, body_copy, cloth_obj, as_shapekey=True)
            sks[sk].value = 0
        
        set_cloth_corrective_drivers(hg_rig.HG.body_obj, cloth_obj.data.shape_keys.key_blocks)
        
        bpy.data.objects.remove(body_copy)
        cloth_obj.select_set(True)
        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        
        layout.label(text = 'Adding shapekeys for type: {}'.format(context.scene.HG3D.shapekey_calc_type.capitalize()))
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
class HG_OT_ADDCLOTHMATH(bpy.types.Operator, MESH_TO_CLOTH_TOOLS):
    bl_idname = "hg3d.addclothmat"
    bl_label = "Add clothing material"
    bl_description = "Adds the default HumGen clothing material for you to set up"
    bl_options = {"UNDO"}

    def execute(self,context): 
        pref = get_prefs()
        mat_file = pref.filepath + str(Path('/outfits/HG_CLOTHING_MAT.blend'))
        
        with bpy.data.libraries.load(mat_file, link = False) as (data_from ,data_to):
            data_to.materials = data_from.materials['HG_CLOTHING']
            
        mat = data_to.materials[0]

        ob = context.object
        if ob.data.materials:
            ob.data.materials[0] = mat
        else:
            ob.data.materials.append(mat)
        
        ob['cloth'] = 1
        
        return {'FINISHED'}