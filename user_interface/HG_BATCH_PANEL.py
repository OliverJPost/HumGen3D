"""
This file is currently inactive
"""

import bpy
import numpy as np

from ..core.HG_PCOLL import get_hg_icon, preview_collections
from ..features.batch_section.HG_BATCH_FUNC import (calculate_batch_statistics,
                                                    length_from_bell_curve)
from ..features.batch_section.HG_BATCH_MODAL_OPERATOR import \
    get_batch_marker_list
from ..features.common.HG_COMMON_FUNC import get_prefs  # type: ignore
from ..user_interface.HG_TIPS_SUGGESTIONS_UI import draw_tips_suggestions_ui
from .HG_PANEL_FUNCTIONS import (draw_panel_switch_header, draw_resolution_box,
                                 get_flow)


class Batch_PT_Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"

    def Header (self, context):
        return True

class HG_PT_BATCH_Panel(Batch_PT_Base, bpy.types.Panel):
    bl_idname = "HG_PT_Batch_Panel"
    bl_label = "Batch Mode" #tab name

    @classmethod
    def poll(cls, context):
        sett = context.scene.HG3D
        return sett.active_ui_tab == 'BATCH' and not sett.content_saving_ui
    
    def draw_header(self, context):
        draw_panel_switch_header(self.layout, context.scene.HG3D)

    def draw(self,context):
        layout=self.layout
        sett = context.scene.HG3D

        col = layout.column(align = True)
        col.scale_y = 1.5
        col.prop(sett, 'batch_marker_selection', text = '')
        
        marker_total = len(get_batch_marker_list(context))
        
        col = col.column(align = True)
        if sett.batch_idx:
            col.prop(sett, 'batch_progress', text=f'Building Human {sett.batch_idx}')
        else: 
            col.alert = True
            col.operator('hg3d.generate', text = f'Generate {marker_total} humans', depress = True, icon  = 'TIME').run_immediately = False
              
        box = layout.box().column(align = True)
        box.prop(
            sett,
            'batch_performance_statistics',
            text='Performance statistics:',
            emboss = False,
            icon="TRIA_DOWN" if sett.batch_performance_statistics else "TRIA_RIGHT"
        )
        if sett.batch_performance_statistics:
            box.separator()
            row = box.row()
            row.alignment = 'CENTER'
            row.label(text = 'Lower is better', icon = 'INFO')
            box.separator()
            split = box.split(factor = 0.25)
            split.scale_y = 0.8
            col_l = split.column(align = True)
            col_r = split.column(align = True)
            
            weight_dict = calculate_batch_statistics(sett)
            
            col_l.label(text = 'Cycles:')
            col_r.label(text = weight_dict['cycles_time'], icon = 'RENDER_STILL')
            col_l.label(text = '')
            col_r.label(text = weight_dict['cycles_memory'], icon = 'BLANK1')
            col_l.label(text = 'Eevee:')
            col_r.label(text = weight_dict['eevee_time'], icon = 'RENDER_STILL')
            col_l.label(text = '')
            col_r.label(text = weight_dict['eevee_memory'], icon = 'BLANK1')
            col_l.label(text = 'RAM:')
            col_r.label(text = weight_dict['scene_memory'], icon = 'MEMORY')
            col_l.label(text = 'Storage:')
            col_r.label(text = weight_dict['storage'], icon = 'DISK_DRIVE')
            col_r.label(text = '* Excluding textures')

class HG_PT_B_GENERATION_PROBABILITY(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = "Generation Probability"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text = '', icon = 'MOD_TINT')
        
    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D

        col = layout.column(align = True)

        flow = get_flow(sett, col)
        flow.separator() 
        flow.prop(sett, 'male_chance')
        flow.prop(sett, 'female_chance')
        flow.separator()

        flow.prop(sett, 'caucasian_chance')
        flow.prop(sett, 'black_chance')
        flow.prop(sett, 'asian_chance')
        
