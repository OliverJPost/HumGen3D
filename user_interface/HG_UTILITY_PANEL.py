import bpy #type: ignore
import os
from .. HG_COMMON_FUNC import find_human
from .. HG_PCOLL import preview_collections
from . HG_PANEL_FUNCTIONS import tab_switching_menu, get_flow

class Tools_PT_Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"

    def Header (self, context):
        return True

    def draw_thumbnail_prev(self, layout, sett):
        box = layout.box().column(align = True)
        box.prop(sett, 'thumb_ui', text = 'Select thumbnail',
            icon="TRIA_DOWN" if sett.thumb_ui else "TRIA_RIGHT",
            emboss=False,
            toggle=True)

        if not sett.thumb_ui:    
            return

        row = box.row()
        img = sett.preset_thumbnail
        if img:
            row.alert = True if img.size[0] > 600 or img.size[1] > 600 else False
        row.label(text = '256x265px preferably', icon = 'INFO')
        box.template_icon_view(sett, "preset_thumbnail_enum", show_labels=True, scale=4, scale_popup=10)   
        box.template_ID(sett, "preset_thumbnail", open="image.open")
        if img and img.name == 'Render Result':
            box.label(text = "Can't preview img, but it will be saved")
        box.prop(sett, 'dont_export_thumb', text = "Don't export thumbnail")

    def not_creation(self, hg_rig, layout):
        if not hg_rig.HG.phase in ['body', 'face', 'skin', 'hair', 'length']:
            layout.alert = True
            layout.label(text = 'Human not in creation phase')
            return True
        else:
            return False

class Tools_PT_Poll:
    @classmethod
    def poll (cls, context):
        hg_rig = find_human(context.object)
        return hg_rig 
        
class HG_PT_UTILITY(Tools_PT_Base, bpy.types.Panel):
    bl_idname = "HG_PT_UTILITY"
    bl_label = "Extras"

    @classmethod
    def poll(cls, context):
        return context.scene.HG3D.active_ui_tab == 'TOOLS'

    def draw_header(self, context):
        tab_switching_menu(self.layout, context.scene.HG3D)

    def draw(self,context):
        layout = self.layout
        hg_rig = find_human(context.object)
        if not hg_rig:
            layout.label(text='No human selected')
            return

        pref = context.preferences.addons[os.path.splitext(__package__)[0]].preferences
        sett = context.scene.HG3D

        col_h = layout.column()
        col_h.scale_y = 1.5
        col_h.operator('hg3d.drawtutorial', text = 'Open Tutorial Again', icon = 'WINDOW').first_time = False

 
class HG_PT_T_BAKE(Tools_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_UTILITY"
    bl_label = "Texture Baking"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text = '', icon = 'RENDER_RESULT')

         
    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D

        hg_rig = find_human(context.object)
        if not hg_rig:
            layout.label(text = 'No human selected')
            return

        if 'hg_baked' in hg_rig:
            layout.label(text = 'Already baked')
            return

        col = get_flow(sett, layout.box())
        col.prop(sett, 'bake_samples', text = 'Quality')

        col = get_flow(sett, layout.box())
        row = col.row()
        row.alignment = 'CENTER'
        row.label(text = 'Resolution', icon = 'IMAGE_PLANE')
        res_list = ['body', 'eyes', 'teeth', 'clothes']
        for res_type in res_list:
            col.prop(sett, f'bake_res_{res_type}', text = res_type.capitalize())

        col = get_flow(sett, layout.box())
        col.prop(sett, 'bake_export_folder', text = 'Output Folder:')
        row = col.row()
        row.alignment = 'RIGHT'
        row.label(text = 'HumGen folder when left empty', icon = 'INFO')
        col.prop(sett, 'bake_file_type', text = 'Format:')

        col = layout.column()
        col.scale_y = 1.5
        col.alert = True
        col.operator('hg3d.bake', icon = 'OUTPUT', depress = True)
        col.label(text = 'Blender freezes in current version', icon = 'INFO')

