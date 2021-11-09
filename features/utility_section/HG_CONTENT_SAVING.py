import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from shutil import copyfile

import bpy
from mathutils import Vector

from ...core.HG_PCOLL import refresh_pcoll  # type: ignore
from ...core.HG_SHAPEKEY_CALCULATOR import (build_distance_dict,
                                            deform_obj_from_difference)
from ...features.common.HG_COMMON_FUNC import (ShowMessageBox, apply_shapekeys,
                                               find_human, get_addon_root,
                                               get_prefs, hg_delete, hg_log,
                                               show_message, unhide_human)
from ...features.creation_phase.HG_LENGTH import apply_armature, correct_origin


class Content_Saving_Operator:
    def overwrite_warning(self):
        """Show a warning popup if the file already exists
        """
        layout = self.layout
        col = layout.column(align = True)
        col.label(text = f'"{self.name}" already exists in:')
        col.label(text = self.folder)
        col.separator()
        col.label(text = 'Overwrite?')

    def save_thumb(self, folder, current_name, save_name):
        """Save the thumbnail with this content

        Args:
            folder (Path): folder where to save it
            current_name (str): current name of the image
            save_name (str): name to save the image as
        """
        
        img = bpy.data.images[current_name]
        thumbnail_type = self.sett.thumbnail_saving_enum
        
        destination_path = os.path.join(folder, f'{save_name}.jpg')
        if thumbnail_type in ('last_render', 'auto'):
            image_name = 'temp_render_thumbnail' if thumbnail_type == 'last_render' else 'temp_thumbnail'
            source_image = os.path.join(get_prefs().filepath, 'temp_data', f'{image_name}.jpg')
            hg_log("Copying", source_image, "to", destination_path)
            copyfile(source_image, destination_path) 
            
        else:    
            try:
                img.filepath_raw = os.path.join(folder, f'{save_name}.jpg')
                img.file_format  = 'JPEG'
                img.save()
            except RuntimeError as e:
                show_message(self, "Thumbnail image doesn't have any image data")
                print(e)

    def save_objects_optimized(self, context, objs, folder, filename, 
                               clear_sk = True, clear_materials = True,
                               clear_vg = True, clear_ps = True,
                               run_in_background = True, clear_drivers = True):
        """Saves the passed objects as a new blend file, opening the file in the
        background to make it as small as possible

        Args:
            objs              (list)          : List of objects to save
            folder            (Path)          : Folder to save the file in
            filename          (str)           : Name to save the file as
            clear_sk          (bool, optional): Remove all shapekeys from objs. 
                                                Defaults to True.
            clear_materials   (bool, optional): Remove all materials from objs. 
                                                Defaults to True.
            clear_vg          (bool, optional): Remove all vertex groups from 
                                                objs. Defaults to True.
            clear_ps          (bool, optional): Remove all particle systems from
                                                objs. Defaults to True.
            run_in_background (bool, optional): Open the new subprocess in the 
                                                background. Defaults to True.
        """
        for obj in objs:
            if obj.type != 'MESH':
                continue
            if clear_materials:
                obj.data.materials.clear()
            if clear_vg:
                obj.vertex_groups.clear()  
            if clear_sk:
                self._remove_shapekeys(obj)
            if clear_ps:
                self._remove_particle_systems(context, obj)
            if clear_drivers:
                self._remove_obj_drivers(obj)

        if clear_drivers:
            self._clear_sk_drivers()

        new_scene = bpy.data.scenes.new(name='test_scene')
        new_col   = bpy.data.collections.new(name='HG')
        new_scene.collection.children.link(new_col)
        for obj in objs:
            new_col.objects.link(obj)    

        if not os.path.exists(folder):
            os.makedirs(folder)  

        blend_filepath = os.path.join(folder, f'{filename}.blend')
        bpy.data.libraries.write(blend_filepath, {new_scene})
        
        python_file = os.path.join(get_addon_root(), 'scripts', 'hg_purge.py')
        if run_in_background:
            hg_log('STARTING HumGen background process', level = 'BACKGROUND')
            background_blender = subprocess.Popen([bpy.app.binary_path,
                            blend_filepath,
                            "--background",
                            "--python",
                            python_file],
                            stdout= subprocess.DEVNULL)
        else:
            subprocess.Popen([bpy.app.binary_path,
                              blend_filepath,
                              "--python",
                              python_file])
            
        bpy.data.scenes.remove(new_scene)
        for obj in objs:
            hg_delete(obj)

    def _clear_sk_drivers(self):
        for key in bpy.data.shape_keys:
            try:
                fcurves = key.animation_data.drivers
                for _ in fcurves:
                    fcurves.remove(fcurves[0])
            except AttributeError:
                pass

    def _remove_obj_drivers(self, obj):
        try:
            drivers_data = obj.animation_data.drivers

            for dr in drivers_data[:]:  
                obj.driver_remove(dr.data_path, -1)
        except AttributeError:
            return
        
    def _remove_particle_systems(self, context, obj):
        """Remove particle systems from the passed object

        Args:
            obj (Object): obj to remove particle systems from
        """
        context.view_layer.objects.active= obj
        for i, ps in enumerate(obj.particle_systems):   
            obj.particle_systems.active_index = i
            bpy.ops.object.particle_system_remove()

    def _remove_shapekeys(self, obj):
        """Remove shapekeys from the passed object

        Args:
            obj (Object): obj to remove shapekeys from
        """        
        for sk in [sk for sk in obj.data.shape_keys.key_blocks if sk.name != 'Basis']:
            obj.shape_key_remove(sk)
        if obj.data.shape_keys:
            obj.shape_key_remove(obj.data.shape_keys.key_blocks['Basis'])
        
    def remove_number_suffix(self, name) -> str:
        """Remove the number suffix from the passed name 
        (i.e. Box.004 becomes Box)

        Args:
            name (str): name to remove suffix from

        Returns:
            str: name without suffix
        """
        re_suffix = re.search(r'.\d\d\d', name)
        if not re_suffix or not name.endswith(re_suffix.group(0)):
            return name
        else:
            return name.replace(re_suffix.group(0), '')
        