class HG_PT_B_HEIGHT_VARIATION(Batch_PT_Base, bpy.types.Panel):
    """Subpanel showing options for height variation in the generation of batch
    humans.
    """
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = "Height variation"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text = '', icon_value = get_hg_icon('length'))
        
    def draw(self, context):
        layout = self.layout      
        sett = context.scene.HG3D
        
        row = layout.box().row(align = True)
        row.scale_y = 1.5
        row.prop(sett, 'batch_height_system', expand = True)
        
        layout.label(text = 'Average height:', icon = 'EMPTY_SINGLE_ARROW')
        
        self._draw_average_height_props(layout, sett)
        
        layout.separator()
        layout.label(text = 'Bell curve settings:', icon = 'SMOOTHCURVE')
        
        col = layout.column(align = True)
        col.prop(sett, 'batch_standard_deviation', slider = False)      
        
        box = layout.box()
        box.prop(
            sett, 'show_height_examples',
            text = 'Show height examples',
            icon="TRIA_DOWN" if sett.show_height_examples else "TRIA_RIGHT",
            emboss=False,
            toggle=True
            )
        if sett.show_height_examples:
            split = box.split()
            for gender in ['male', 'female']:
                col_l = split.column()
                col_l.separator()
                col_l.label(text = f'{gender.capitalize()} examples:')
                
                self._draw_examples_list(col_l, sett, gender) 

    def _draw_average_height_props(self, layout, sett):
        """Draws props for the user to select the average height in either 
        metric or imperial system

        Args:
            layout (UILayout): layout to draw in
            sett (PropertyGroup): addon props
        """
        col = layout.column(align=True)
        if sett.batch_height_system == 'metric':
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(sett, 'batch_average_height_cm_male')
            col.prop(sett, 'batch_average_height_cm_female')
        else:
            for gender in ['male', 'female']:
                row = col.row(align=True)
                row.label(text=gender.capitalize())
                row.prop(sett, f'batch_average_height_ft_{gender}')
                row.prop(sett, f'batch_average_height_in_{gender}')

    def _draw_examples_list(self, layout, sett, gender):
        """Draws a list of example heights based on the settings the user selected.

        Args:
            layout (UILayout): layout to draw in
            sett (PropertyGroup): Add-on preferences
            gender (str): 'male' or 'female', determines which average height to
                sample from.
        """
        length_list = length_from_bell_curve(
            sett,
            gender,
            random_seed=False,
            samples=10
        )
        
        col = layout.column(align = True)
        col.scale_y = 0.8
        
        for i in length_list:
            length_m = round(i/100, 2)
            
            length_label = self._unit_conversion(sett, length_m)
            
            row = col.row(align = True)
            row.alert = i > 200 or i < 150
            row.label(text = length_label) 

    def _unit_conversion(self, sett, length_m):
        if sett.batch_height_system == 'imperial':
            length_feet   = length_m / 0.3048
            length_inches = int(length_feet*12.0 - int(length_feet)*12.0)
            length_label  = (str(int(length_feet))
                                + "' "
                                + str(length_inches)
                                + '"'
                                )
        else:
            alignment = '0 ' if len(str(length_m)) == 3 else ' '
            length_label = str(length_m) + alignment + 'm'
        
        return length_label



class HG_PT_B_QUALITY(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = "Quality"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text = '', icon = 'OPTIONS')
        
    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D

        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        
        col.label(text = 'Texture resolution:', icon = 'IMAGE_PLANE')
        col.prop(sett, 'batch_texture_resolution', text = '')
        
        # col.separator()
        
        # col.label(text = 'Polygon reduction [BETA]:', icon = 'MOD_DECIM')
        # col.prop(sett, 'batch_poly_reduction', text = '')
        
        col.separator()

        col.label(text = 'Objects:', icon = 'MESH_CUBE')
        col_header = col.column(heading = 'Delete')
        col_header.prop(sett, 'batch_delete_backup', text = 'Backup human')
        
        col.separator()
        
        col.label(text = 'Modifiers/effects:', icon = 'MODIFIER')
        col_header = col.column(heading = 'Apply')
        col_header.prop(sett, 'batch_apply_shapekeys', text = 'Shape keys')
        col_e = col_header.column()
        col_e.enabled = sett.batch_apply_shapekeys       
        col_e.prop(sett, 'batch_apply_armature_modifier', text = 'Armature')
        col_e.prop(sett, 'batch_apply_clothing_geometry_masks', text = 'Geometry masks') 
        #col_e.prop(sett, 'batch_apply_poly_reduction', text = 'Polygon reduction')
        
        col.separator()

        col.label(text = 'Clothing:', icon = 'MOD_CLOTH')
        col_header = col.column(heading = 'Remove')
        col_header.prop(sett, 'batch_remove_clothing_subdiv', text = 'Subdivisions')
        col_header.prop(sett, 'batch_remove_clothing_solidify', text = 'Solidify')
        
        


