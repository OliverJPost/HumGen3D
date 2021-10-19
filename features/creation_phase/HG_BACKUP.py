import bpy  # type: ignore

from ...features.common.HG_COMMON_FUNC import (add_to_collection, find_human,
                                               hg_delete)


class HG_REVERT_TO_CREATION(bpy.types.Operator):
    """
    Reverts to creation phase by deleting the current human and making the 
    corresponding backup human the active human
    
    Operator Type:
        HumGen phase change
        Object deletion
        
    Prereq:
        Active object is part of finalize phase
    """
    bl_idname = "hg3d.revert"
    bl_label = "Revert: ALL changes made after creation phase will be discarded. This may break copied version of this human"
    bl_description = "Revert to the creation phase. This discards any changes made after the creation phase"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        #confirmation checkbox
        return context.window_manager.invoke_confirm(self, event)

    def execute(self,context):
        hg_rig    = find_human(context.active_object)
        hg_backup = hg_rig.HG.backup
        children  = [child for child in hg_rig.children]

        #remove current human, including all children of the current human
        for child in children:
            hg_delete(child)
        hg_delete(hg_rig)
        
        #backup human: rename, make visible, add to collection
        hg_backup.name          = hg_backup.name.replace('_Backup', '')
        hg_backup.hide_viewport = False
        hg_backup.hide_render   = False
        add_to_collection(context, hg_backup)
        
        #backup children: set correct body_obj property, add to collection, make visible
        hg_body = None
        for child in hg_backup.children:
            if 'hg_body' in child:
                hg_backup.HG.body_obj = child
                hg_body = child
            add_to_collection(context, child)
            child.hide_viewport = False
            child.hide_render   = False

        #point constraints to the correct rig
        p_bones= hg_backup.pose.bones
        for bone in [p_bones['jaw'], p_bones['jaw_upper']]:
            child_constraints = [c for c in bone.constraints
                                 if c.type == 'CHILD_OF' 
                                 or c.type == 'DAMPED_TRACK'
                                 ]
            for c in child_constraints:
                c.target = hg_body

        context.view_layer.objects.active = hg_backup

        return {'FINISHED'}