class HG_OT_OPEN_FOLDER(bpy.types.Operator):
    """Open the folder that belongs to this section

    API: False

    Operator type:
        Open subprocess
    
    Prereq:
        subpath passed
    """
    bl_idname      = "hg3d.openfolder"
    bl_label       = "Open folder"
    bl_description = "Opens the folder that belongs to this type of content"

    subpath: bpy.props.StringProperty()

    def execute(self,context):        
        pref = get_prefs()
        path = pref.filepath + str(Path(self.subpath))

        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

        return {'FINISHED'}

class HG_OT_SAVE_SHAPEKEY(bpy.types.Operator, Content_Saving_Operator):
    """Save these shapekeys to a separate file. They will be loaded on any 
    newly created human from now on

    Operator type:
        Content saving
        
    Prereq:
        Items in shapekeys_col
        
    Args:
        name (str): internal, does not need to be passed

    """
    bl_idname = "hg3d.save_shapekeys"
    bl_label = "Save shapekeys"
    bl_description = "Save shapekeys"
    bl_options = {'UNDO'}
    
    name: bpy.props.StringProperty()

    def invoke(self, context, event):
        pref            = get_prefs()
        self.sett       = context.scene.HG3D
        self.collection = context.scene.shapekeys_col

        self.folder = pref.filepath + str(Path('/models/shapekeys/'))
        self.name = self.sett.sk_collection_name
        if os.path.isfile(str(Path(f'{self.folder}/{self.name}.blend'))):
            return context.window_manager.invoke_props_dialog(self)

        return self.execute(context)

    def draw(self, context):
        self.overwrite_warning()

    def execute(self,context):        
        hg_rig = self.sett.content_saving_active_human

        data = [item.sk_name for item in self.collection if item.enabled]
   
        sk_obj      = hg_rig.HG.body_obj.copy()
        sk_obj.data = sk_obj.data.copy()
        sk_obj.name = 'hg_shapekey'
        context.collection.objects.link(sk_obj)
        
        sks_to_remove = [sk for sk in sk_obj.data.shape_keys.key_blocks 
                         if sk.name not in data 
                         and sk.name != 'Basis']
        for sk in sks_to_remove:
            sk_obj.shape_key_remove(sk)
    
        with open((os.path.join(self.folder, f'{self.name}.json')), 'w') as f:
            json.dump(data, f, indent = 4)
        
        self.save_objects_optimized(
            context,
            [sk_obj,],
            self.folder,
            self.name,
            clear_sk=False
        )

        msg = f'Saved {len(data)} shapekeys to {self.folder}'
        
        self.report({'INFO'}, msg)
        ShowMessageBox(message = msg)
        
        self.sett.content_saving_ui = False    
        
        return {'FINISHED'}


