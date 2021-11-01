import bpy  # type: ignore

from ..core.HG_PCOLL import preview_collections
from ..features.common.HG_COMMON_FUNC import find_human, get_prefs
from .HG_PANEL_FUNCTIONS import (draw_panel_switch_header, draw_sub_spoiler,
                                 get_flow, in_creation_phase)


class Tools_PT_Base:
    """Bl_info and commonly used tools for Utility panels
    """
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "HumGen"

    def Header (self, context):
        return True

    def draw_thumbnail_selector(self, layout, sett):
        """Collapsable layout for selecting thunbnails to save, used by saving
        sections

        Args:
            layout (UILayout): layout to draw thumbnail selector in
            sett (PropertyGroup): HumGen props
        """
        is_open, box = draw_sub_spoiler(
            layout, sett, 'thumb_ui', 'Select thumbnail')
        if not is_open:
            return
        
        img = sett.preset_thumbnail
        
        row = box.row()
        if img:
            row.alert = (True if img.size[0] > 600 or img.size[1] > 600 
                         else False)
        row.label(text = '256x265px preferably', icon = 'INFO')
        
        box.template_icon_view(
            sett, "preset_thumbnail_enum",
            show_labels=True,
            scale=4,
            scale_popup=10
            )   
        box.template_ID(
            sett, "preset_thumbnail",
            open="image.open"
            )

        if img and img.name == 'Render Result':
            box.label(text = "Can't preview img, but it will be saved")
            
        box.prop(sett, 'dont_export_thumb',
                 text = "Export without thumbnail"
                 )

    def warning_if_not_creation_phase(self, hg_rig, layout) -> bool:
        """Show a warning if the human is not in creation phase

        Args:
            hg_rig (Object): rig of HumGen human
            layout (UILayout): layout to draw the warning in

        Returns:
            bool: returns True if warning raised, causing the layout this method
            is called in to not draw the rest of the section
        """
        if not hg_rig.HG.phase in ['body', 'face', 'skin', 'hair', 'length']:
            layout.alert = True
            layout.label(text = 'Human not in creation phase')
            return True
        else:
            return False
        
class HG_PT_UTILITY(Tools_PT_Base, bpy.types.Panel): 
    """Panel with extra functionality for HumGen that is not suitable for the 
    main panel. Things like content pack creation, texture baking etc.

    Args:
        Tools_PT_Base (class): Adds bl_info and commonly used tools
    """
    bl_idname = "HG_PT_UTILITY"
    bl_label  = "Extras"

    @classmethod
    def poll(cls, context):
        sett = context.scene.HG3D
        return sett.active_ui_tab == 'TOOLS' and not sett.content_saving_ui

    def draw_header(self, context):
        draw_panel_switch_header(self.layout, context.scene.HG3D)

    def draw(self,context):
        layout = self.layout

        if not get_prefs().filepath:
            layout.alert = True
            layout.label(text = 'No filepath selected', icon = 'ERROR')
            return
        
        hg_rig = find_human(context.object)
        if not hg_rig:
            layout.label(text='No human selected')
            

        col_h = layout.column()
        col_h.scale_y = 1.5
        col_h.operator('hg3d.draw_tutorial',
                       text = 'Open Tutorial Again',
                       icon = 'WINDOW'
                       ).tutorial_name = 'get_started_tutorial'

 
class HG_PT_T_BAKE(Tools_PT_Base, bpy.types.Panel):
    """subpanel with tools for texture baking

    Args:
        Tools_PT_Base (class): bl_info and common tools
    """
    bl_parent_id = "HG_PT_UTILITY"
    bl_label     = "Texture Baking"
    bl_options   = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text = '', icon = 'RENDER_RESULT')

    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D

        found_problem = self._draw_warning_labels(context, layout)
        if found_problem:
            return

        col = get_flow(sett, layout.box())
        col.prop(sett, 'bake_samples', text = 'Quality')

        col = get_flow(sett, layout.box())
        
        draw_resolution_box(sett, col)

        col = get_flow(sett, layout.box())
        col.prop(sett, 'bake_export_folder', text = 'Output Folder:')
        
        row = col.row()
        row.alignment = 'RIGHT'
        row.label(text = 'HumGen folder when left empty', icon = 'INFO')
        col.prop(sett, 'bake_file_type', text = 'Format:')

        col         = layout.column()
        col.scale_y = 1.5
        col.alert   = True
        col.operator('hg3d.bake', icon = 'OUTPUT', depress = True)
        col.label(text = 'Blender freezes in current version', icon = 'INFO')

    def _draw_warning_labels(self, context, layout) -> bool:
        """Draws warning if no human is selected or textures are already baked

        Args:
            context (bpy.context): Blender context
            layout (UILayout): layout to draw warning labels in

        Returns:
            bool: True if problem found, causing rest of ui to cancel
        """
        hg_rig = find_human(context.object)
        if not hg_rig:
            layout.label(text = 'No human selected')
            return True

        if 'hg_baked' in hg_rig:
            if context.scene.HG3D.batch_idx:
                layout.label(text = 'Baking in progress')
            else:
                layout.label(text = 'Already baked')
            
            return True
        
        return False
        
