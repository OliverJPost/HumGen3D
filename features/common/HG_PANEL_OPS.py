"""
Operators used in the main panel, not related to any particular section
"""

import bpy #type: ignore
from . HG_COMMON_FUNC import ShowMessageBox, find_human, get_prefs
from ... core.HG_PCOLL import refresh_pcoll
from . HG_INFO_POPUPS import HG_OT_INFO
import os

class HG_DESELECT(bpy.types.Operator):
    """
    sets the active object as none
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

class HG_UITOGGLE(bpy.types.Operator):
    """
    section buttons, pressing it will make that section the active one, closing any other opened sections
    """
    bl_idname      = "hg3d.uitoggle"
    bl_label       = ""
    bl_description = """
        Open this menu
        CTRL+Click to keep hair children turned on
        """

    categ: bpy.props.StringProperty()

    def execute(self,context):
        sett = context.scene.HG3D
        sett.ui_phase = 'closed' if sett.ui_phase == self.categ else self.categ
        categ_dict = {'clothing': ('outfit',),'footwear': ('footwear',), 'pose': ('poses',), 'hair': ('hair', 'face_hair'), 'expression': ('expressions',)}
        if self.categ in categ_dict:
            for item in categ_dict[self.categ]:
                 refresh_pcoll(self, context, item)
        
        pref = get_prefs()
        if pref.auto_hide_hair_switch and not self.keep_hair:
            for mod in find_human(context.object).HG.body_obj.modifiers:
                if mod.type == 'PARTICLE_SYSTEM':
                    ps_sett = mod.particle_system.settings
                    if ps_sett.child_nbr > 1:
                        ps_sett.child_nbr = 1 #put in try except 
                        self.report({'INFO'}, 'Hair children were hidden to improve performance. This can be turned off in preferences')
                        if pref.auto_hide_popup:
                            HG_OT_INFO.ShowMessageBox(None, 'autohide_hair')


        return {'FINISHED'}

    def invoke(self, context, event):
        self.keep_hair = event.ctrl
        return self.execute(context)
        

class HG_NEXTPREV(bpy.types.Operator):
    """
    Zooms in on next or previous human in the scene
    """
    bl_idname      = "hg3d.nextprev"
    bl_label       = "Deselect"
    bl_description = "Deselects active object"
    bl_options     = {"REGISTER", "UNDO"}

    forward : bpy.props.BoolProperty(name = '', default = False)

    def execute(self,context):
        forward = self.forward
        
        for obj in bpy.context.selected_objects:
            obj.select_set(False)

        humans = []
        for obj in bpy.data.objects:
            if obj.HG.ishuman and not 'backup' in obj.name.lower():
                humans.append(obj)

        if len(humans) == 0:
            self.report({'INFO'}, "No Humans in this scene")
            return {'FINISHED'}
        
        index = 0
        hg_rig = find_human(context.active_object)
        if hg_rig in humans:
            index = humans.index(hg_rig)

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
    """
    Opens the preferences. 
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
    Deletes the active human, including it's backup human if it's not in use by any other humans
    """
    bl_idname      = "hg3d.delete"
    bl_label       = "Delete Human"
    bl_description = "Deletes human and all objects associated with the human"
    bl_options     = {"REGISTER", "UNDO"}

    def execute(self,context):
        hg_rig = find_human(context.active_object)
        if not hg_rig:
            self.report({'INFO'}, 'No human selected')
            return {'FINISHED'}

        backup_obj = hg_rig.HG.backup
        humans = [obj for obj in bpy.data.objects if obj.HG.ishuman]
        copied_humans = [human for human in humans if human.HG.backup == backup_obj and human != hg_rig]

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
                bpy.data.objects.remove(obj)
            except:
                print('could not remove', obj)
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

class HG_CLEAR_SEARCH(bpy.types.Operator):
    """
    clears searchfield
    """
    bl_idname      = "hg3d.clearsearch"
    bl_label       = "Clear search"
    bl_description = "Clears the searchbox"

    categ: bpy.props.StringProperty()

    def execute(self,context):
        sett = context.scene.HG3D
        
        sett['search_term_{}'.format(self.categ)] = ''
        refresh_pcoll(self, context, self.categ)

        return {'FINISHED'}