class HG_OT_SAVE_POSE(bpy.types.Operator, Content_Saving_Operator):
    bl_idname = "hg3d.save_pose"
    bl_label = "Save pose"
    bl_description = "Save pose"
    bl_options = {'UNDO'}
    
    name: bpy.props.StringProperty()

    def invoke(self, context, event):
        pref = get_prefs()
        sett = context.scene.HG3D
        self.sett = sett
        
        self.thumb = self.sett.preset_thumbnail_enum
        if sett.pose_category_to_save_to == 'existing':
            category = sett.pose_chosen_existing_category
        else:
            category = sett.pose_new_category_name
        
        self.folder = os.path.join(pref.filepath, 'poses', category)
        self.name = self.sett.pose_name
        
        if os.path.isfile(os.path.join(self.folder, f'{self.name}.blend')):
            return context.window_manager.invoke_props_dialog(self)

        return self.execute(context)

    def draw(self, context):
        self.overwrite_warning()

    def execute(self,context):        
        hg_rig = self.sett.content_saving_active_human
  
        pose_object = hg_rig.copy()
        pose_object.data = pose_object.data.copy()
        pose_object.name = 'HG_Pose'
        context.collection.objects.link(pose_object)        
  
        self.save_objects_optimized(
            context,
            [pose_object,],
            self.folder,
            self.name
        )

        if not self.sett.thumbnail_saving_enum == 'none':
            self.save_thumb(self.folder, self.thumb, self.name)

        msg = f'Saved {self.name} to {self.folder}'
        
        self.report({'INFO'}, msg)
        ShowMessageBox(message = msg)
        
        context.view_layer.objects.active = hg_rig
        refresh_pcoll(self, context, 'poses')
        
        self.sett.content_saving_ui = False    
        
        return {'FINISHED'}