class HG_PT_T_MODAPPLY(Tools_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_UTILITY"
    bl_label = "Apply modifiers"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text = '', icon = 'MOD_SUBSURF')

    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D
        hg_rig =  find_human(context.object)
        if not hg_rig:
            layout.label(text='No human selected')
            return

        if hg_rig.HG.phase in ['body', 'face', 'skin', 'hair', 'length']:
            col = layout.column()
            col.alert = True
            col.label(text = 'Human still in Creation Phase')
            col.label(text = 'Sure you want to apply modifiers?')

        col = layout.column()
        col.label(text = 'Select modifiers to be applied:')
        col.operator('hg3d.ulrefresh', text = 'Refresh modifiers').type = 'modapply'
        col.template_list("HG_UL_MODAPPLY", "", context.scene, "modapply_col", context.scene, "modapply_col_index")

        row = col.row(align = True)
        row.operator('hg3d.selectmodapply', text = 'All').all = True
        row.operator('hg3d.selectmodapply', text = 'None').all = False
        col.separator()

        box = col.box().column(align = True)
        box.label(text='Objects to apply:')
        row= box.row(align = True)
        row.prop(sett, 'modapply_search_objects', text = '')
        box.label(text='Modifier list display:')
        row= box.row(align = True)
        row.prop(sett, 'modapply_search_modifiers', text = '')

        box = col.box().column(align = True)
        box.label(text = 'Options:')
        box.prop(sett, 'modapply_keep_shapekeys', text = 'Keep shapekeys')
        box.prop(sett, 'modapply_apply_hidden', text = 'Apply hidden modifiers')

        col_h = col.column()
        col_h.scale_y = 1.5
        col_h.operator('hg3d.modapply', text = 'Apply selected modifiers', depress = True)

class HG_PT_T_PRESET(Tools_PT_Base, bpy.types.Panel, Tools_PT_Poll):
    bl_parent_id = "HG_PT_UTILITY"
    bl_label = "Save as starting human"
    bl_options = {'DEFAULT_CLOSED'}

    #poll inherited
    
    def draw_header(self, context):
        self.layout.label(text = '', icon = 'OUTLINER_OB_ARMATURE')
        
    def draw(self, context):   
        hg_rig = find_human(context.object)
        sett = context.scene.HG3D
        layout = self.layout

        col= layout.column(align = True)

        if self.not_creation(hg_rig, layout):
            return

        self.draw_thumbnail_prev(col, sett)

        col.separator()
        col.prop(sett, 'preset_name', text = 'Name')
        col.separator()

        row = col.row(align = True)
        row.scale_y = 1.5
        row.operator('hg3d.savepreset', text = 'Save starting human', depress= True)
        row.operator('hg3d.openfolder', text = '', icon = 'FILE_FOLDER').subpath = '/models/{}'.format(hg_rig.HG.gender)
        col.separator()
        row = col.row(align = True)
        row.label(text = 'Not everything will be saved')
        row.operator('hg3d.showinfo', icon = 'QUESTION', emboss = False).info = 'starting_human'


#RELEASE update base shapekeys json    
class HG_PT_T_SHAPEKEY(Tools_PT_Base, bpy.types.Panel, Tools_PT_Poll):
    bl_parent_id = "HG_PT_UTILITY"
    bl_label = "Save custom shapekeys"
    bl_options = {'DEFAULT_CLOSED'}

    #poll inherited

    def draw_header(self, context):
        self.layout.label(text = '', icon = 'SHAPEKEY_DATA')

    def draw(self, context):   
        hg_rig = find_human(context.object)
        sett = context.scene.HG3D
        layout = self.layout

        col= layout.column(align = True)

        if self.not_creation(hg_rig, layout):
            return

        box = col.box()
        row = box.row()
        row.alignment = 'CENTER'
        row.label(text = 'Prefix naming scheme', icon = 'INFO')
        box.label(text = 'bp_ = Body tab (i.e. Muscular)')
        box.label(text = 'pr_ = Face presets/Ethnicities')
        box.label(text = 'ff_x_ = Custom facial features tab')

        col.label(text = 'Collection name:')
        col.prop(sett, 'shapekey_col_name', text = '')
        col.separator()
        col.operator('hg3d.ulrefresh', text = 'Refresh shapekeys').type = 'shapekeys'
        col.template_list("HG_UL_SHAPEKEYS", "", context.scene, "shapekeys_col", context.scene, "shapekeys_col_index")
        col.separator()
        col.prop(sett, 'show_saved_sks', text = 'Show already saved shapekeys', icon = 'CHECKBOX_HLT'if sett.show_saved_sks else 'CHECKBOX_DEHLT')
        col.separator()
        col.prop(sett, 'save_shapkeys_as', text = 'Save as')
        col.separator()
        row = col.row(align = True)
        row.scale_y = 1.5
        row.operator('hg3d.saveshapekey', text = 'Save selected shapekeys', depress= True)
        row.operator('hg3d.openfolder', text = '', icon = 'FILE_FOLDER').subpath = '/models/shapekeys'

        col.label(text = 'Give your shapekeys clear names', icon = 'INFO')