class HG_PT_T_MODAPPLY(Tools_PT_Base, bpy.types.Panel):
    """Panel for applying modifiers to HumGen human

    Args:
        Tools_PT_Base (class): bl_info and common tools
    """
    bl_parent_id = "HG_PT_UTILITY"
    bl_label     = "Apply modifiers"
    bl_options   = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text = '', icon = 'MOD_SUBSURF')

    def draw(self, context):
        layout = self.layout
        sett = context.scene.HG3D
        found_problem = self._draw_warning_labels(context, layout)
        if found_problem:
            return
        
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

    def _draw_warning_labels(self, context, layout) -> bool:
        """Draws warning labels if no human selected or in creation phase

        Args:
            context (bpy.context): B context
            layout (UILayout): layout to draw in

        Returns:
            bool: True if problem found, prompting return
        """
        hg_rig =  find_human(context.object)
        if not hg_rig:
            layout.label(text='No human selected')
            return True

        if in_creation_phase(hg_rig):
            col = layout.column()
            col.alert = True
            col.label(text = 'Human still in Creation Phase')
            col.label(text = 'Sure you want to apply modifiers?')
            
        return False



class HG_PT_CUSTOM_CONTENT(Tools_PT_Base, bpy.types.Panel):
    """Shows options for adding preset/starting humans

    Args:
        Tools_PT_Base (class): bl_info and common tools
        Tools_PT_Poll (class): poll for checking if object is HumGen human
    """
    bl_parent_id = "HG_PT_UTILITY"
    bl_label     = "Save custom content"

    @classmethod
    def poll (cls, context):
        hg_rig = find_human(context.object)
        return hg_rig

    def draw_header(self, context):
        self.layout.label(text = '', icon = 'OUTLINER_OB_ARMATURE')
        
    def draw(self, context):   
        layout = self.layout
        
        col = layout.column()
        col.operator('hg3d.open_content_saving_tab').content_type = 'hair'


class Tools_PT_Poll:
    """adds a poll classmethod to check if a HumGen human is selected

    Returns:
        bool: False if no HumGen human is selected
    """
    @classmethod
    def poll (cls, context):
        hg_rig = find_human(context.object)
        return hg_rig and get_prefs().classic_content_saving_panels

class HG_PT_T_PRESET(Tools_PT_Base, bpy.types.Panel, Tools_PT_Poll):
    """Shows options for adding preset/starting humans

    Args:
        Tools_PT_Base (class): bl_info and common tools
        Tools_PT_Poll (class): poll for checking if object is HumGen human
    """
    bl_parent_id = "HG_PT_UTILITY"
    bl_label     = "Save as starting human"
    bl_options   = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text = '', icon = 'OUTLINER_OB_ARMATURE')
        
    def draw(self, context):   
        hg_rig = find_human(context.object)
        sett = context.scene.HG3D
        layout = self.layout

        if self.warning_if_not_creation_phase(hg_rig, layout):
            return
        
        col= layout.column(align = True)
        col.operator(
            'hg3d.draw_tutorial',
            text='Tutorial',
            icon='HELP'
        ).tutorial_name = 'starting_human_tutorial'
        
        col.separator()

        self.draw_thumbnail_selector(col, sett)


        col.separator()
        
        col.prop(sett, 'preset_name', text = 'Name')
        
        col.separator()

        row = col.row(align = True)
        row.scale_y = 1.5
        row.operator('hg3d.savepreset',
                     text = 'Save starting human',
                     depress= True
                     )
        row.operator('hg3d.openfolder',
                     text = '',
                     icon = 'FILE_FOLDER'
                     ).subpath = '/models/{}'.format(hg_rig.HG.gender)
        
        col.separator()
        
        row = col.row(align = True)
        row.label(text = 'Not everything will be saved')
        row.operator('hg3d.showinfo',
                     icon = 'QUESTION',
                     emboss = False
                     ).info = 'starting_human'