class HG_OT_SAVEPRESET(bpy.types.Operator, Content_Saving_Operator):
    """Save the current creation phase human as a starting human

    Operator type:
        Content Saving
        
    Prereq:
        Active object is part of a humgen human
        That humgen human is still in creation phase
        All external dependencies (custom shapekeys, textures) are saved separately
    
    Args:
        name (str): internal, does not need to be passed
    """
    bl_idname      = "hg3d.save_starting_human"
    bl_label       = "Save as starting human"
    bl_description = "Save as starting human"

    name: bpy.props.StringProperty()

    def invoke(self, context, event):
        pref        = get_prefs()
        self.sett   = context.scene.HG3D
        self.hg_rig = self.sett.content_saving_active_human

        self.thumb = self.sett.preset_thumbnail_enum

        self.folder = pref.filepath + str(Path(f'/models/{self.hg_rig.HG.gender}/'))
        self.name = self.sett.preset_name
        if os.path.isfile(str(Path(f'{self.folder}/{self.name}.json'))):
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)
    
    def draw(self, context):
        self.overwrite_warning()

    def execute(self,context):        
        hg_rig = self.hg_rig
        folder = self.folder

        hg_body = hg_rig.HG.body_obj
        hg_eyes = [obj for obj in hg_rig.children if 'hg_eyes' in obj]
        
        if not self.sett.thumbnail_saving_enum == 'none':
            self.save_thumb(self.folder, self.thumb, self.name)

        preset_data = {}
        preset_data['gender'] = hg_rig.HG.gender
        preset_data['experimental'] = True if hg_rig.HG.experimental else False
        
        eyebrows = [mod for mod in hg_body.modifiers 
                    if mod.type == 'PARTICLE_SYSTEM' 
                    and mod.particle_system.name.startswith('Eyebrows')
                    ]
        preset_data['eyebrows'] = next(
            (mod.particle_system.name for mod in eyebrows 
                if (mod.show_viewport or mod.show_render)
                ),
            f'Eyebrows_{hg_rig.HG.gender.capitalize()}'
            )
        
        #TODO is it even necessary to return the dict back?
        preset_data = self.add_body_proportions(preset_data, hg_rig) 
        preset_data = self.add_shapekeys(preset_data, hg_body)
        preset_data = self.add_material_data(preset_data, hg_body, hg_eyes)
        
        with open(str(Path(f'{folder}/{self.name}.json')), 'w') as f:
            json.dump(preset_data, f, indent = 4)
        
        self.report({'INFO'}, f'Saved starting human {self.name} to {folder}')
        ShowMessageBox(message = f'Saved starting human {self.name} to {folder}')    
        
        self.sett.content_saving_ui = False    
        
        context.view_layer.objects.active = hg_rig
        refresh_pcoll(self, context, 'humans')
        
        return {'FINISHED'}
    
    def add_body_proportions(self, preset_data, hg_rig) -> dict:
        """Add body proportions to the preset_data dict

        Args:
            preset_data (dict): preset human settings dict
            hg_rig (Object): Armature

        Returns:
            dict: preset_data
        """
        bp_dict = {}
        bp_dict['length'] = hg_rig.dimensions[2]
        
        size = hg_rig.pose.bones['breast.L'].scale[0]
        bp_dict['chest'] = 3*size -2.5
  
        preset_data['body_proportions'] = bp_dict

        return preset_data

    def add_shapekeys(self, preset_data, hg_body) -> dict:
        """Add shapekey data to the preset_data dict

        Args:
            preset_data (dict): preset human settings dict
            hg_rig (Object): Armature

        Returns:
            dict: preset_data
        """        
        sks = hg_body.data.shape_keys.key_blocks
        sk_dict = {sk.name:sk.value for sk in sks 
                   if sk.value != 0 
                   and not sk.name.startswith(('expr',
                                               'cor',
                                               'Basis'))
                   }
        preset_data['shapekeys'] = sk_dict
        
        return preset_data

    def add_material_data(self, preset_data, hg_body, hg_eyes) -> dict:
        """Add material info to the preset_data dict

        Args:
            preset_data (dict): preset human settings dict
            hg_body (Object): HumGen body object
            hg_eyes (Object): HumGen eyes object

        Returns:
            dict: preset_data
        """
        mat_dict = {}
        mat = hg_body.data.materials[0]
        nodes = mat.node_tree.nodes
        
        mat_dict['texture_library'] = (mat['texture_library'] 
                                       if getattr(mat, "texture_library", None) 
                                       else 'Default 4K') 
        
        img_name = nodes['Color'].image.name
        if img_name[-1].isdigit(): #check if ends with duplicate numbers
            img_name = img_name[:-4]
        
        mat_dict['diffuse'] = img_name
        nodegroup_dict = {}
        for node in [node for node in nodes if node.bl_idname == 'ShaderNodeGroup']:
            input_dict = {}
            for input in [inp for inp in node.inputs if not inp.links]:
                inp_value = (
                    tuple(input.default_value) 
                    if str(type(input.default_value)) == "<class 'bpy_prop_array'>" 
                    else input.default_value
                    )
                input_dict[input.name] = inp_value
                
            nodegroup_dict[node.name] = input_dict
        nodename_dict = {
            'Bump': 'Strength',
            'Normal Map': 'Strength',
            'Darken_hsv': 'Value',
            'Lighten_hsv': 'Value',
            'R_Multiply': 1
        }
        
        for nodename, input_name in nodename_dict.items():
            nodegroup_dict[nodename] = {input_name: nodes[nodename].inputs[input_name].default_value,}
        
        mat_dict['node_inputs'] = nodegroup_dict

        eye_mat = hg_eyes[0].data.materials[1]
        eye_nodes = eye_mat.node_tree.nodes
        mat_dict['eyes'] = {
            'HG_Eye_Color': tuple(eye_nodes['HG_Eye_Color'].inputs[2].default_value),
            'HG_Scelera_Color': tuple(eye_nodes['HG_Scelera_Color'].inputs[2].default_value)
        }

        preset_data['material'] = mat_dict

        return preset_data



