"""
Operators not related to any particular section
"""

import bpy

from ...core.HG_PCOLL import refresh_pcoll
from ...user_interface.HG_TIPS_SUGGESTIONS_UI import \
    update_tips_from_context  # type: ignore
from .HG_COMMON_FUNC import (find_human, get_prefs, hg_delete, hg_log,
                             is_batch_result)
from .HG_INFO_POPUPS import HG_OT_INFO


class HG_DESELECT(bpy.types.Operator):
    """
    Sets the active object as none
    
    Operator Type: 
        Selection 
        HumGen UI manipulation
    
    Prereq:
        -Human selected
    """
    bl_idname      = "hg3d.deselect"
    bl_label       = "Deselect"
    bl_description = "Deselects active object"
    bl_options     = {"REGISTER", "UNDO"}

    def execute(self,context):
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        
        context.view_layer.objects.active = None
        return {'FINISHED'}

class HG_SECTION_TOGGLE(bpy.types.Operator):
    """
    Section tabs, pressing it will make that section the open/active one, 
    closing any other opened sections
    
    API: False
    
    Operator Type: 
        HumGen UI manipulation
    
    Args:
        section_name (str): name of the section to toggle
    """
    bl_idname      = "hg3d.section_toggle"
    bl_label       = ""
    bl_description = """
        Open this menu
        CTRL+Click to keep hair children turned on
        """

    section_name: bpy.props.StringProperty()

    def invoke(self, context, event):
        self.children_hide_exception = event.ctrl
        return self.execute(context)

    def execute(self,context):
        sett = context.scene.HG3D
        sett.ui_phase = 'closed' if sett.ui_phase == self.section_name else self.section_name
        #PCOLL add here
        categ_dict = {
            'clothing': ('outfit',),
            'footwear': ('footwear',),
            'pose': ('poses',),
            'hair': ('hair', 'face_hair'),
            'expression': ('expressions',)
        }
        
        if not any(is_batch_result(context.object)):
            if self.section_name in categ_dict:
                for item in categ_dict[self.section_name]:
                    refresh_pcoll(self, context, item)
        
        pref = get_prefs()
        if pref.auto_hide_hair_switch and not self.children_hide_exception:
            if not self.section_name in ('hair', 'eyes'):
                self._hide_hair_children(context, pref)
        return {'FINISHED'}

    def _hide_hair_children(self, context, pref):
        """Hides hair children to improve viewport performance

        Args:
            pref (AddonPreferences): HumGen preferences
        """
        mods = find_human(context.object).HG.body_obj.modifiers
        for mod in [m for m in mods if m.type == 'PARTICLE_SYSTEM']:
            ps_sett = mod.particle_system.settings
            if ps_sett.child_nbr <= 1:
                continue
                
            ps_sett.child_nbr = 1
            self.report(
                {'INFO'},
                'Hair children were hidden to improve performance.'
            )
            
            if pref.auto_hide_popup:
                HG_OT_INFO.ShowMessageBox(None, 'autohide_hair')

class HG_NEXT_PREV_HUMAN(bpy.types.Operator):
    """Zooms in on next or previous human in the scene

    Operator Type:
        Selection
        VIEW 3D (zoom)

    Args:
        forward (bool): True if go to next, False if go to previous
    
    Prereq:
        Humans in scene
    """
    
    bl_idname      = "hg3d.next_prev_human"
    bl_label       = "Next/Previous"
    bl_description = "Goes to the next human"
    bl_options     = {"UNDO"}

    forward : bpy.props.BoolProperty(name = '', default = False)

    def execute(self,context):
        forward = self.forward
        
        for obj in bpy.context.selected_objects:
            obj.select_set(False)

        humans = []
        for obj in context.scene.objects: #CHECK if works
            if obj.HG.ishuman and not 'backup' in obj.name.lower():
                humans.append(obj)

        if len(humans) == 0:
            self.report({'INFO'}, "No Humans in this scene")
            return {'FINISHED'}
         
        hg_rig = find_human(context.active_object)
        
        index = humans.index(hg_rig) if hg_rig in humans else 0
  
        if forward:
            if index + 1 < len(humans):
                next_index = index + 1
            else:
                next_index = 0
        else:
            if index - 1 >= 0:
                next_index = index - 1
            else:
                next_index = len(humans) -1

        next_human = humans[next_index]
        
        context.view_layer.objects.active = next_human
        next_human.select_set(True)
        
        bpy.ops.view3d.view_selected()
        
        return {'FINISHED'}

