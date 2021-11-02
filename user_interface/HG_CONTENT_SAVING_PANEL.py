import bpy

from ..core.HG_PCOLL import preview_collections
from ..features.common.HG_COMMON_FUNC import find_human, hg_log
from ..features.utility_section.HG_UTILITY_FUNC import (refresh_hair_ul,
                                                        refresh_outfit_ul,
                                                        refresh_shapekeys_ul)
from ..user_interface.HG_UTILITY_PANEL import Tools_PT_Base


class HG_OT_CANCEL_CONTENT_SAVING_UI(bpy.types.Operator):
    bl_idname      = "hg3d.cancel_content_saving_ui"
    bl_label       = "Cancel saving operation"
    bl_description = 'Cancel saving operation'
    bl_options     = {"UNDO"}

    def invoke(self, context, event):
        #confirmation checkbox
        return context.window_manager.invoke_confirm(self, event)

    def execute(self,context):
        sett = context.scene.HG3D
        sett.content_saving_ui = False
        return {'FINISHED'}
    
class HG_OT_OPEN_CONTENT_SAVING_TAB(bpy.types.Operator):
    bl_idname      = "hg3d.open_content_saving_tab"
    bl_label       = "Save custom content"
    bl_description = "Opens the screen to save custom content"

    content_type: bpy.props.StringProperty()

    def execute(self,context):  
        sett = context.scene.HG3D
        
        hg_rig = find_human(context.object)

        if self.content_type   == 'shapekeys':
            refresh_shapekeys_ul(self, context)
        elif self.content_type   == 'hair':
            refresh_hair_ul(self, context)
        elif self.content_type   == 'clothing':
            refresh_outfit_ul(self, context)

        sett.content_saving_ui = True
        sett.content_saving_type = self.content_type  
        sett.content_saving_tab_index = 0  
        sett.content_saving_active_human = hg_rig
        return {'FINISHED'}