class HG_PT_T_HAIR(Tools_PT_Base, bpy.types.Panel, Tools_PT_Poll):
    bl_parent_id = "HG_PT_UTILITY"
    bl_label = "Save custom hairstyles"
    bl_options = {'DEFAULT_CLOSED'}

    #poll inherited

    def draw_header(self, context):
        hg_icons = preview_collections['hg_icons']
        self.layout.label(text = '', icon_value = hg_icons['hair'].icon_id)

    def draw(self, context):   
        hg_rig = find_human(context.object)
        hg_icons = preview_collections['hg_icons']
        sett = context.scene.HG3D
        layout = self.layout

        col= layout.column(align = True)

        if self.not_creation(hg_rig, layout):
            return

        self.draw_thumbnail_prev(col, sett)
 
        col.separator()
        row = col.row(align = True)
        row.operator('hg3d.ulrefresh', text = 'Refresh hairsystems').type = 'hair'
        row.prop(sett, 'show_eyesystems', text = '', icon_value = hg_icons['eyes'].icon_id, toggle = True)

        col.template_list("HG_UL_SAVEHAIR", "", context.scene, "savehair_col", context.scene, "savehair_col_index")

        col.separator()
        col = col.column()
        col.use_property_split = True
        col.use_property_decorate = False
        #col.label(text = 'Hairstyle name:')
        col.prop(sett, 'hairstyle_name', text = 'Name:')
        col.separator()
        row = col.column(heading = 'Gender').row(align = True)
        row.prop(sett, 'savehair_male', text = 'Male', toggle= True)    
        subrow = row.row(align = True)
        subrow.enabled = False if sett.save_hairtype == 'facial_hair' else True  
        subrow.prop(sett, 'savehair_female', text = 'Female', toggle= True)     
        
        col.separator()
        col.prop(sett, 'save_hairtype', text = 'Type')
        col.separator()
        row = col.row(align = True)
        row.scale_y = 1.5
        row.operator('hg3d.savehair', text = 'Save selected systems', depress= True)
        row.operator('hg3d.openfolder', text = '', icon = 'FILE_FOLDER').subpath = f'/hair/{sett.save_hairtype}'

        col.label(text = 'Give your shapekeys clear names', icon = 'INFO')

