"""
Operators and functions to be used by the developer and content pack creators
"""

import subprocess
import bpy #type: ignore
from mathutils import Vector #type: ignore
from pathlib import Path
import mathutils #type: ignore
from . HG_COMMON_FUNC import apply_shapekeys, find_human, get_prefs
from . HG_LENGTH import apply_armature, update_length
from . HG_CREATION import load_human
from . HG_NEXTPHASE import remove_stretch_bones
import numpy as np #type: ignore
import os
import json
import random


#REMOVE
class HG_TESTOP(bpy.types.Operator):
    """
    operator for testing bits of code
    """
    bl_idname = "hg3d.testop"
    bl_label = "Test"
    bl_description = ""
    bl_options = {"UNDO"}

    def execute(self,context):
        return {'FINISHED'}



#REMOVE
class HG_RENDER_THUMBS(bpy.types.Operator):
    """
    Renders thumbnails for the selected preview collection
    """
    bl_idname = "hg3d.renderthumbs"
    bl_label = "Render thumbnails"
    bl_description = "Renders thumbnails of selected category"
    bl_options = {"UNDO"}

    @classmethod
    def poll (cls, context):
        return context.object

    def execute(self,context):
        sett = context.scene.HG3D
        pcoll_name = sett.pcoll_render

        hg_rig = find_human(context.object)
        if not hg_rig:
            self.report({'WARNING'}, 'No human selected')
            return {'FINISHED'}

        if not pcoll_name == 'randomize_human':
            pcoll_list = sett['previews_list_{}'.format(pcoll_name)]

        old_filepath = context.scene.render.filepath
        ext_dict = {'expressions': '.txt', 'humans': '.jpg', 'patterns': '.png', 'face_hair': '.json', 'hair': '.json'}
        context.scene.render.image_settings.file_format='JPEG'
        
        if pcoll_name == 'randomize_human':
            for i in range(20):
                context.scene.render.filepath = sett.thumb_render_path + str(random.randint(0,9999)) + '.jpg'
                bpy.ops.hg3d.random(type="body_type")
                bpy.ops.hg3d.random(type="face_all")
                hg_body = hg_rig.HG.body_obj
                mat = hg_body.data.materials[0]
                nodes = mat.node_tree.nodes
                eye_mat = [child for child in hg_rig.children if 'hg_eyes' in child][0].data.materials[1]
                eye_nodes = eye_mat.node_tree.nodes

                nodes['Skin_tone'].inputs[1].default_value = random.uniform(.2,3)
                nodes['Skin_tone'].inputs[2].default_value = random.uniform(-1,1)
                eye_nodes['HG_Eye_Color'].inputs[2].default_value = (random.uniform(0,1), random.uniform(0,1), random.uniform(0,1), 1)
                nodes['Darken_hsv'].inputs[2].default_value = random.uniform(0,2)
                nodes['Lighten_hsv'].inputs[2].default_value = random.uniform(0,2)
                nodes['Freckles_control'].inputs[3].default_value = random.uniform(0,.5)
                nodes['Splotches_control'].inputs[3].default_value = random.uniform(0,.5)

                old_chance = random.choice([0,0,0,0,0,0,0,0, .3, .3, .6, .6, 1, 1])
                hg_body.data.shape_keys.key_blocks["age_old.Transferred"].value = old_chance
                nodes['HG_Age'].inputs[1].default_value = old_chance * 6

                makeup_chance= random.choice([0,0,0,0,0,0,0,0, .3, .3, .6, .6, 1, 1])
                if hg_rig.HG.gender == 'male':
                    nodes['Gender_Group'].inputs[2].default_value = makeup_chance/2
                    nodes['Gender_Group'].inputs[3].default_value = makeup_chance/2
                else:
                    nodes['Gender_Group'].inputs[10].default_value = makeup_chance
                    nodes['Gender_Group'].inputs[8].default_value = makeup_chance
                    nodes['Gender_Group'].inputs[6].default_value = makeup_chance

                grey_chance= random.choice([1,1,1,1,.8,.8,.8,.6,.6,.3,.3,0])
                hair_mat = hg_body.data.materials[1]
                hair_nodes = hair_mat.node_tree.nodes
                hair_control = hair_nodes['HG_Hair']
                hair_control.inputs[0].default_value = random.uniform(0,1)
                hair_control.inputs[1].default_value = grey_chance
                bpy.ops.render.render(write_still=True)
        else:
            #TODO make better code for this. Note: sett[pcoll_{pcoll_name}] results in keyerror
            for item in pcoll_list:
                context.scene.render.filepath = sett.thumb_render_path + str(Path(item)).replace(ext_dict[pcoll_name] if pcoll_name in ext_dict else '.blend', '') + '.jpg'
                if pcoll_name == 'poses':
                    sett.pcoll_poses = item
                elif pcoll_name == 'expressions':
                    sett.pcoll_expressions = item
                elif pcoll_name == 'outfit':
                    sett.pcoll_outfit = item
                elif pcoll_name == 'humans':
                    sett.pcoll_humans = item
                elif pcoll_name == 'hair':
                    sett.pcoll_hair = item
                elif pcoll_name == 'face_hair':
                    sett.pcoll_face_hair = item
                elif pcoll_name == 'footwear':
                    sett.pcoll_footwear = item
                elif pcoll_name == 'patterns':
                    sett.pcoll_patterns = item

                bpy.ops.render.render(write_still=True)
        
        context.scene.render.filepath = old_filepath
        return {'FINISHED'}