class HG_PT_B_HAIR(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = " Hair"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        header(self,context, 'hair')
        self.layout.label(text = '', icon_value = get_hg_icon('hair'))
        
    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D
        layout.enabled = sett.batch_hair

        row = layout.row(align = True)
        row.scale_y = 1.5
        row.prop(sett, 'batch_hairtype', expand = True)
        if sett.batch_hairtype == 'particle':
            layout.prop(sett, 'batch_hair_quality_{}'.format(sett.batch_hairtype), text = 'Quality')
        else:
            col = layout.column()
            col.alert = True
            col.label(text = 'Coming soon!')

class HG_PT_B_CLOTHING(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = " Clothing"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        header(self, context,'clothing')
        self.layout.label(text = '', icon_value = get_hg_icon('clothing'))

    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D
        layout.enabled = sett.batch_clothing
        hg_icons = preview_collections['hg_icons']
        
        col = layout.column(align = True)
        box =col.box().row()
        box.label(text = 'Select libraries:')
        box.operator('hg3d.refresh_batch_uilists', text = '', icon = 'FILE_REFRESH')

        #col.scale_y = 1.5
        row=col.row(align = False)
        row.template_list("HG_UL_BATCH_CLOTHING", "", context.scene, "batch_clothing_col", context.scene, "batch_clothing_col_index")
        
        col = layout.column()
        count = sum([(item.male_items + item.female_items) for item in context.scene.batch_clothing_col if item.enabled])
        
        if count == 0:
            col.alert = True
        
        col.label(text = 'Total: {} Outfits'.format(count))
        


class HG_PT_B_EXPRESSION(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = " Expression"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        header(self, context, 'expression')
        self.layout.label(text = '', icon_value = get_hg_icon('expression'))
        
    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D
        layout.enabled = sett.batch_expression

        col = layout.column(align = True)
        box =col.box().row()
        box.label(text = 'Select libraries:')
        box.operator('hg3d.refresh_batch_uilists', text = '', icon = 'FILE_REFRESH')
        col = col.column()
        col.template_list("HG_UL_BATCH_EXPRESSIONS", "", context.scene, "batch_expressions_col", context.scene, "batch_expressions_col_index")

        count = sum([item.count for item in context.scene.batch_expressions_col if item.enabled])
        if count == 0:
            col.alert = True
        col.label(text = 'Total: {} Expressions'.format(count))

class HG_PT_B_BAKING(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = " Bake textures"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return False

    def draw_header(self, context):
        header(self, context, 'bake')
        self.layout.label(text = '', icon = "RENDERLAYERS")
        
    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D
        layout.enabled = sett.batch_bake

        col = get_flow(sett, layout.box())
        col.prop(sett, 'bake_samples', text = 'Quality')

        col = get_flow(sett, layout.box())
        
        draw_resolution_box(sett, col, show_batch_comparison=True)

        col = get_flow(sett, layout.box())
        col.prop(sett, 'bake_export_folder', text = 'Output Folder:')
        
        row = col.row()
        row.alignment = 'RIGHT'
        row.label(text = 'HumGen folder when left empty', icon = 'INFO')
        col.prop(sett, 'bake_file_type', text = 'Format:')

def header(self, context, categ):
    sett = context.scene.HG3D
    layout = self.layout
    layout.prop(sett, 'batch_{}'.format(categ), text="")


class HG_PT_BATCH_TIPS(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = "Tips and suggestions!"
    bl_options = {'HIDE_HEADER'}
        
    @classmethod
    def poll(cls, context):
        return get_prefs().show_tips
    
    def draw(self, context):
        layout = self.layout
    
        draw_tips_suggestions_ui(
            layout,
            context
        )
        
        if get_prefs().full_height_menu:
            layout.separator(factor=200)