class HG_OT_SAVEHAIR(bpy.types.Operator, Content_Saving_Operator):
    bl_idname      = "hg3d.save_hair"
    bl_label       = "Save hairstyle"
    bl_description = "Save hairstyle"

    name: bpy.props.StringProperty()

    def invoke(self, context, event):
        pref = get_prefs()
        self.sett = context.scene.HG3D
        
        self.hg_rig = self.sett.content_saving_active_human
        try:
            unhide_human(self.hg_rig)
        except Exception as e:
            show_message(self, 'Could not find human, did you delete it?')
            hg_log('Content saving failed, rig could not be found with error: ', e)
            return {'CANCELLED'}

        self.thumb = self.sett.preset_thumbnail_enum

        self.folder = pref.filepath + str(Path(f'/hair/{self.sett.save_hairtype}/'))
        self.name = self.sett.hairstyle_name
        if os.path.isfile(str(Path(f'{self.folder}/{self.name}.blend'))):
            return context.window_manager.invoke_props_dialog(self)
        return self.execute(context)

    def draw(self, context):
        self.overwrite_warning()
        
    def execute(self,context):        
        sett = self.sett
        pref = get_prefs()

        hg_rig  = self.hg_rig
        hg_body = hg_rig.HG.body_obj
        col     = context.scene.savehair_col

        hair_obj      = hg_body.copy()
        hair_obj.data = hair_obj.data.copy()
        hair_obj.name = 'HG_Body'
        context.collection.objects.link(hair_obj)

        context.view_layer.objects.active = hair_obj
        hair_obj.select_set(True)
        self._remove_other_systems(hair_obj, [item.ps_name for item in col if item.enabled])

        keep_vgs = self._find_vgs_used_by_hair(hair_obj)
        for vg in [vg for vg in hair_obj.vertex_groups if vg.name not in keep_vgs]:
                hair_obj.vertex_groups.remove(vg)

        genders = [
            gd for gd, enabled 
            in {
                'male': sett.savehair_male,
                'female': sett.savehair_female }.items() 
            if enabled
            ]
        for gender in genders:
            hair_type = sett.save_hairtype
            if hair_type == 'face_hair' and gender == 'female':
                continue

            if hair_type == 'head':
                folder = os.path.join(pref.filepath, 'hair', hair_type, gender, 'Custom')
            else:
                folder = os.path.join(pref.filepath, 'hair', hair_type, 'Custom')

            if not os.path.exists(folder):
                os.makedirs(folder)     
            if not self.sett.thumbnail_saving_enum == 'none':
                self.save_thumb(folder, self.thumb, self.name)  
            
            self._make_hair_json(context, hair_obj, folder, self.name)
            
        self.save_objects_optimized(
            context,
            [hair_obj,],
            self.folder,
            self.name,
            clear_ps=False,
            clear_vg=False
        )
        
        context.view_layer.objects.active= hg_rig
        msg = f'Saved {self.name} to {self.folder}'
        self.report({'INFO'}, msg)
        ShowMessageBox(message = msg)
        
        sett.content_saving_ui = False
        
        context.view_layer.objects.active = hg_rig
        refresh_pcoll(self, context, 'hair')
        refresh_pcoll(self, context, 'face_hair')
        
        return {'FINISHED'}

    def _find_vgs_used_by_hair(self, hair_obj) -> list:
        """Get a list of all vertex groups used by the hair systems

        Args:
            hair_obj (bpy.types.Object): Human body the hair is on

        Returns:
            list: list of vertex groups that are used by hairsystems
        """
        all_vgs = [vg.name for vg in hair_obj.vertex_groups]
        keep_vgs = []
        for ps in [ps for ps in hair_obj.particle_systems]: #TODO only iterate over selected systems
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


    def _remove_other_systems(self, obj, keep_list):
        """Remove particle systems that are nog going to be saved

        Args:
            obj (bpy.types.Object): Human body object to remove systems from
            keep_list (list): List of names of particle systems to keep
        """
        remove_list = [ps.name for ps in obj.particle_systems if ps.name not in keep_list]
           
        for ps_name in remove_list:    
            ps_idx = [i for i, ps in enumerate(obj.particle_systems) if ps.name == ps_name]
            obj.particle_systems.active_index = ps_idx[0]
            bpy.ops.object.particle_system_remove()

    def _make_hair_json(self, context, hair_obj, folder, style_name):
        """Make a json that contains the settings for this hairstyle and save it

        Args:
            context (context): bl context
            hair_obj (bpy.types.Object): Body object the hairstyles are on
            folder (str): Folder to save json to
            style_name (str): Name of this style
        """
        ps_dict = {}
        for mod in hair_obj.modifiers:
            if mod.type == 'PARTICLE_SYSTEM':
                ps          = mod.particle_system
                ps_length   = ps.settings.child_length
                ps_children = ps.settings.child_nbr
                ps_steps    = ps.settings.display_step
                ps_dict[ps.name] = {"length": ps_length,
                                    "children_amount": ps_children,
                                    "path_steps": ps_steps}

        json_data = {
            "blend_file": f'{style_name}.blend',
            "hair_systems": ps_dict
        }

        full_path = os.path.join(folder, f'{style_name}.json')
        
        with open(full_path, 'w') as f:
            json.dump(json_data, f, indent = 4)