#REMOVE
class HG_CHECK_DISTANCE(bpy.types.Operator):
    """
    Places an empty at all vertex positions that are closer than 3mm to the human
    """
    bl_idname = "hg3d.checkdistance"
    bl_label = "Distance"
    bl_description = "Places an empty at all vertex positions that are closer than 3mm to the human"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll (cls, context):
        return context.object

    def execute(self,context):
        human = bpy.context.active_object
        
        if not human.parent or not human.parent.HG.ishuman:
            self.report({'WARNING'}, 'Active object is not a HumGen body object')
            return {'FINISHED'}
        cloth = [obj for obj in bpy.context.selected_objects if obj != human]
        if not cloth:
            self.report({'WARNING'}, 'No cloth object in selected objects')   
            return {'FINISHED'}
        if len(cloth) >= 1:
            self.report({'INFO'}, 'Multiple cloth objects selected, only ran for the first selected cloth object')  

        for vert in cloth[0].data.vertices:
            vert_global = cloth[0].matrix_world @ vert.co
            vert_local = human.matrix_world.inverted() @ vert_global
            (_, loc, _, _) = human.closest_point_on_mesh(vert_local)
            
            v_dist = np.linalg.norm(vert_local-loc)

            if v_dist < .003:
                empty = bpy.data.objects.new( "HG_Empty", None )
                empty.location = vert_global
                empty.scale = (.01, .01, .01)       
                bpy.context.scene.collection.objects.link(empty)
                empty.select_set(True)

        return {'FINISHED'}

#REMOVE
class HG_DELETE_EMPTIES(bpy.types.Operator):
    """
    removes all HG empties
    """
    bl_idname = "hg3d.delempty"
    bl_label = ""
    bl_description = "Removes all the empties placed by the check distance operator"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self,context):
        empties = [obj for obj in bpy.data.objects if 'HG_Empty' in obj.name]
        for empty in empties:
            bpy.data.objects.remove(empty)
        return {'FINISHED'}

#REMOVE
class HG_CREATOR_MODEL(bpy.types.Operator):
    """
    Adds a new human in creator mode. This stops the script from removing parts of the hg_human, for example the shapekeys of the opposite gender
    """
    bl_idname = "hg3d.creatorhuman"
    bl_label = "Add creator human"
    bl_description = "Places the full HumGen human model, this is used for clothing modeling"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self,context):
        bpy.ops.view3d.snap_cursor_to_center()
        load_human(context, creator = True)
        return {'FINISHED'}