#RELEASE update base shapekeys json    
class HG_PT_T_SHAPEKEY(Tools_PT_Base, bpy.types.Panel, Tools_PT_Poll):
    """Panel for saving custom shapekeys

    Args:
        Tools_PT_Base (class): bl_info and common tools
        Tools_PT_Poll (class): poll to check if object is humgen human
    """
    bl_parent_id = "HG_PT_UTILITY"
    bl_label     = "Save custom shapekeys"
    bl_options   = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text = '', icon = 'SHAPEKEY_DATA')

    def draw(self, context):   
        hg_rig = find_human(context.object)
        sett = context.scene.HG3D
        layout = self.layout

        col= layout.column(align = True)

        if self.warning_if_not_creation_phase(hg_rig, layout):
            return

        col.operator(
            'hg3d.draw_tutorial',
            text='Tutorial',
            icon='HELP'
        ).tutorial_name = 'shapekeys_tutorial'
        
        col.separator()

        self._draw_prefix_info(col)

        col.label(text = 'Collection name:')
        col.prop(sett, 'shapekey_col_name', text = '')
        
        col.separator()
        
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
        
        col.separator()
        
        row = col.row(align = True)
        row.scale_y = 1.5
        row.operator('hg3d.saveshapekey',
                     text = 'Save selected shapekeys',
                     depress= True
                     )
        row.operator('hg3d.openfolder',
                     text = '',
                     icon = 'FILE_FOLDER'
                     ).subpath = '/models/shapekeys'

        col.label(text = 'Give your shapekeys clear names', icon = 'INFO')

    def _draw_prefix_info(self, layout):
        """Info for what prefixes to include

        Args:
            layout (UILayout): layout to draw in
        """
        box = layout.box()
        row = box.row()
        row.alignment = 'CENTER'
        row.label(text = 'Prefix naming scheme', icon = 'INFO')
        box.label(text = 'bp_ = Body tab (i.e. Muscular)')
        box.label(text = 'pr_ = Face presets/Ethnicities')
        box.label(text = 'ff_x_ = Custom facial features tab')