#FIXME origin to model origin? Correction?
class HG_OT_SAVEOUTFIT(bpy.types.Operator, Content_Saving_Operator):
    """Save this outfit to the content folder

    Args:
        name (str): Internal prop 
        alert (str): Internal prop #TODO check if redundant
    """
    bl_idname      = "hg3d.save_clothing"
    bl_label       = "Save as outfit"
    bl_description = "Save as outfit"
    bl_options     = {"UNDO"}

    name: bpy.props.StringProperty()
    alert: bpy.props.StringProperty()

    def invoke(self, context, event):
        self.pref   = get_prefs()
        self.sett   = context.scene.HG3D
        self.hg_rig = self.sett.content_saving_active_human
        self.col    = context.scene.saveoutfit_col

        self.thumb = self.sett.preset_thumbnail_enum
        
        obj_list_without_suffix = [self.remove_number_suffix(item.obj_name) for item in self.col]
        if len(obj_list_without_suffix) != len(set(obj_list_without_suffix)):
            show_message(self, 'There are objects in the list which have the same names if suffix like .001 is removed')
            return {'CANCELLED'}            

        self.folder = os.path.join(self.pref.filepath, self.sett.saveoutfit_categ)
        self.name = self.sett.clothing_name
        
        if os.path.isfile(str(Path(f'{self.folder}/{self.hg_rig.HG.gender}/Custom/{self.name}.blend'))):
            self.alert = 'overwrite'
            return context.window_manager.invoke_props_dialog(self)
        
        return self.execute(context)

    def draw(self, context):
        self.overwrite_warning()

    def execute(self,context):        
        sett = self.sett
        col  = self.col
        objs = [bpy.data.objects[item.obj_name] for item in col]
                  
        genders = []
        if sett.saveoutfit_female:
            genders.append('female')
        if sett.saveoutfit_male:
            genders.append('male')

        for gender in genders:
            gender_folder = self.folder + str(Path(f'/{gender}/Custom'))
            if not os.path.isdir(gender_folder):
                os.mkdir(gender_folder)
            if not self.sett.thumbnail_saving_enum == 'none':
                self.save_thumb(gender_folder, self.thumb, self.name)
        
        body_copy = self.hg_rig.HG.body_obj.copy()
        body_copy.data = body_copy.data.copy()
        context.collection.objects.link(body_copy)
        apply_shapekeys(body_copy)
        apply_armature(body_copy)
        
        self.save_material_textures(objs)
        obj_distance_dict = {}
        for obj in objs:
            distance_dict = build_distance_dict(body_copy, obj, apply = False) 
            obj_distance_dict[obj.name] = distance_dict
        
 
        for gender in genders:
            export_list = []
            backup_human = next((obj for obj in self.hg_rig.HG.backup.children 
                                 if 'hg_body' in obj))
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
                
                if gender != self.hg_rig.HG.gender:
                    name = 'Opposite gender'
                    as_sk = True
                else:
                    name = ''
                    as_sk = False
                    
                deform_obj_from_difference(
                    name,
                    distance_dict,
                    backup_human,
                    obj_copy,
                    as_shapekey = as_sk,
                    apply_source_sks = False,
                    ignore_cor_sk = True
                )
                correct_origin(context, obj, backup_human)
                export_list.append(obj_copy)

            if gender == 'male':
                hg_delete(backup_human)
                
            gender_folder = self.folder + str(Path(f'/{gender}/Custom'))
            self.save_objects_optimized(
                context,
                export_list,
                gender_folder,
                self.name,
                clear_sk=False,
                clear_materials=False,
                clear_vg=False,
                clear_drivers= False,
                run_in_background= not sett.open_exported_outfits
            )
        hg_delete(body_copy)

        context.view_layer.objects.active = self.hg_rig
        refresh_pcoll(self, context, 'outfit')
        refresh_pcoll(self, context, 'footwear')

        show_message(self, 'Succesfully exported outfits')
        self.sett.content_saving_ui = False  
        
        return {'FINISHED'}

    #CHECK naming adds .004 to file names, creating duplicates
    def save_material_textures(self, objs):
        """Save the textures used by the materials of these objects to the
        content folder

        Args:
            objs (list): List of objects to check for textures on
        """
        saved_images = {}

        for obj in objs:
            for mat in obj.data.materials:
                nodes= mat.node_tree.nodes
                for img_node in [n for n in nodes 
                                 if n.bl_idname == 'ShaderNodeTexImage']:
                    self._process_image(saved_images, img_node)

    def _process_image(self, saved_images, img_node):
        """Prepare this image for saving and call _save_img on it

        Args:
            saved_images (dict): Dict to keep record of what images were saved
            img_node (ShaderNode): TexImageShaderNode the image is in
        """
        img = img_node.image
        if not img:
            return
        colorspace = img.colorspace_settings.name 
        if not img:
            return
        img_path, saved_images = self._save_img(img, saved_images)
        if img_path:
            new_img = bpy.data.images.load(img_path)
            img_node.image = new_img
            new_img.colorspace_settings.name = colorspace
    
    def _save_img(self, img, saved_images) -> 'tuple[str, list]':
        """Save image to content folder

        Returns:
            tuple[str, dict]: 
                str: path the image was saved to
                dict[str: str]:
                    str: name of the image
                    str: path the image was saved to 
        """
        img_name = self.remove_number_suffix(img.name)
        if img_name in saved_images:
            return saved_images[img_name], saved_images
        
        path = self.pref.filepath + str(Path(f'{self.sett.saveoutfit_categ}/textures/'))
        if not os.path.exists(path):
            os.makedirs(path)  

        full_path = os.path.join(path, img_name)
        try:
            shutil.copy(bpy.path.abspath(img.filepath_raw), os.path.join(path, img_name))
            saved_images[img_name] = full_path
        except RuntimeError as e:
            hg_log(f'failed to save {img.name} with error {e}', level = 'WARNING')
            self.report({'WARNING'}, 'One or more images failed to save. See the system console for specifics')
            return None, saved_images
        except shutil.SameFileError:
            saved_images[img_name] = full_path
            return full_path, saved_images
            
        return full_path, saved_images