#REMOVE
class HG_PURGE_FILE(bpy.types.Operator):
    """
    Purges the current file and saves it again. It reports how much filesize was removed
    """
    bl_idname = "hg3d.purge"
    bl_label = ""
    bl_description = "Blend files contain about 500kb of unneeded data. This operator removes that data, so the library can be much smaller in filesize"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self,context):
        if not bpy.data.is_saved:
            self.report({'WARNING'}, 'Save the file first')
            return {'FINISHED'}

        original_size = self.get_file_size()

        remove_list = []
        for obj in bpy.data.objects:
            try:
                bpy.data.collections[0].objects.link(obj)
            except: pass
            try:
                context.scene.collection.objects.unlink(obj)
            except: pass

            if obj.type == 'CAMERA' or obj.type == 'LIGHT':
                remove_list.append(obj)

            elif context.scene.HG3D.dev_delete_unselected and obj not in context.selected_objects:
                remove_list.append(obj)
            
        for obj in remove_list:
            bpy.data.objects.remove(obj)

        brushes = [brush for brush in bpy.data.brushes]
        for brush in brushes:
            bpy.data.brushes.remove(brush)

        images = [image for image in bpy.data.images]
        for image in images:
            if not image.users or image.file_format == 'HDR':
                bpy.data.images.remove(image)
        
        workspaces = [ws for ws in bpy.data.workspaces if ws != context.workspace]
        bpy.data.batch_remove(ids=workspaces)

        screens = [screen for screen in bpy.data.screens if screen != context.screen]
        bpy.data.batch_remove(ids=screens)

        try:
            if context.scene.gaf_props: 
                context.scene.gaf_props.hdri_handler_enabled = False #turn of gaffer if installed
        except:
            pass

        if bpy.data.worlds:
            world = bpy.data.worlds[0]
            bpy.data.worlds.remove(world)  

        override = bpy.context.copy()
        override["area.type"] = ['OUTLINER']
        override["display_mode"] = ['ORPHAN_DATA']
        bpy.ops.outliner.orphans_purge(override)     
        bpy.ops.file.make_paths_relative()

        bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)

        new_size = self.get_file_size()
        saved_size = original_size - new_size

        kilobyte = 1024  
        megabyte = 1048576  

        saved_size_scaled = "{:.1f} KB".format(saved_size / kilobyte)
        new_size_scaled = "{:.1f} MB".format(new_size / megabyte)

        self.report({'INFO'}, 'Purged {}, new size is {}'.format(saved_size_scaled, new_size_scaled))
        
        return {'FINISHED'}

    def get_file_size(self):
        filepath = bpy.data.filepath
        size_bytes = os.stat(filepath).st_size if filepath != '' else -1

        return size_bytes

#REMOVE
class HG_CLOTH_CALCULATOR(bpy.types.Operator):
    """
    Calculates correct shapekeys for proportion changes
    """
    bl_idname = "hg3d.clothcalc"
    bl_label = "Calc"
    bl_description = "Calculate cloth"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll (cls, context):
        return context.object

    def execute(self,context):
        sett = context.scene.HG3D
        
        if not context.active_object.parent or not context.active_object.parent.HG.ishuman:
            self.report({'WARNING'}, 'Active object is not a HumGen body object')
            return {'FINISHED'}

        source = bpy.context.active_object.copy()
        source.data = source.data.copy()
        bpy.context.scene.collection.objects.link(source)

        for driver in [driver for driver in source.data.shape_keys.animation_data.drivers]:
            source.data.shape_keys.animation_data.drivers.remove(driver)

        targets = [obj for obj in context.selected_objects if obj != context.active_object and obj != source]
        if not targets:
            bpy.data.objects.remove(source)
            self.report({'WARNING'}, 'No cloth object in selected objects')   
            return {'FINISHED'}
        org_target = targets[0]
        
        distance_dict  = self.build_distance_dict(source, org_target)
        self.save_distance_dict(distance_dict)

        target = org_target.copy()
        target.data = target.data.copy()
        bpy.context.scene.collection.objects.link(target)

        sk = target.shape_key_add(name = 'Basis')
        sk.interpolation = 'KEY_LINEAR'

        if sett.shapekey_calc_type == 'pants':
            shapekey_list.extend(['cor_LegFrontRaise_Rt', 'cor_LegFrontRaise_Lt', 'cor_FootDown_Lt', 'cor_FootDown_Rt'])
        elif sett.shapekey_calc_type == 'top':
            shapekey_list.extend(['cor_ElbowBend_Lt', 'cor_ElbowBend_Rt', 'cor_ShoulderSideRaise_Lt', 'cor_ShoulderSideRaise_Rt', 'cor_ShoulderFrontRaise_Lt', 'cor_ShoulderFrontRaise_Rt'])
        elif sett.shapekey_calc_type == 'shoe':
            shapekey_list.extend(['cor_FootDown_Lt', 'cor_FootDown_Rt'])

        #### Create shapekeys specific to clothing type
        for sk_name in shapekey_list:
            sk = source.data.shape_keys.key_blocks[sk_name]
            sk.mute = False
            sk.value = 1
            self.create_shapekey_from_difference(sk_name, distance_dict, source, target)
            sk.mute = True

    def save_distance_dict(self, distance_dict):
        json_string = json.dumps(distance_dict, indent = 4)
        text_file = bpy.data.texts.new('hg_cloth_distance_dict')
        text_file.from_string(json_string)        