class HG_PT_T_HAIR(Tools_PT_Base, bpy.types.Panel, Tools_PT_Poll):
    """Subpanel for saving custom hair styles

    Args:
        Tools_PT_Base (class): bl_info and common tools
        Tools_PT_Poll (class): poll to check if object is humgen human
    """
    bl_parent_id = "HG_PT_UTILITY"
    bl_label     = "Save custom hairstyles"
    bl_options   = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        hg_icons = preview_collections['hg_icons']
        self.layout.label(text = '', icon_value = hg_icons['hair'].icon_id)

    def draw(self, context):   
        hg_rig   = find_human(context.object)
        hg_icons = preview_collections['hg_icons']
        sett     = context.scene.HG3D
        layout   = self.layout

        col= layout.column(align = True)

        if self.warning_if_not_creation_phase(hg_rig, layout):
            return

        col.operator(
            'hg3d.draw_tutorial',
            text='Tutorial',
            icon='HELP'
        ).tutorial_name = 'hairstyles_tutorial'
        
        col.separator()

        self.draw_thumbnail_selector(col, sett)
 
        col.separator()
        
        row = col.row(align = True)
        row.operator('hg3d.ulrefresh',
                     text = 'Refresh hairsystems'
                     ).type = 'hair'
        row.prop(sett, 'show_eyesystems',
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

        col.separator()
        
        col = col.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(sett, 'hairstyle_name',
                 text = 'Name:'
                 )
        
        col.separator()
        
        row = col.column(heading = 'Gender').row(align = True)
        row.prop(sett, 'savehair_male',
                 text = 'Male',
                 toggle= True
                 )    
        subrow = row.row(align = True)
        subrow.enabled = False if sett.save_hairtype == 'facial_hair' else True  
        subrow.prop(sett, 'savehair_female',
                    text = 'Female',
                    toggle= True
                    )     
        
        col.separator()
        
        col.prop(sett, 'save_hairtype', text = 'Type')
        
        col.separator()
        
        row = col.row(align = True)
        row.scale_y = 1.5
        row.operator('hg3d.savehair',
                     text = 'Save selected systems',
                     depress= True
                     )
        row.operator('hg3d.openfolder',
                     text = '',
                     icon = 'FILE_FOLDER'
                     ).subpath = f'/hair/{sett.save_hairtype}'

        col.label(text = 'Give your shapekeys clear names',
                  icon = 'INFO'
                  )

class HG_PT_T_OUTFIT(Tools_PT_Base, bpy.types.Panel):
    """Subpanel for saving custom outfits

    Args:
        Tools_PT_Base (class): bl_info and common tools
    """
    bl_parent_id = "HG_PT_UTILITY"
    bl_label     = "Save custom outfits"
    bl_options   = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        hg_icons = preview_collections['hg_icons']
        self.layout.label(text = '', icon_value = hg_icons['clothing'].icon_id)

    def draw(self, context):   
        sett = context.scene.HG3D
        layout = self.layout
        col= layout.column(align = True)

        col.operator('hg3d.draw_tutorial',
                    text = 'Tutorial',
                    icon = 'HELP'
                    ).tutorial_name = 'save_outfits_tutorial'

        col.separator()

        self.draw_thumbnail_selector(col, sett)

        col.separator()
        
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

        col.separator()
        
        col = col.column()
        col.use_property_split = True
        col.use_property_decorate = False
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
        row.operator('hg3d.saveoutfit',
                     text = 'Save as outfit',
                     depress= True
                     )
        row.operator('hg3d.openfolder',
                     text = '',
                     icon = 'FILE_FOLDER'
                     ).subpath = f'/{sett.saveoutfit_categ}/'
        
        layout.prop(sett, 'open_exported_outfits',
                    text = 'Open exported files when done'
                    )

class HG_PT_T_CLOTH(Tools_PT_Base, bpy.types.Panel):
    """Subpanel for making cloth objects from normal mesh objects

    Args:
        Tools_PT_Base (class): bl_info and common tools
    """
    bl_parent_id = "HG_PT_UTILITY"
    bl_label     = "Mesh --> Clothing"
    bl_options   = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.object

    def draw_header(self, context):
        hg_icons = preview_collections['hg_icons']
        self.layout.label(text = '',
                          icon_value = hg_icons['clothing'].icon_id
                          )

    def draw(self, context):   
        sett     = context.scene.HG3D
        layout   = self.layout
        hg_icons = preview_collections['hg_icons']
 
        layout.operator('hg3d.draw_tutorial',
                    text = 'Tutorial',
                    icon = 'HELP'
                    ).tutorial_name = 'mtc_tutorial'
        
        box = layout.box().row()
        box.alignment = 'CENTER'
        box.label(text = context.object.name,
                  icon_value = hg_icons['clothing'].icon_id
                  )
        
        col= layout.column(align = True)
        col.use_property_split = True
        col.use_property_decorate = False
        
        col.prop(sett, 'mtc_armature', text = 'Armature:')
        if sett.mtc_armature and in_creation_phase(sett.mtc_armature):
            scol = col.column()
            scol.alert = True
            scol.label(text = 'Human in creation phase', icon = 'ERROR')
        col.prop(sett, 'shapekey_calc_type', text = 'Cloth type')
        
#TODO make this panel work 
class HG_PT_T_MASKS(Tools_PT_Base, bpy.types.Panel):
    """Currently disabled
    """
    bl_parent_id = "HG_PT_T_CLOTH"
    bl_label = "Geometry masks"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):   
        hg_rig = find_human(context.object)
        sett = context.scene.HG3D
        layout = self.layout
        col= layout.column(align = True, heading = 'Masks:')
        col.use_property_split = True
        col.use_property_decorate = False
        
        col.prop(sett, 'mask_short_legs', text = 'Short legs')
        col.prop(sett, 'mask_long_legs', text = 'Long legs')
        col.prop(sett, 'mask_short_arms', text = 'Short Arms')
        col.prop(sett, 'mask_long_arms', text = 'Long Arms')
        col.prop(sett, 'mask_torso', text = 'Torso')
        col.prop(sett, 'mask_foot', text = 'Foot')
        col.separator()
        col.operator('hg3d.add_masks', text = 'Add masks')
        
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
        
        mask_props = [f'mask_{i}' for i in range(10)
                      if f'mask_{i}' in context.object
                      ]
        if mask_props:
            col.separator()
            col.label(text = 'Current masks:')
            for prop_name in mask_props:
                col.label(text = context.object[prop_name])
        