class HG_OT_AUTO_RENDER_THUMB(bpy.types.Operator, Content_Saving_Operator):
    """Renders a thumbnail from preset camera positions and lighting. This thumb
    is then added to the prop used by custom content saving operators.
    """
    bl_idname      = "hg3d.auto_render_thumbnail"
    bl_label       = "Auto render thumbnail"
    bl_description = "Automatically renders a thumbnail for you"

    thumbnail_type: bpy.props.StringProperty()

    def execute(self, context):
        hg_rig = context.scene.HG3D.content_saving_active_human
        
        thumbnail_type = self.thumbnail_type
               
        type_sett = self._get_settings_dict_by_thumbnail_type(thumbnail_type)
        
        hg_thumbnail_scene = bpy.data.scenes.new('HG_Thumbnail_Scene')
        old_scene = context.window.scene
        context.window.scene = hg_thumbnail_scene
        
        camera_data = bpy.data.cameras.new(name='Camera')
        camera_object = bpy.data.objects.new('Camera', camera_data)
        hg_thumbnail_scene.collection.objects.link(camera_object)
        
        camera_object.location = Vector(
            (
                type_sett['camera_x'],
                type_sett['camera_y'],
                hg_rig.dimensions[2]
            )
        ) + hg_rig.location
        
        hg_thumbnail_scene.camera = camera_object
        hg_thumbnail_scene.render.engine = 'CYCLES'
        hg_thumbnail_scene.cycles.samples = 16
        try:
            hg_thumbnail_scene.cycles.use_denoising = True
        except Exception:
            pass
        
        new_coll = hg_thumbnail_scene.collection
        new_coll.objects.link(hg_rig)
        for child in hg_rig.children:
            new_coll.objects.link(child)
        
        
        hg_thumbnail_scene.render.resolution_y = 256
        hg_thumbnail_scene.render.resolution_x = 256

        self._make_camera_look_at_human(
            camera_object,
            hg_rig,
            type_sett['look_at_correction']
        )
        camera_data.lens = type_sett['focal_length']
        
        lights = []
        light_settings_enum = [
            (100, (-.3, -1, 2.2)),
            (10, (0.38, 0.7, 1.83)),
            (50, (0, -1.2, 0))
        ]
        for energy, location in light_settings_enum:
            point_light = bpy.data.lights.new(name = f'light_{energy}W', type = 'POINT')
            point_light.energy = energy
            point_light_object = bpy.data.objects.new('Light', point_light)
            point_light_object.location = Vector(location) + hg_rig.location
            hg_thumbnail_scene.collection.objects.link(point_light_object)
            lights.append(point_light_object)

        save_folder = os.path.join(get_prefs().filepath, 'temp_data')
        
        if not os.path.isdir(save_folder):
            os.makedirs(save_folder)
        
        hg_thumbnail_scene.render.image_settings.file_format='JPEG'   
        full_image_path = os.path.join(save_folder, 'temp_thumbnail.jpg')
        hg_thumbnail_scene.render.filepath = full_image_path
        
        bpy.ops.render.render(write_still = True)
        
        for light in lights:
            hg_delete(light)
        
        hg_delete(camera_object)
        
        context.window.scene = old_scene 
        
        bpy.data.scenes.remove(hg_thumbnail_scene)
        
        img = bpy.data.images.load(full_image_path)
        context.scene.HG3D.preset_thumbnail = img
        
        return {'FINISHED'}

    def _get_settings_dict_by_thumbnail_type(self, thumbnail_type) -> dict:
        """Returns a dict with settings of how to configure the camera for this
        automatic thumbnail

        Args:
            thumbnail_type (str): key to the dict inside this function

        Returns:
            dict[str, float]:
                str: name of this property
                float: setting for camera property
        """
        type_settings_dict = {
            'head': {
                'camera_x': -1.0,
                'camera_y': -1.0,
                'focal_length': 135,
                'look_at_correction': 0.14
            },
            'full_body_front': {
                'camera_x': 0,
                'camera_y': -2.0,
                'focal_length': 50,
                'look_at_correction': 0.9
            },
            'full_body_side': {
                'camera_x': -2.0,
                'camera_y': -2.0,
                'focal_length': 50,
                'look_at_correction': 0.9
            },
        }
        
        type_sett = type_settings_dict[thumbnail_type]
        return type_sett
            
    def _make_camera_look_at_human(self, obj_camera, hg_rig, look_at_correction):
        """Makes the passed camera point towards a preset point on the human

        Args:
            obj_camera (bpy.types.Object): Camera object
            hg_rig (Armature): Armature object of human
            look_at_correction (float): Correction based on how much lower to 
                point the camera compared to the top of the armature
        """
        
        hg_loc = hg_rig.location
        height_adjustment = hg_rig.dimensions[2] - look_at_correction*0.55*hg_rig.dimensions[2] 
        hg_rig_loc_adjusted = Vector((hg_loc[0], hg_loc[1], hg_loc[2]+height_adjustment))
        loc_camera = obj_camera.location

        direction = hg_rig_loc_adjusted - loc_camera
        rot_quat = direction.to_track_quat('-Z', 'Y')

        obj_camera.rotation_euler = rot_quat.to_euler()        
        
        