#REMOVE
class HG_SHAPEKEY_CALCULATOR(bpy.types.Operator):
    """
    Calculates correct shapekeys for proportion changes
    """
    bl_idname = "hg3d.skcalc"
    bl_label = "Calc"
    bl_description = "Generates specified amount of humans"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll (cls, context):
        return context.object

    def execute(self,context):
        sett = context.scene.HG3D
        
        if not context.active_object.parent or not context.active_object.parent.HG.ishuman:
            self.report({'WARNING'}, 'Active object is not a HumGen body object')
            return {'FINISHED'}
        
        source = bpy.context.active_object.copy()
        source.data = source.data.copy()
        bpy.context.scene.collection.objects.link(source)

        remove_list = [driver for driver in source.data.shape_keys.animation_data.drivers]
        for driver in remove_list:
            source.data.shape_keys.animation_data.drivers.remove(driver)

        targets = [obj for obj in context.selected_objects if obj != context.active_object and obj != source]
        if not targets:
            bpy.data.objects.remove(source)
            self.report({'WARNING'}, 'No cloth object in selected objects')   
            return {'FINISHED'}
        org_target = targets[0]
        distance_dict  = self.build_distance_dict(source, org_target)

        context.view_layer.objects.active = source

        sks = context.active_object.data.shape_keys.key_blocks

        #hacky way of handling the genders
        if sett.calc_gender:
            genders = ['female', 'male'] if sks['Male'].mute == True else ['male', 'female']
        elif sks['Male'].mute == True:
            genders = ['female'] 
        else:
            genders = ['male'] 

        #iterate to make two separate meshes for both genders
        for idx, gender in enumerate(genders):
            target = org_target.copy()
            target.data = target.data.copy()
            bpy.context.scene.collection.objects.link(target)
            
            shapekey_list = [
                '{}_Skinny'.format(gender.capitalize()),
                '{}_Muscular'.format(gender.capitalize()),
                '{}_Overweight'.format(gender.capitalize()),
            ]

            if sett.shapekey_calc_type == 'pants':
                shapekey_list.extend(['cor_LegFrontRaise_Rt', 'cor_LegFrontRaise_Lt', 'cor_FootDown_Lt', 'cor_FootDown_Rt'])
            elif sett.shapekey_calc_type == 'top':
                shapekey_list.extend(['cor_ElbowBend_Lt', 'cor_ElbowBend_Rt', 'cor_ShoulderSideRaise_Lt', 'cor_ShoulderSideRaise_Rt', 'cor_ShoulderFrontRaise_Lt', 'cor_ShoulderFrontRaise_Rt'])
            elif sett.shapekey_calc_type == 'shoe':
                shapekey_list.extend(['cor_FootDown_Lt', 'cor_FootDown_Rt'])
           
            #### Create basis shapekey
            context.view_layer.objects.active = source
            sks = source.data.shape_keys.key_blocks
            if idx > 0:
                sks['Male'].mute = False if gender == 'male' else True
                for i in range(3):
                    update_length(context, True)
            else:
                for i in range(3):
                    update_length(context, True)
            self.update_pose_dimensions(context, source)
            context.view_layer.objects.active = source
            context.scene.HG3D.chest_size  = 0
            self.deform_obj_from_difference('Basis', distance_dict, source, target)

            #### Create shapekeys specific to clothing type
            for sk_name in shapekey_list:
                sk = source.data.shape_keys.key_blocks[sk_name]
                sk.mute = False
                sk.value = 1
                self.deform_obj_from_difference(sk_name, distance_dict, source, target)
                sk.mute = True

            #### Create shapekey for length
            context.view_layer.objects.active = source
            for i in range(9):
                update_length(context, False)
            self.update_pose_dimensions(context, source)
            self.deform_obj_from_difference('Shorten', distance_dict, source, target)
            
            #### Create shapekey for chest size
            context.view_layer.objects.active = source
            for i in range(9):
                update_length(context, True)
            self.update_pose_dimensions(context, source)
            if sett.shapekey_calc_type == 'top':
                context.scene.HG3D.chest_size  = 1
                self.deform_obj_from_difference('Chest', distance_dict, source, target)

            #### Revert human to default 1.84m length
            context.view_layer.objects.active = source
            for i in range(3):
                update_length(context, False)
            self.update_pose_dimensions(context, source)

            if sett.calc_gender:
                target.name += '_{}'.format(gender.capitalize())
            
        if not '_Original_Cloth' in org_target.name:
            org_target.name += '_Original_Cloth'
        
        bpy.data.objects.remove(source)

        return {'FINISHED'}
   
    def update_pose_dimensions(self, context, source):
        context.view_layer.objects.active = source.parent
        bpy.ops.object.mode_set(mode='POSE')
        bpy.ops.object.mode_set(mode='OBJECT')
        context.view_layer.objects.active = source

    def invoke (self, context, event):
        #Show a message box asking the user if they did the necessary steps
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.label(text= 'Have you transfered weights already?')
        self.layout.label(text= 'Is your cloth UV unwrapped?')
        self.layout.label(text= 'If not, do that first')

    #TODO keep
    def build_distance_dict(self, source_org, target, apply = True):
        """
        Returns a dict with a key for each vertex of the source and the value the closest vertex of the target and the distance to it
        """        
        source = source_org.copy()
        source.data = source.data.copy()
        bpy.context.scene.collection.objects.link(source)
        
        apply_shapekeys(source)
        hg_rig = find_human(bpy.context.object)
        if apply:
            apply_armature(hg_rig, source)

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
    def deform_obj_from_difference(self, name, distance_dict, source, target, as_shapekey = True):
        """
        Creates a shapekey from the difference between the distance_dict value and the current distance to that corresponding vertex
        """
        source_copy = source.copy()
        source_copy.data = source_copy.data.copy()
        bpy.context.scene.collection.objects.link(source_copy)
        apply_shapekeys(source_copy)
        hg_rig = find_human(bpy.context.object)
        #apply_armature(hg_rig, source_copy)

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
            distance_to_vert = distance_dict[vertex_index][1]
            world_new_loc = source_new_vert_loc - distance_to_vert
            if vertex_index == 24:
                print('test', world_new_loc, distance_to_vert)

            if sk:
                sk.data[vertex_index].co = target.matrix_world.inverted() @ world_new_loc
            else:
                target.data.vertices[vertex_index].co = target.matrix_world.inverted() @ world_new_loc

        bpy.data.objects.remove(source_copy)

