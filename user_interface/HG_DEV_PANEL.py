import bpy #type: ignore
import os
from .. HG_COMMON_FUNC import find_human
from . HG_PANEL_FUNCTIONS import draw_panel_switch_header


class Dev_PT_Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"

    def Header (self, context):
        return True

class HG_PT_DEVTOOLS(Dev_PT_Base, bpy.types.Panel):
    bl_idname = "HG_PT_DEVTOOLS"
    bl_label = "Dev Tools"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.scene.HG3D.active_ui_tab == 'TOOLS'

    def draw_header(self, context):
        draw_panel_switch_header(self.layout, context.scene.HG3D)


    def draw(self,context):
        sett = context.scene.HG3D
        self.dev_tools(sett)
        self.layout.operator('hg3d.testop')

    def dev_tools(self, sett):
        layout = self.layout
        

class HG_PT_D_CLOTH(Dev_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_DEVTOOLS"
    bl_label = "Clothing creation"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw_header(self, context):
        if not self.Header(context):
            return
        
    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D

        layout.operator('hg3d.creatorhuman')
        layout.operator('hg3d.delstretch')
        try:
            sk = bpy.context.active_object.data.shape_keys.key_blocks['Male']
            layout.prop(sk, 'mute', text = 'Male/Female')
        except:
            pass
        row = layout.row(align = True)
        row.operator('hg3d.checkdistance', text = 'Highlight cloth distance')
        row.operator('hg3d.delempty', icon = 'TRASH')
        row = layout.row(align = True)
        row.prop(sett, 'dev_mask_name')
        row.operator('hg3d.maskprop', text = 'Add')
        layout.operator('hg3d.skcalc', text = 'Calculate cloth shapekeys')
        layout.operator('hg3d.clothcalc', text = 'V2_Calculate cloth shapekeys')
        layout.prop(sett, 'shapekey_calc_type')
        layout.prop(sett, 'calc_gender')

class HG_PT_D_POSE(Dev_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_DEVTOOLS"
    bl_label = "Pose creation"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        if not self.Header(context):
            return
        
    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D

        layout.operator('hg3d.purge', text = 'Hard purge .blend file')
        layout.prop(sett, 'dev_delete_unselected')

class HG_PT_D_HAIR(Dev_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_DEVTOOLS"
    bl_label = "Hair creation"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        if not self.Header(context):
            return
        
    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D
        layout.prop(sett, 'hair_json_path', text = 'save path')
        layout.prop(sett, 'hair_json_name', text = 'filename')
        layout.operator('hg3d.hairjson', text = 'Generate hair json')

class HG_PT_D_THUMB(Dev_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_DEVTOOLS"
    bl_label = "Thumbnail creation"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        if not self.Header(context):
            return
        
    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D
        layout.operator('hg3d.renderthumbs', text = 'Render thumbnails')
        layout.prop(sett, 'pcoll_render', text = 'Pcoll')
        layout.prop(sett, 'thumb_render_path', text = 'Save path')