class HG_PT_CONTENT_SAVING(Tools_PT_Base, bpy.types.Panel): 
    """Panel with extra functionality for HumGen that is not suitable for the 
    main panel. Things like content pack creation, texture baking etc.

    Args:
        Tools_PT_Base (class): Adds bl_info and commonly used tools
    """
    bl_idname = "HG_PT_CONTENT_SAVING"
    bl_label  = " Content Saving"

    @classmethod
    def poll(cls, context):
        return context.scene.HG3D.content_saving_ui

    def draw_header(self, context):
        row = self.layout.row()
        row.alert = True
        row.operator('hg3d.cancel_content_saving_ui', text = 'Cancel', icon = 'X')

    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D
        self.sett = sett
        
        content_type = sett.content_saving_type

        tab_idx = sett.content_saving_tab_index

        self._draw_warning_if_different_active_human(context, layout)
        
        if content_type == 'hair':
            if tab_idx == 0:
                self._draw_particle_system_selection_ui(context, layout)
            elif tab_idx == 1:
                self._draw_thumbnail_selection_ui(context, layout, content_type)
            elif tab_idx == 2:
                self._draw_hairtype_ui(context, layout)  
            elif tab_idx == 3:
                self._draw_hair_gender_ui(context, layout)
            else:
                self._draw_name_ui(context, layout, content_type)
        elif content_type == 'starting_human':
            if tab_idx == 0:
                self._draw_thumbnail_selection_ui(context, layout, content_type)
            elif tab_idx == 1:
                self._draw_name_ui(context, layout, content_type)
        elif content_type == 'shapekeys':
            if tab_idx == 0:
                self._draw_shapekey_selection_ui(context, layout)
            elif tab_idx == 1:
                self._draw_name_ui(context, layout, content_type)
        elif content_type == 'clothing':
            if tab_idx == 0:
                self._draw_outfit_type_selector(context, layout)
            elif tab_idx == 1:
                self._draw_clothing_uilist_ui(context, layout)
            elif tab_idx == 2:
                self._draw_thumbnail_selection_ui(context, layout, content_type)
            elif tab_idx == 3:
                self._draw_clothing_gender_ui(context, layout)
            elif tab_idx == 4:
                self._draw_name_ui(context, layout, content_type)
    
    def _draw_clothing_gender_ui(self, context, layout):
        self._draw_header_box(layout, "Is this clothing for men \nwomen or all genders?", 'MOD_CLOTH')
        
        col = layout.column(align = True)
        col.scale_y = 1.5
        sett = self.sett
        
        col.prop(sett, 'saveoutfit_male', text = 'Male', toggle= True)    
        col.prop(sett, 'saveoutfit_female', text = 'Female', toggle= True)      
        
        poll = any((sett.saveoutfit_male, sett.saveoutfit_female))  
        self._draw_next_button(layout, poll = poll)      
    
    def _draw_clothing_uilist_ui(self, context, layout):
        self._draw_header_box(layout, "Select which objects are \npart of this outfit.", 'MOD_CLOTH')
        
        col = layout.column(align = True)
        row = col.row(align = True)
        row.operator('hg3d.ulrefresh',
                     text = 'Refresh objects'
                     ).type = 'outfit'
        col.template_list("HG_UL_SAVEOUTFIT",
                          "",
                          context.scene,
                          "saveoutfit_col",
                          context.scene,
                          "saveoutfit_col_index"
                          )       
        
        poll = [i for i in context.scene.saveoutfit_col if i.enabled]
        self._draw_next_button(layout, poll = poll)   

    def _draw_outfit_type_selector(self, context, layout):
        self._draw_header_box(layout, "Are you saving an outfit \nor footwear?", 'MOD_CLOTH')
        
        col = layout.column()
        col.scale_y = 1.5
        col.prop(self.sett, 'saveoutfit_categ', expand = True)
        
        self._draw_next_button(layout)        

    def _draw_shapekey_selection_ui(self, context, layout):
        sett = self.sett
        self._draw_header_box(layout, "Select shapekeys to save", 'SHAPEKEY_DATA')
        
        col = layout.column(align = True)
        
        col.operator(
            'hg3d.ulrefresh',
            text = 'Refresh shapekeys'
            ).type = 'shapekeys'
        col.template_list(
            "HG_UL_SHAPEKEYS",
            "",
            context.scene,
            "shapekeys_col",
            context.scene,
            "shapekeys_col_index"
            )
        
        col.separator()
        
        col.prop(sett, 'show_saved_sks',
                 text = 'Show already saved shapekeys',
                 icon = ('CHECKBOX_HLT' 
                         if sett.show_saved_sks 
                         else 'CHECKBOX_DEHLT'))     
        
        poll = [i for i in context.scene.shapekeys_col if i.enabled]
        self._draw_next_button(layout, poll = poll)   

    def _draw_name_ui(self, context, layout, content_type):
        sett = self.sett
        
        tag_dict = {
            'hair': 'hairstyle',
            'starting_human': 'preset',
            'shapekeys': 'sk_collection',
            'clothing': 'clothing'
        }
        tag = tag_dict[content_type]
        self._draw_header_box(layout, f"Give your {tag.replace('sk_', '')} a name", 'OUTLINER_OB_FONT')
        
        col = layout.column()
        col.scale_y = 1.5
        col.prop(sett, f'{tag}_name',
                 text = 'Name'
                 )
        
        self._draw_save_button(layout, content_type, poll = bool(getattr(sett, f'{tag}_name')))
        
    def _draw_hair_gender_ui(self, context, layout):
        sett = self.sett
        
        self._draw_header_box(layout, "Is this style for men, women \nor all genders?", 'COMMUNITY')
        
        col = layout.column()
        col.scale_y = 1.5
        col.prop(sett, 'savehair_male',
                 text = 'Male',
                 toggle= True
                 )    
        subrow = col.row(align = True)
        subrow.enabled = False if sett.save_hairtype == 'facial_hair' else True  
        subrow.prop(sett, 'savehair_female',
                    text = 'Female',
                    toggle= True
                    )      
        
        poll = any((sett.savehair_male, sett.savehair_female))
        self._draw_next_button(layout, poll = poll)    
          
    def _draw_hairtype_ui(self, context, layout):
        sett = self.sett
        
        self._draw_header_box(layout, "Is this style facial hair?", 'COMMUNITY')
        
        col = layout.column()
        col.scale_y = 1.5
        col.prop(sett, 'save_hairtype', expand = True)
        
        self._draw_next_button(layout)

    def _draw_particle_system_selection_ui(self, context, layout):
        
        self._draw_header_box(layout, 'Select particle systems \nto be included in this style.', 'OUTLINER_OB_HAIR')
        
        
        col = layout.column(align = True)
        row = col.row(align = True)
        hg_icons = preview_collections['hg_icons']
        
        row.operator('hg3d.ulrefresh',
                     text = 'Refresh hairsystems'
                     ).type = 'hair'
        row.prop(self.sett, 'show_eyesystems',
                 text = '',
                 icon_value = hg_icons['eyes'].icon_id,
                 toggle = True
                 )

        col.template_list(
            "HG_UL_SAVEHAIR",
            "",
            context.scene,
            "savehair_col",
            context.scene,
            "savehair_col_index"
            )
        
        poll = [i for i in context.scene.savehair_col if i.enabled]
        self._draw_next_button(layout, poll)
        

    def _draw_thumbnail_selection_ui(self, context, layout, content_type):
        sett = self.sett
        
        self._draw_header_box(layout, 'Select a thumbnail', icon = 'IMAGE')
        
        col = layout.column(align = True)
        col.scale_y = 1.5
        col.prop(sett, 'thumbnail_saving_enum', text = '')
        
        if sett.thumbnail_saving_enum == 'none':
            row = layout.row()
            row.alignment = 'CENTER'
            row.scale_y = 3
            row.alert = True
            row.label(text = 'No thumbnail will be exported')
            self._draw_next_button(layout)
            return
        
        img = sett.preset_thumbnail
               
        layout.template_icon_view(
            sett, "preset_thumbnail_enum",
            show_labels=True,
            scale=8,
            scale_popup=10
            )   
        if sett.thumbnail_saving_enum == 'custom':
            layout.template_ID(
                sett, "preset_thumbnail",
                open="image.open"
                )
            layout.label(text = '256*256px recommended', icon = 'INFO')
        elif sett.thumbnail_saving_enum == 'auto':
            row = layout.row()
            row.scale_y = 1.5
            row.operator('hg3d.auto_render_thumbnail', text = 'Render [Automatic]', icon = 'RENDER_STILL').thumbnail_type = 'head' if content_type in ('hairstyle', 'starting_human') else 'full_body'
        elif sett.thumbnail_saving_enum == 'last_render':
            layout.label(text = '256*256px recommended', icon = 'INFO')
            layout.separator()
            layout.label(text = 'If you render does not show,', icon = 'INFO')
            layout.label(text = 'reload thumbnail category above.')
               
        self._draw_next_button(layout, poll = sett.preset_thumbnail)

    def _draw_header_box(self, layout, text, icon):
        box = layout.box()
        
        lines = text.splitlines()
        
        split = box.split(factor = 0.1)
        icon_col = split.column()
        text_col = split.column() 
        
        icon_col.scale_y = len(lines)*0.7 if len(lines) > 1 else 1
        if len(lines) > 1:
            text_col.scale_y = 0.7

        icon_col.label(text = '', icon = icon)
        
        for line in lines:
            text_col.label(text = line)

    def _draw_next_button(self, layout, poll = True):
        row = layout.row(align=True)
        row.scale_y = 1.5
        row.alert = True
        if self.sett.content_saving_tab_index > 0:
            row.operator('hg3d.nextprev_content_saving_tab', text = 'Previous', icon = 'TRIA_LEFT', depress = True).next = False
        
        if not poll:
            row = row.row(align = True)
            row.enabled = False
        row.operator('hg3d.nextprev_content_saving_tab', text = 'Next', icon = 'TRIA_RIGHT', depress = True).next = True

    def _draw_save_button(self, layout, content_type, poll = True):
        split = layout.split(factor = 0.1, align = True)
        row = split.row(align = True)
        row.scale_y = 1.5
        row.alert = True
        row.operator('hg3d.nextprev_content_saving_tab', text = '', icon = 'TRIA_LEFT', depress = True).next = False
        
        row = split.row(align=True)
        row.enabled = poll
        row.scale_y = 1.5
        row.operator(f'hg3d.save_{content_type}', text = 'Save', icon = 'FILEBROWSER', depress = True)        

    def _draw_warning_if_different_active_human(self, context, layout):
        sett = self.sett
        
        active_human = find_human(context.object)
        try:            
            if active_human and active_human != sett.content_saving_active_human:
                row = layout.row()
                row.alert = True
                row.label(text = f'Selected human is not {sett.content_saving_active_human.name}')
        except Exception as e:
            row = layout.row()
            row.alert = True
            row.label(text='Human seems to be deleted')            
            hg_log(e)