#keep
class HG_MASK_PROP(bpy.types.Operator):
    """
    Adds a custom property to the object indicating what mesh mask should be added to the human for this cloth
    """
    bl_idname = "hg3d.maskprop"
    bl_label = "Add"
    bl_description = "Adds a custom prop with the name of the mask"
    bl_options = {"UNDO"}
 
    def execute(self, context):
        obj = context.object
        mask_name = context.scene.HG3D.dev_mask_name
        for i in range(10):
            try:
                mask = obj['mask_{}'.format(i)]
                continue
            except:
                obj['mask_{}'.format(i)] = 'mask_{}'.format(mask_name)
                break
    
        return {'FINISHED'}

#keep
class HG_DELETE_STRETCH(bpy.types.Operator):
    """
    Deletes stretch bones from this human
    """
    bl_idname = "hg3d.delstretch"
    bl_label = "Remove stretch bones"
    bl_description = "Removes all stretch bones"
    bl_options = {"UNDO"}
 
    def execute(self, context):
        hg_rig = find_human(context.object)
        if not hg_rig:
            self.report({'WARNING'}, 'No human selected')
            return {'FINISHED'}
        
        hg_body = hg_rig.HG.body_obj
        
        remove_list = [driver for driver in hg_body.data.shape_keys.animation_data.drivers]

        for driver in remove_list:
            hg_body.data.shape_keys.animation_data.drivers.remove(driver)

        remove_stretch_bones(hg_rig)

        return {'FINISHED'}

#REMOVE
class HG_MAKE_HAIR_JSON(bpy.types.Operator):
    """
    Creates a json file that states which file the hair systems are in and what hair systems should be imported including their steps, children count and length
    """
    bl_idname = "hg3d.hairjson"
    bl_label = "Make Hair JSON"
    bl_description = "Makes json for hair"
    bl_options = {"UNDO"}
 
    def execute(self, context):
        sett = context.scene.HG3D
        hair_obj = context.object
        if not hair_obj:
            self.report({'WARNING'}, 'no active object')
            return {'FINISHED'}

        filepath = sett.hair_json_path
        filename = sett.hair_json_name

        try:
            blend_name = bpy.path.basename(bpy.context.blend_data.filepath)
        except:
            self.report({'WARNING'}, 'this file is not saved, or the path could not be found')
            return {'FINISHED'}
        
        ps_dict = {}

        for mod in hair_obj.modifiers:
            if mod.type == 'PARTICLE_SYSTEM' and mod.show_viewport:
                ps = mod.particle_system
                ps_length = ps.settings.child_length
                ps_children = ps.settings.child_nbr
                ps_steps = ps.settings.display_step
                ps_dict[ps.name]= {"length": ps_length, "children_amount": ps_children, "path_steps": ps_steps}

        if len(ps_dict) == 0:
            self.report({'WARNING'}, 'no hair systems that are visible')
            return {'FINISHED'}            

        json_data = {"blend_file": blend_name, "hair_systems": ps_dict}
        #data = json.loads(json_string)

        full_path = filepath + str(Path('/{}.json'.format(filename)))
        with open(full_path, 'w') as f:
            json.dump(json_data, f, indent = 4)

        return {'FINISHED'}