class HG_PT_T_OUTFIT(Tools_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_UTILITY"
    bl_label = "Save custom outfits"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        hg_icons = preview_collections['hg_icons']
        self.layout.label(text = '', icon_value = hg_icons['clothing'].icon_id)

    def draw(self, context):   
        hg_rig = find_human(context.object)
        sett = context.scene.HG3D
        layout = self.layout
        col= layout.column(align = True)

        self.draw_thumbnail_prev(col, sett)

        col.separator()
        row = col.row(align = True)
        row.operator('hg3d.ulrefresh', text = 'Refresh objects').type = 'outfit'
        col.template_list("HG_UL_SAVEOUTFIT", "", context.scene, "saveoutfit_col", context.scene, "saveoutfit_col_index")

        col.separator()
        col = col.column()
        col.use_property_split = True
        col.use_property_decorate = False
        #col.label(text = 'Hairstyle name:')
        col.prop(sett, 'saveoutfit_human', text = 'Human:')
        col.separator()
        col.prop(sett, 'saveoutfit_name', text = 'Outfit name:')
        col.separator()
        row = col.column(heading = 'Gender:').row(align = True)
        row.prop(sett, 'saveoutfit_male', text = 'Male', toggle= True)    
        subrow = row.row(align = True)
        subrow.enabled = False if sett.save_hairtype == 'facial_hair' else True  
        subrow.prop(sett, 'saveoutfit_female', text = 'Female', toggle= True)     
        
        col.separator()
        col.prop(sett, 'saveoutfit_categ', text = 'Category:')
        col.separator()
        row = col.row(align = True)
        row.scale_y = 1.5
        row.operator('hg3d.saveoutfit', text = 'Save as outfit', depress= True)
        row.operator('hg3d.openfolder', text = '', icon = 'FILE_FOLDER').subpath = f'/{sett.saveoutfit_categ}/'
        
        layout.prop(sett, 'open_exported_outfits', text = 'Open exported files when done')


class HG_PT_T_CLOTH(Tools_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_UTILITY"
    bl_label = "Mesh --> Clothing"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.object

    def draw_header(self, context):
        hg_icons = preview_collections['hg_icons']
        self.layout.label(text = '', icon_value = hg_icons['clothing'].icon_id)

    def draw(self, context):   
        sett = context.scene.HG3D
        layout = self.layout
        hg_icons = preview_collections['hg_icons']
        
        box = layout.box().row()
        box.alignment = 'CENTER'
        box.label(text = context.object.name, icon_value = hg_icons['clothing'].icon_id)
        
        col= layout.column(align = True)
        col.use_property_split = True
        col.use_property_decorate = False
        
        col.prop(sett, 'mtc_armature', text = 'Armature:')
        col.prop(sett, 'shapekey_calc_type', text = 'Cloth type')
        
  
class HG_PT_T_MASKS(Tools_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_T_CLOTH"
    bl_label = "Geometry masks"
    bl_options = {'DEFAULT_CLOSED'}

    #TODO make
    @classmethod
    def poll(cls, context):
        return False
    
    def draw(self, context):   
        hg_rig = find_human(context.object)
        sett = context.scene.HG3D
        layout = self.layout
        col= layout.column(align = True, heading = 'Masks:')
        col.use_property_split = True
        col.use_property_decorate = False
        
        col.prop(sett, 'ui_custom', text = 'Short legs')
        col.prop(sett, 'ui_custom', text = 'Long legs')
        col.prop(sett, 'ui_custom', text = 'Short Arms')
        col.prop(sett, 'ui_custom', text = 'Long Arms')
        col.prop(sett, 'ui_custom', text = 'Torso')
        col.prop(sett, 'ui_custom', text = 'Foot')
        col.separator()
        col.operator('hg3d.showinfo', text = 'Add masks')
        
        mask_options = [
                "mask_lower_short",
                "mask_lower_long", 
                "mask_torso",
                "mask_arms_short",
                "mask_arms_long",
                "mask_foot",
            ]
        default = "lower_short",
        
        if not context.object:
            return
        
        mask_props = [f'mask_{i}' for i in range(10) if f'mask_{i}' in context.object]
        if mask_props:
            col.separator()
            col.label(text = 'Current masks:')
            for prop_name in mask_props:
                col.label(text = context.object[prop_name])
        
class HG_PT_T_CLOTHWEIGHT(Tools_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_T_CLOTH"
    bl_label = "Weight painting"
    
    def draw(self, context):        
        sett = context.scene.HG3D
        hg_rig = sett.mtc_armature
        layout = self.layout
           
        if not hg_rig:
            layout.label(text = 'Select an armature in the field above')   
            return
            
        col = layout.column()   
        col.prop(sett, 'mtc_add_armature_mod', text = 'Add armature modifier')
        col.prop(sett, 'mtc_parent', text = 'Parent cloth to human')
        col.operator('hg3d.autoweight', text = 'Auto weight paint')

        if 'spine' in set([vg.name for vg in context.object.vertex_groups]):
            col.label(text= 'Weight painting found', icon = 'INFO')
        
class HG_PT_T_CLOTHSK(Tools_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_T_CLOTH"
    bl_label = "Corrective shapekeys"
    
    def draw(self, context):   
        hg_rig = find_human(context.object)
        sett = context.scene.HG3D
        layout = self.layout
  
        if hg_rig:
            if context.object.data.shape_keys:
                if next((True for sk in context.object.data.shape_keys.key_blocks if sk.name.startswith('cor')), False):
                    layout.label(text = 'Corrective shapekeys found!', icon = 'INFO')
                    
        col = layout.column()
        col.operator('hg3d.addcorrective', text = 'Add corrective shapekeys')
        
class HG_PT_T_CLOTHMAT(Tools_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_T_CLOTH"
    bl_label = "Clothing material"
    
    def draw(self, context):   
        hg_rig = find_human(context.object)
        sett = context.scene.HG3D
        layout = self.layout
  
        col = layout.column()
        mat = context.object.active_material
        if mat and 'HG_Control' in [n.name for n in mat.node_tree.nodes]:
            nodes = mat.node_tree.nodes
            base_color = nodes.get('Base Color')
            if base_color:
                col.label(text = 'Base color')
                col.template_ID(base_color, "image", new="image.new", open="image.open")
            roughness = nodes.get('Roughness')
            if roughness:
                col.label(text = 'Roughness')
                col.template_ID(roughness, "image", new="image.new", open="image.open")
            normal = nodes.get('Normal')
            if normal:
                col.label(text = 'Normal map')
                col.template_ID(normal, "image", new="image.new", open="image.open")
        else:
            col.operator('hg3d.addclothmat', text = 'Add default HG material')
            

class HG_PT_T_DEV(Tools_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_UTILITY"
    bl_label = "Developer tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text = '', icon = 'PREFERENCES')

    def draw(self, context):   
        sett = context.scene.HG3D
        layout = self.layout
        hg_icons = preview_collections['hg_icons']
        
        col = layout.column()
        col.operator('hg3d.testop', text = 'test operator')
        col.operator('hg3d.delstretch')