class HG_OPENPREF(bpy.types.Operator):
    """Opens the preferences. 
    
    API: False
    
    Operator type:
        Blender UI manipulation
        
    Prereq:
        None
    """
    bl_idname = "hg3d.openpref"
    bl_label = ""
    bl_description = "Opens the preferences window"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self,context):
        old_area    = bpy.context.area
        old_ui_type = old_area.ui_type
        
        bpy.context.area.ui_type                 = 'PREFERENCES'
        bpy.context.preferences.active_section   = 'ADDONS'
        bpy.context.window_manager.addon_support = {'COMMUNITY'}
        bpy.context.window_manager.addon_search  = 'Human Generator 3D'
        
        bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
        old_area.ui_type = old_ui_type    
        return {'FINISHED'}

class HG_DELETE(bpy.types.Operator):
    """
    Deletes the active human, including it's backup human if it's not in use by 
    any other humans
    
    Operator type:
        Object deletion
    
    Prereq:
        Active object is part of HumGen human
    """
    bl_idname      = "hg3d.delete"
    bl_label       = "Delete Human"
    bl_description = "Deletes human and all objects associated with the human"
    bl_options     = {"UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self,context):
        hg_rig = find_human(context.active_object)
        if not hg_rig:
            self.report({'INFO'}, 'No human selected')
            return {'FINISHED'}

        backup_obj = hg_rig.HG.backup
        humans = [obj for obj in bpy.data.objects if obj.HG.ishuman]
        
        copied_humans = [human for human in humans
                         if human.HG.backup == backup_obj 
                         and human != hg_rig
                         ]

        delete_list = [hg_rig,]
        for child in hg_rig.children:
            delete_list.append(child)
            for sub_child in child.children:
                delete_list.append(sub_child)
        
        if not copied_humans and backup_obj:
            delete_list.append(backup_obj)
            for child in backup_obj.children:
                delete_list.append(child)
        
        for obj in delete_list:
            try:
                hg_delete(obj)
            except:
                hg_log('could not remove', obj)
                
        return {'FINISHED'}


class HG_CLEAR_SEARCH(bpy.types.Operator):
    """Clears the passed searchfield
    
    API: False
    
    Operator type:
        Preview collection manipulation
        
    Prereq:
        None
    
    Args:
        pcoll_type (str): Name of preview collection to clear the searchbox for
    """
    bl_idname      = "hg3d.clear_searchbox"
    bl_label       = "Clear search"
    bl_description = "Clears the searchbox"

    searchbox_name: bpy.props.StringProperty()

    def execute(self,context):
        sett = context.scene.HG3D
        if self.searchbox_name == 'cpack_creator':
            get_prefs().cpack_content_search = ''
        else:
            sett['search_term_{}'.format(self.searchbox_name)] = ''
            refresh_pcoll(self, context, self.searchbox_name)

        return {'FINISHED'}

class HG_NEXTPREV_CONTENT_SAVING_TAB(bpy.types.Operator):

    bl_idname      = "hg3d.nextprev_content_saving_tab"
    bl_label       = "Next/previous"
    bl_description = "Next/previous tab"

    next: bpy.props.BoolProperty()

    def execute(self,context):
        sett = context.scene.HG3D
        
        
        if (self.next 
            and sett.content_saving_type == 'mesh_to_cloth' 
            and sett.content_saving_tab_index >= 1):
            not_in_a_pose = self.check_if_in_A_pose(context, sett)
            
            if not_in_a_pose:
                sett.mtc_not_in_a_pose = True
                
        sett.content_saving_tab_index += 1 if self.next else -1
        
        update_tips_from_context(
            context,
            sett,
            sett.content_saving_active_human
        )
        
        return {'FINISHED'}

    def check_if_in_A_pose(self, context, sett):
        hg_rig = sett.content_saving_active_human
        context.view_layer.objects.active = hg_rig
        hg_rig.select_set(True)
        bpy.ops.object.mode_set(mode='POSE')
        
        important_bone_suffixes = (
            'forearm',
            'upper',
            'spine',
            'shoulder',
            'neck',
            'head',
            'thigh',
            'shin',
            'foot',
            'toe',
            'hand',
            'breast'
        )
        
        not_in_a_pose = False
        for bone in hg_rig.pose.bones:
            if not bone.name.startswith(important_bone_suffixes):
                continue
            for i in range(1, 4):
                if bone.rotation_quaternion[i]:
                    not_in_a_pose = True
        
        bpy.ops.object.mode_set(mode='OBJECT')
        
        return not_in_a_pose