class HG_PT_T_CLOTHWEIGHT(Tools_PT_Base, bpy.types.Panel):
    """Subsubpanel for adding weight painting to clothes

    Args:
        Tools_PT_Base (class): bl_info and common tools
    """
    bl_parent_id = "HG_PT_T_CLOTH"
    bl_label     = "Weight painting"
    
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
    """Subsubpanel for adding corrective shapekeys to cloth

    Args:
        Tools_PT_Base (class): bl_info and common tools
    """
    bl_parent_id = "HG_PT_T_CLOTH"
    bl_label     = "Corrective shapekeys"
    
    def draw(self, context):   
        hg_rig = find_human(context.object)
        sett = context.scene.HG3D
        layout = self.layout

        if context.object and not context.object.type == 'MESH':
            return

        if hg_rig and context.object.data.shape_keys:
            has_corrective_sks = next(
                (True for sk in context.object.data.shape_keys.key_blocks
                    if sk.name.startswith('cor')),
                False
                )
            if has_corrective_sks:
                layout.label(text = 'Corrective shapekeys found!',
                             icon = 'INFO'
                             )
                    
        col = layout.column()
        col.operator('hg3d.addcorrective',
                     text = 'Add corrective shapekeys'
                     )
        
class HG_PT_T_CLOTHMAT(Tools_PT_Base, bpy.types.Panel):
    """Subsubpanel for adding standard material to cloth object

    Args:
        Tools_PT_Base (class): bl_info and common tools
    """
    bl_parent_id = "HG_PT_T_CLOTH"
    bl_label     = "Clothing material"
    
    def draw(self, context):   
        layout = self.layout
  
        col = layout.column()
        
        col.operator('hg3d.draw_tutorial',
                    text = 'Material tutorial',
                    icon = 'HELP'
                    ).tutorial_name = 'cloth_mat_tutorial'
                
        mat = context.object.active_material
        if not (mat and 'HG_Control' in [n.name for n in mat.node_tree.nodes]):
            col.operator('hg3d.addclothmat',
                         text = 'Add default HG material'
                         ) 
            return
        
        nodes = mat.node_tree.nodes
        self._draw_image_picker(col, nodes, 'Base Color')
        self._draw_image_picker(col, nodes, 'Roughness')
        self._draw_image_picker(col, nodes, 'Normal')
        
    def _draw_image_picker(self, layout, nodes, node_name):
        """adds an template_ID image picker for the cloth material nodes

        Args:
            layout (UILayout): to draw in
            nodes (ShaderNode list): nodes of cloth material
            node_name (str): name of image node
        """
        image_node = nodes.get(node_name)
        if not image_node:
            return
        
        layout.label(text = node_name)
        layout.template_ID(image_node, "image",
                            new="image.new",
                            open="image.open"
                            )

            
class HG_PT_T_DEV(Tools_PT_Base, bpy.types.Panel):
    """developer tools subpanel

    Args:
        Tools_PT_Base (class): bl_info and common tools
    """
    bl_parent_id = "HG_PT_UTILITY"
    bl_label     = "Developer tools"
    bl_options   = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        self.layout.label(text = '', icon = 'PREFERENCES')

    def draw(self, context):   
        layout = self.layout
        
        col = layout.column()
        col.operator('hg3d.testop', text = 'Test Operator')
        col.prop(context.scene.HG3D, 'batch_texture_resolution')
        col.operator('hg3d.delstretch')
        col.operator('hg3d.prepare_for_arkit')
        col.operator('hg3d.convert_hair_shader')
        col.operator('hg3d.reset_batch_operator')
