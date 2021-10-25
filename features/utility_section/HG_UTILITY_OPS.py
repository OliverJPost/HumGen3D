"""
Operators and functions for experimental features and QoL automations
"""

from pathlib import Path

import bpy  # type: ignore

from ...features.common.HG_COMMON_FUNC import (apply_shapekeys, find_human,
                                               get_prefs, hg_log, show_message)
from ...features.common.HG_INFO_POPUPS import HG_OT_INFO
from ...features.creation_phase.HG_FINISH_CREATION_PHASE import (
    extract_shapekeys_to_keep, reapply_shapekeys)
from .HG_UTILITY_FUNC import (build_object_list, refresh_hair_ul,
                              refresh_modapply, refresh_outfit_ul,
                              refresh_shapekeys_ul)


class HG_MAKE_EXPERIMENTAL(bpy.types.Operator):
    """
    Makes human experimental, loosening limits on shapekeys and sliders
    """
    bl_idname      = "hg3d.experimental"
    bl_label       = "Make human experimental"
    bl_description = "Makes human experimental, loosening limits on shapekeys and sliders"
    bl_options     = {"UNDO"}

    def execute(self,context):        
        hg_rig = find_human(context.active_object)
        HG = hg_rig.HG
        hg_body = hg_rig.HG.body_obj

        is_experimental = HG.experimental

        s_max    =  1 if is_experimental else  2
        s_min_ff = -1 if is_experimental else -2
        s_min_bd =  0 if is_experimental else -.5

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

class HG_OT_MODAPPLY(bpy.types.Operator):
    bl_idname      = "hg3d.modapply"
    bl_label       = "Apply selected modifiers"
    bl_description = "Apply selected modifiers"
    bl_options     = {"UNDO"}

    def execute(self,context):        
        sett = context.scene.HG3D
        col = context.scene.modapply_col

        objs = build_object_list(context, sett)

        sk_dict = {}
        driver_dict = {}

        for obj in objs:
            if sett.modapply_keep_shapekeys:
                sk_dict, driver_dict = self.copy_shapekeys(context, col, sk_dict, driver_dict, obj)
            apply_shapekeys(obj)
        
        objs_to_apply = objs.copy()
        for sk_list in sk_dict.values():
            if sk_list:
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
        pref = get_prefs()
        #TODO this is kind of weird
        keep_sk_pref = pref.keep_all_shapekeys
        pref.keep_all_shapekeys = True
        sk_dict[obj.name], driver_dict[obj.name] = extract_shapekeys_to_keep(context, obj, apply_armature = apply)
        pref.keep_all_shapekeys = keep_sk_pref
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
                    hg_log(f'Error while applying modifier {item.mod_name} on {item.object}, with error as {e}', level = 'WARNING')

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
                hg_log(f'Error while applying modifier {mod.name} on {obj.name}, with error as {e}', level = 'WARNING')

class HG_OT_REFRESH_UL(bpy.types.Operator):
    bl_idname      = "hg3d.ulrefresh"
    bl_label       = "Refresh list"
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
    bl_idname      = "hg3d.selectmodapply"
    bl_label       = "Select all/none modifiers"
    bl_description = "Select all/none modifiers"
    bl_options     = {"UNDO"}

    all: bpy.props.BoolProperty()

    def execute(self,context):        
        col = context.scene.modapply_col

        refresh_modapply(self, context)

        for item in col:
            item.enabled = self.all

        return {'FINISHED'}

class HG_OT_PREPARE_FOR_ARKIT(bpy.types.Operator):
    bl_idname      = "hg3d.prepare_for_arkit"
    bl_label       = "Prepare for ARKit"
    bl_description = "Removes drivers and adds single keyframe to all FACS shapekeys"
    bl_options     = {"UNDO"}

    suffix: bpy.props.EnumProperty(
        name = 'Shapekey suffix',
        items = [
            ('long', 'Left and Right (Default ARKit)', '', 0),
            ('short', '_L and _R (FaceApp)', '', 1)
        ]
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "suffix", text = 'Suffix')

    def execute(self,context):        
        hg_rig = find_human(context.object)
        hg_body = hg_rig.HG.body_obj
        
        for sk in hg_body.data.shape_keys.key_blocks[:]:
            if sk.name == 'Basis' or sk.name.startswith('cor_'):
                continue
            sk.driver_remove("value")
            sk.keyframe_insert("value", frame=0)
            if self.suffix == 'long' and sk.name.endswith(('_L', '_R')):
                sk.name = sk.name.replace('_L', 'Left').replace('_R', 'Right')
        
        show_message(self, 'Succesfully removed drivers and added keyframes')
        return {'FINISHED'}
        

