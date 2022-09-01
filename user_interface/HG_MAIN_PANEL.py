import os
from pathlib import Path
from sys import platform

import addon_utils  # type: ignore
import bpy

from .. import bl_info
from ..core.HG_PCOLL import preview_collections
from ..data.HG_COLORS import color_dict
from ..features.common.HG_COMMON_FUNC import (find_human, get_prefs,
                                              is_batch_result)
from ..user_interface.HG_TIPS_SUGGESTIONS_UI import \
    draw_tips_suggestions_ui  # type: ignore
from .HG_PANEL_FUNCTIONS import (draw_panel_switch_header, draw_spoiler_box,
                                 draw_sub_spoiler, get_flow, in_creation_phase,
                                 searchbox)


class HG_PT_PANEL(bpy.types.Panel):
    """Main Human Generator panel, divided into creation phase and finalize 
    phase. These phases are then divided into sections (i.e. hair, body, face)

    One exception is the clothing material section. If a HumGen clothing object
    is selected, this UI shows options to change the material
    """
    bl_idname      = "HG_PT_Panel"
    bl_label       = "HumGen"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "HumGen"

    @classmethod
    def poll(cls, context):
        sett = context.scene.HG3D
        return sett.active_ui_tab == 'CREATE' and not sett.content_saving_ui

    def draw_header(self, context):
        draw_panel_switch_header(self.layout, context.scene.HG3D)

    def draw(self,context):
        layout      = self.layout
        self.sett   = context.scene.HG3D
        self.pref   = get_prefs()

        self.hg_rig = find_human(context.active_object, include_applied_batch_results=True)
        if self.hg_rig:
            is_batch, is_applied_batch = is_batch_result(self.hg_rig)
        
        found_problem = self.draw_info_and_warning_labels(context, layout) 
        if found_problem:
            return
        
        self._draw_top_widget() 

        hg_rig = self.hg_rig
        
        if not hg_rig:
            try:
                context.object['hg_batch_marker']
                self._draw_batch_marker_notification(layout)  
            except:
                pass  
            self._draw_starting_human_ui(layout)
        elif is_batch:
            self._draw_batch_result_ui()
        elif 'cloth' in context.object or 'shoe' in context.object:
            self._draw_cloth_material_ui(context, layout)
        #creation phase
        elif in_creation_phase(hg_rig):
            self._draw_creation_section() 
            self._draw_length_section() 
            self._draw_face_section() 
            self._draw_skin_section() 
            self._draw_eyes_section() 
            if self.pref.hair_section in ['both', 'creation']:
                self._draw_hair_section(context) 
            self._draw_finish_creation_button(layout)    
        #finalize phase
        else:
            self.draw_creation_backup_section() 
            if self.pref.hair_section in ['both', 'finalize']:
                self._draw_hair_section(context) 
            self._draw_clothing_section() 
            self._draw_footwear_section() 
            self._draw_pose_section() 
            self._draw_expression_section() 
        
        if get_prefs().show_tips:
            draw_tips_suggestions_ui(
                layout,
                context
            )
            if get_prefs().full_height_menu:
                layout.separator(factor=200)

    #  __    __   _______     ___       _______   _______ .______      
    # |  |  |  | |   ____|   /   \     |       \ |   ____||   _  \     
    # |  |__|  | |  |__     /  ^  \    |  .--.  ||  |__   |  |_)  |    
    # |   __   | |   __|   /  /_\  \   |  |  |  ||   __|  |      /     
    # |  |  |  | |  |____ /  _____  \  |  '--'  ||  |____ |  |\  \----.
    # |__|  |__| |_______/__/     \__\ |_______/ |_______|| _| `._____|

    def draw_info_and_warning_labels(self, context, layout) -> bool:
        """Collection of all info and warning labels of HumGen

        Args:
            context : Blender Context
            layout : HumGen main panel layout

        Returns:
            bool: True if problem was found, causing the HumGen UI to stop
            displaying anything after the warning labels
        """
        filepath_problem = self._filepath_warning(layout)
        if filepath_problem:
            return True
        
        base_content_found = self._base_content_warning(layout)
        if not base_content_found:
            return True
        
        if not self.sett.subscribed:
            self._welcome_menu(layout)
            return True

        update_problem = self._update_notification(layout)
        if update_problem:
            return True
           
        general_problem = self._warning_header(context, layout)
        if general_problem:
            return True
        
        return False #no problems found
        
    def _filepath_warning(self, layout) -> bool:
        """Shows warning if no filepath is selected

        Args:
            layout (AnyType): Main HumGen panel layout

        Returns:
            Bool: True if filepath was not found, causing the UI to cancel
        """
        if self.pref.filepath:
            return False
        
        layout.alert = True
        layout.label(text = 'No filepath selected')
        layout.label(text = 'Select one in the preferences')
        layout.operator(
            'hg3d.openpref',
            text = 'Open preferences',
            icon ='PREFERENCES')
        
        return True       

    def _base_content_warning(self, layout) -> bool:
        """Looks if base content is installed, otherwise shows warning and 
        stops the rest of the UI from showing

        Args:
            layout (AnyType): Main Layout of HumGen Panel

        Returns:
            Bool: True if base content found, False causes panel to return
        """
        base_humans_path = os.path.join(
            self.pref.filepath,
            'content_packs',
            'Base_Humans.json'
            )
        
        base_content = os.path.exists(base_humans_path)
        
        if not base_content:
            layout.alert = True
            
            layout.label(text = "Filepath selected, but couldn't")
            layout.label(text = 'find any humans.')
            layout.label(text = 'Check if filepath is correct and')
            layout.label(text = 'if the content packs are installed.')
            
            layout.operator('hg3d.openpref',
                            text = 'Open preferences',
                            icon ='PREFERENCES'
                            )     
            
        return base_content

    def _update_notification(self, layout) -> bool:
        """Shows notifications for available or required updates of both the
        add-on and the content packs.

        Args:
            layout ([AnyType]): Main layout of HumGen panel

        Returns:
            bool: True if update required, causing panel to only show error message
        """
        #find out what kind of update is available
        if self.pref.cpack_update_required:      
            self.update = 'cpack_required'
        elif tuple(bl_info['version']) < tuple(self.pref.latest_version):
            self.update = 'addon'
        elif self.pref.cpack_update_available:
            self.update = 'cpack_available'
        else:
            self.update = None

        if not self.update:
            return False

        if self.update == 'cpack_required':
            layout.alert = True
            layout.label(text = 'One or more cpacks outdated!')
            layout.operator('hg3d.openpref',
                            text = 'Open preferences',
                            icon ='PREFERENCES'
                            )
            return True
        else:
            addon_label = 'Add-on update available!'
            cpack_label = 'CPack updates available'
            label = addon_label if self.update == 'addon' else cpack_label
            layout.operator("hg3d.openpref",
                            text = label,
                            icon = 'PACKAGE',
                            depress = True,
                            emboss = True if self.update == 'addon' else False)
            return False

    def _welcome_menu(self, layout):
        col = layout.column()
        col.scale_y = 4
        col.operator('hg3d.showinfo',
                     text = 'Welcome to Human Generator!',
                     depress = True
                     )

        col_h = col.column(align=True)
        col_h.scale_y = .5
        col_h.alert = True

        tutorial_op = col_h.operator(
            'hg3d.draw_tutorial',
            text='Get Started!',
            depress=True,
            icon='FAKE_USER_ON'
        )
        tutorial_op.first_time = True
        tutorial_op.tutorial_name = 'get_started_tutorial'

    def _warning_header(self, context, layout) -> bool:
        """Checks if context is in object mode and if a body object can be
        found

        Args:
            context (AnyType): Blender context
            layout (AnyType): Main HumGen panel layout

        Returns:
            bool: returns True if problem was found, causing panel to only show
            these error messages
        """
       
        if not context.mode == 'OBJECT':
            layout.alert = True
            layout.label(text = 'HumGen only works in Object Mode')
            return True

        if self.hg_rig and 'no_body' in self.hg_rig:
            layout.alert = True
            layout.label(text = 'No body object found for this rig')
            return True
        
        return False

    def _draw_top_widget(self):
        hg_rig = self.hg_rig
        
        col = self.layout.column(align = True)
        
        row_h = col.row(align = True)
        row_h.scale_y = 1.5
        subrow_h = row_h.row(align = True)
        if hg_rig and hg_rig.HG.experimental:        
            subrow_h.alert = True
        
        #button showing name and gender of human
        subrow_h.operator('view3d.view_selected', 
                          text = self._get_header_label(hg_rig),
                          depress = bool(hg_rig)
                          )
        
        #show button for switching to experimental
        if hg_rig and in_creation_phase(hg_rig):
            self._experimental_mode_button(hg_rig, row_h)

        row = col.row(align=True)
        row.operator('hg3d.next_prev_human', text = 'Previous', icon = 'TRIA_LEFT').forward = False
        row.operator('hg3d.next_prev_human', text = 'Next', icon = 'TRIA_RIGHT').forward = True
        
        row = col.row(align=True)
        row.operator('hg3d.deselect', icon = 'RESTRICT_SELECT_ON')
        row.operator('hg3d.delete', text = 'Delete', icon = 'TRASH')
        
        if hg_rig:
            box = col.box()
            hair_systems = self._get_hair_systems(self.hg_rig.HG.body_obj, eyesystems=True)     
            self._draw_hair_children_switch(hair_systems, box)

    def _experimental_mode_button(self, hg_rig, row_h):
        subrow = row_h.row(align = True)
        is_expr = hg_rig.HG.experimental
        if not is_expr:
            subrow.alert = True
                
        subrow.operator('hg3d.experimental',
            text = '',
            icon = 'GHOST_{}'.format('DISABLED' if is_expr else 'ENABLED'),
            depress = True)

    def _get_header_label(self, hg_rig):
        if not hg_rig:
            label = 'No Human selected'          
        else:
            name = hg_rig.name.replace('HG_', '').replace('_RIGIFY', '')     
            gender = hg_rig.HG.gender.capitalize()
            label = f'This is {name} [{gender}]'
        return label


    #   ______ .______       _______     ___   .___________. _______ 
    #  /      ||   _  \     |   ____|   /   \  |           ||   ____|
    # |  ,----'|  |_)  |    |  |__     /  ^  \ `---|  |----`|  |__   
    # |  |     |      /     |   __|   /  /_\  \    |  |     |   __|  
    # |  `----.|  |\  \----.|  |____ /  _____  \   |  |     |  |____ 
    #  \______|| _| `._____||_______/__/     \__\  |__|     |_______|

    def _draw_starting_human_ui(self, layout):
        """UI that shows when no human is selected, with buttons for creating a
        new human.
        
        Shows a template icon view of all 'starting humans', a switch for male
        and female genders and a pink button to add the selected human
        """
        box = layout.box()
        
        col = box.column(align = True)
        col.label(text='Select a starting human')
        col.template_icon_view(self.sett, "pcoll_humans",
                               show_labels=True,
                               scale=10,
                               scale_popup=6
                               )   
        
        row = col.row()
        row.scale_y = 2
        row.prop(self.sett, 'gender',
                 expand = True
                 )

        col = box.column()
        col.scale_y = 2
        col.alert   = True
        col.operator('hg3d.startcreation',
                     icon = 'COMMUNITY',
                     depress = True
                     )
        
    def _draw_batch_marker_notification(self, layout):
        box = layout.box().column()
        box.scale_y = 0.7
        box.label(text = 'Go to the batch panel to', icon = 'INFO')
        box.label(text = 'generate humans from this')
        box.label(text = 'batch marker.')
        box.separator()
        box.label(text = '(Switch at the top of the UI)')


    # .______     ______    _______  ____    ____ 
    # |   _  \   /  __  \  |       \ \   \  /   / 
    # |  |_)  | |  |  |  | |  .--.  | \   \/   /  
    # |   _  <  |  |  |  | |  |  |  |  \_    _/   
    # |  |_)  | |  `--'  | |  '--'  |    |  |     
    # |______/   \______/  |_______/     |__|

    def _draw_creation_section(self):
        """First section shown to the user after adding a human
        
        Shows sliders for body proportion shapekeys, including a randomize
        button for these sliders
        Also shows a collapsable menu for changing individual body part size 
        """
        sett = self.sett
        
        spoiler_open, box = draw_spoiler_box(self, 'body')
        if not spoiler_open:   
            return
        
        col = box.column()
        col.scale_y = 1.25

        col_h = col.column()
        col_h.scale_y = 1.5
        col_h.operator('hg3d.random',
                       text = 'Random',
                       icon = 'FILE_REFRESH'
                       ).random_type = 'body_type'

        col.separator()
        
        hg_body = self.hg_rig.HG.body_obj 
        flow = get_flow(sett, col)
       
        sks = hg_body.data.shape_keys.key_blocks
        bp_sks = [sk for sk in sks if sk.name.startswith('bp_')]
        for sk in bp_sks:         
            flow.prop(sk, 'value',
                      text = sk.name.replace('bp_', '').capitalize(),
                      expand = True
                      )

        col.separator()
        
        self._individual_scale_ui(col, sett)

    def _individual_scale_ui(self, box, sett):
        """Collapsable menu showing sliders to change bone scale of different
        body parts of the HumGen human

        Args:
            box (UILayout): Box layout of body section
            sett (Scene.HG3D): Humgen properties
        """
        is_open, boxbox = draw_sub_spoiler(
            box, sett, 'indiv_scale_ui', 'Individual scaling')
        if not is_open:
            return 
        
        col = boxbox.column(align = True)
        col.use_property_split = True
        col.use_property_decorate = False

        col.prop(sett, 'head_size', text = 'Head', slider = True)
        col.prop(sett, 'neck_size', text = 'Neck', slider = True)
        col.separator()
        col.prop(sett, 'chest_size', text = 'Chest', slider = True)
        col.prop(sett, 'shoulder_size', text = 'Shoulders', slider = True)
        col.prop(sett, 'breast_size', text = 'Breasts', slider = True)
        col.prop(sett, 'hips_size', text = 'Hips', slider = True)
        col.separator()
        col.prop(sett, 'upper_arm_size', text = 'Upper Arm', slider = True)
        col.prop(sett, 'forearm_size', text = 'Forearm', slider = True)
        col.prop(sett, 'hand_size', text = 'Hands', slider = True)
        col.separator()
        col.prop(sett, 'thigh_size', text = 'Thighs', slider = True)
        col.prop(sett, 'shin_size', text = 'Shins', slider = True)
        col.separator()
        
        col.label(text = 'Type number for stronger values', icon = 'INFO')

    #  __       _______ .__   __.   _______ .___________. __    __  
    # |  |     |   ____||  \ |  |  /  _____||           ||  |  |  | 
    # |  |     |  |__   |   \|  | |  |  __  `---|  |----`|  |__|  | 
    # |  |     |   __|  |  . `  | |  | |_ |     |  |     |   __   | 
    # |  `----.|  |____ |  |\   | |  |__| |     |  |     |  |  |  | 
    # |_______||_______||__| \__|  \______|     |__|     |__|  |__|

    def _draw_length_section(self):
        """Section showing a slider for changing human length and a label that
        shows the active length in metric and imperial measurements
        """
        spoiler_open, box = draw_spoiler_box(self, 'length')
        if not spoiler_open:   
            return
    
        col = box.column(align = True)
  
        length_m = self.hg_rig.dimensions[2]
        length_feet   = length_m / 0.3048
        length_inches = int(length_feet*12.0 - int(length_feet)*12.0)
        length_label  = (str(round(length_m, 2))
                         + ' m   |   '
                         + str(int(length_feet))
                         + "'"
                         + str(length_inches)
                         +'"'
                         ) #example: 1.83m   |   5'11"

        row           = col.box().row()
        row.scale_y   = 2
        row.alignment = 'CENTER'
        row.label(text = length_label,
                  icon = 'EMPTY_SINGLE_ARROW'
                  )

        row = col.row(align= True)
        row.scale_y = 2
        row.scale_x = 1.2
        row.prop(self.sett, 'human_length', text = 'Length [cm]')
        row.operator('hg3d.randomlength', text = '', icon = 'FILE_REFRESH')


    #  _______    ___       ______  _______ 
    # |   ____|  /   \     /      ||   ____|
    # |  |__    /  ^  \   |  ,----'|  |__   
    # |   __|  /  /_\  \  |  |     |   __|  
    # |  |    /  _____  \ |  `----.|  |____ 
    # |__|   /__/     \__\ \______||_______|

    def _draw_face_section(self):
        """Section showing sliders for all facial shapekeys, all categorized
        in collapsable tabs.
        """
        sett = self.sett
        
        spoiler_open, box = draw_spoiler_box(self, 'face')
        if not spoiler_open or not box.enabled:   
            return

        col = box.column()
        col.scale_y = 1.5
        row = col.row(align = True)
        row.operator('hg3d.random', text = 'Randomize all').random_type = 'face_all'
        row.operator('hg3d.resetface', text = '', icon = 'LOOP_BACK')
        
        col = box.column(align= True)
        
        col.label(text = 'Upper Face:')
        flow_u_skull = self._get_ff_col(col, 'Upper Skull', 'u_skull')
        flow_eyes = self._get_ff_col(col, 'Eyes', 'eyes')
        flow_ears = self._get_ff_col(col, 'Ears', 'ears')
        flow_nose = self._get_ff_col(col, 'Nose', 'nose')
        
        col.separator()
        col.label(text = 'Lower Face:')
        flow_l_skull = self._get_ff_col(col, 'Lower Skull', 'l_skull')
        flow_mouth = self._get_ff_col(col, 'Mouth', 'mouth')
        flow_cheeks = self._get_ff_col(col, 'Cheeks', 'cheeks')  
        flow_jaw = self._get_ff_col(col, 'Jaw', 'jaw')
        flow_chin = self._get_ff_col(col, 'Chin', 'chin')       

        col.separator()
        col.label(text = 'Other:')            
        flow_custom = self._get_ff_col(col, 'Custom', 'custom')   
        flow_presets = self._get_ff_col(col, 'Presets', 'presets')       
   
        hg_body = self.hg_rig.HG.body_obj
        face_sks = [sk for sk in hg_body.data.shape_keys.key_blocks 
                    if sk.name.startswith('ff')
                    ]     
        prefix_dict = {
            'ff_a'      : (flow_u_skull, sett.ui_u_skull),
            'ff_b'      : (flow_u_skull, sett.ui_u_skull),
            'ff_c_eye'  : (flow_eyes, sett.ui_eyes),
            'ff_d'      : (flow_l_skull, sett.ui_l_skull),
            'ff_e_nose' : (flow_nose, sett.ui_nose),
            'ff_f_lip'  : (flow_mouth, sett.ui_mouth),
            'ff_g_chin' : (flow_chin, sett.ui_chin),
            'ff_h_cheek': (flow_cheeks, sett.ui_cheeks),
            'ff_i_jaw'  : (flow_jaw, sett.ui_jaw),
            'ff_j_ear'  : (flow_ears, sett.ui_ears),
            'ff_x'      : (flow_custom, sett.ui_custom),
            }
             
        #iterate over each collapsable menu, adding shapekey sliders to them     
        for prefix in prefix_dict:
            if not prefix_dict[prefix][1]:
                continue
            for sk in [sk for sk in face_sks if sk.name.startswith(prefix)]:
                prefix_dict[prefix][0].prop(
                    sk, 'value',
                    text = self._build_sk_name(sk.name, prefix)
                    )

        #menu for all shapekeys starting with pr_ (preset) prefix
        if sett.ui_presets:
            sks = hg_body.data.shape_keys.key_blocks
            for sk in [sk for sk in sks if sk.name.startswith('pr_')]:
                flow_presets.prop(
                    sk, 'value',
                    text = sk.name.replace('pr_', '').replace('_', ' ').capitalize()
                    )


    def _build_sk_name(self, sk_name, prefix) -> str:
        """Builds a displayable name from internal shapekey names.
        
        Removes prefix->Replaces underscores with space->Removes .Transferred 
        suffix from age shapekey->Title case the name

        Args:
            sk_name (str): internal name of the shapekey
            prefix (str): category prefix of the shapekey to be removed

        Returns:
            str: Display name of shapekey
        """
        for r in ((prefix, ''), ("_", ' '), ('.Transferred', '')):
            sk_name = sk_name.replace(*r)
        
        return sk_name.title()

    def _get_ff_col(self, layout, categ_name, is_open_propname)->bpy.types.UILayout:
        """Creates a collapsable box for passed shapekey category

        Args:
            layout (bpy.types.layout): layout.box of the facial features section
            categ_name (str): Name of this shapekey category to be displayed
            is_open_propname (str): name of the settings bool that opens and 
            closes the box

        Returns:
            UILayout: Column inside collapsable box
        """
        sett = self.sett
        boxbox = layout.box()
        boxbox.scale_y = 1 if self.pref.compact_ff_ui else 1.5 
       
        ui_bools = {
            'nose'   : sett.ui_nose,
            'u_skull': sett.ui_u_skull,
            'chin'   : sett.ui_chin,
            'mouth'  : sett.ui_mouth,
            'eyes'   : sett.ui_eyes,
            'cheeks' : sett.ui_cheeks,
            'l_skull': sett.ui_l_skull,
            'jaw'    : sett.ui_jaw,
            'ears'   : sett.ui_ears,
            'other'  : sett.ui_other,
            'custom' : sett.ui_custom,
            'presets': sett.ui_presets
            }

        row = boxbox.row()
        row.prop(
            sett, 'ui_{}'.format(is_open_propname),
            text = categ_name,
            icon="TRIA_DOWN" if ui_bools[is_open_propname] else "TRIA_RIGHT",
            toggle=True,
            emboss = False
            )
        if is_open_propname != 'presets':
            row.operator(
                'hg3d.random',
                text = '',
                icon = 'FILE_REFRESH',
                emboss = False
                ).random_type = 'face_{}'.format(is_open_propname)
        else:
            row.operator(
                'hg3d.showinfo',
                text = '',
                icon = 'BLANK1',
                emboss = False
                )
        
        col = layout.column(align = True)
        col.scale_y = 1 if self.pref.compact_ff_ui else 1.5 
        
        return col

    #      _______. __  ___  __  .__   __. 
    #     /       ||  |/  / |  | |  \ |  | 
    #    |   (----`|  '  /  |  | |   \|  | 
    #     \   \    |    <   |  | |  . `  | 
    # .----)   |   |  .  \  |  | |  |\   | 
    # |_______/    |__|\__\ |__| |__| \__|

    def _draw_skin_section(self):
        """Collapsable section with options for changing the shader of the human
        """
        spoiler_open, box = draw_spoiler_box(self, 'skin')
        if not spoiler_open:   
            return
        
        sett    = self.sett
        hg_body = self.hg_rig.HG.body_obj
        mat     = hg_body.data.materials[0]
        nodes   = mat.node_tree.nodes

        if 'hg_baked' in self.hg_rig:
            box.label(text = 'Textures are baked', icon = 'INFO')
            return

        self._draw_texture_subsection(sett, box)
        self._draw_main_skin_subsection(sett, box, nodes)
        self._draw_light_dark_subsection(sett, box, nodes)
        self._draw_freckles_subsection(sett, box, nodes)
        self._draw_beautyspots_subsection(sett, box, nodes)
        self._draw_age_subsection(sett, box, nodes)

        gender = self.hg_rig.HG.gender     
        if gender == 'female':
            self._draw_makeup_subsection(sett, box, nodes)
        else:
            self._draw_beard_shadow_subsection(sett, box, nodes)

    def _draw_main_skin_subsection(self, sett, box, nodes):
        """Collapsable section with main sliders of skin effects

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of the skin section
            nodes (Shadernode list): All nodes in the .human material
        """
        is_open, boxbox = draw_sub_spoiler(
            box, sett, 'main_skin_ui', 'Main settings')
        if not is_open:
            return 

        col = boxbox.column(align = True)
        col.scale_y = 1.2
        
        col.operator('hg3d.random',
                       text = 'Randomize skin',
                       icon = 'FILE_REFRESH'
                       ).random_type = 'skin'
        
        col.separator()
        
        tone_node = nodes['Skin_tone']
        col.prop(tone_node.inputs[1], 'default_value',
                 text = 'Tone',
                 slider = True
                 )
        col.prop(tone_node.inputs[2], 'default_value',
                 text = 'Redness',
                 slider = True
                 )
        if len(tone_node.inputs) > 3:
            col.prop(tone_node.inputs[3], 'default_value',
                    text = 'Saturation',
                    slider = True
                    )

        col.separator()
        
        normal_node = nodes['Normal Map']
        r_node =  nodes['R_Multiply']
        col.prop(normal_node.inputs[0], 'default_value',
                 text = 'Normal Strength'
                 ) 
        col.prop(r_node.inputs[1], 'default_value',
                 text = 'Roughness mult.'
                 )
        
        col.separator()
        
        row = col.row()
        row.label(text = 'Subsurface scattering')
        row.operator('hg3d.showinfo',
                     text = '',
                     icon ='QUESTION',
                     emboss = False
                     ).info = 'subsurface'
        
        row = col.row(align = True)
        row.prop(sett, 'skin_sss',
                 expand = True
                 )

        col.label(text = 'Underwear:')
        row = col.row(align = True)
        row.prop(sett, 'underwear_switch',
                 expand = True
                 )

    def _draw_texture_subsection(self, sett, box):
        """Shows a template_icon_view for different texture options

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of the skin section
        """
        
        is_open, boxbox = draw_sub_spoiler(
            box, sett, 'texture_ui', 'Texture sets')
        if not is_open:
            return       

        col = boxbox.column()
        col.template_icon_view(sett, "pcoll_textures",
                               show_labels=True,
                               scale=10,
                               scale_popup=6
                               )  
        col.prop(sett, 'texture_library', text = 'Library')

    def _draw_light_dark_subsection(self, sett, box, nodes):
        """Collapsable section with sliders for dark and light areas on the skin

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of the skin section
            nodes (Shadernode list): All nodes in the .human material
        """
        
        is_open, boxbox = draw_sub_spoiler(
            box, sett, 'light_dark_ui', 'Light & dark areas')
        if not is_open:
            return 

        light_hsv = nodes['Lighten_hsv']
        dark_hsv = nodes['Darken_hsv']

        col = boxbox.column(align = False)
        col.scale_y = 1.2
        col.prop(dark_hsv.inputs['Value'], 'default_value',
                 text = 'Dark areas',
                 slider = True
                 )
        col.prop(light_hsv.inputs['Value'], 'default_value',
                 text = 'Light areas',
                 slider = True
                 )

    def _draw_age_subsection(self, sett, box, nodes):
        """Collapsable section with sliders age effects

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of the skin section
            nodes (Shadernode list): All nodes in the .human material
        """
        is_open, boxbox = draw_sub_spoiler(
            box, sett, 'age_ui', 'Age')
        if not is_open:
            return 

        hg_body = self.hg_rig.HG.body_obj
        sk = hg_body.data.shape_keys.key_blocks
        
        age_sk = sk['age_old.Transferred']
        age_node = nodes['HG_Age']

        col = boxbox.column(align = True)
        col.scale_y = 1.2
        col.prop(age_sk, 'value',
                 text = 'Skin sagging [Mesh]',
                 slider = True
                 )
        col.prop(age_node.inputs[1], 'default_value',
                 text = 'Wrinkles',
                 slider = True
                 )

    def _draw_freckles_subsection(self, sett, box, nodes):
        """Collapsable section with sliders for freckles

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of the skin section
            nodes (Shadernode list): All nodes in the .human material
        """
        is_open, boxbox = draw_sub_spoiler(
            box, sett, 'freckles_ui', 'Freckles')
        if not is_open:
            return 

        freckles_node = nodes['Freckles_control']
        splotches_node = nodes['Splotches_control']

        col = boxbox.column(align = True)
        col.scale_y = 1.2
        col.prop(freckles_node.inputs['Pos2'], 'default_value',
                 text = 'Freckles',
                 slider = True
                 )
        col.prop(splotches_node.inputs['Pos2'], 'default_value',
                 text = 'Splotches',
                 slider = True
                 )


    def _draw_makeup_subsection(self, sett, box, nodes):
        """Collapsable section with sliders for makeup

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of the skin section
            nodes (Shadernode list): All nodes in the .human material
        """
        
        is_open, boxbox = draw_sub_spoiler(
            box, sett, 'makeup_ui', 'Makeup')
        if not is_open:
            return 
        
        makeup_node = nodes['Gender_Group']
        
        #TODO make loop. First try failed, don't remember why
        flow = self._get_skin_flow(boxbox, 'Foundation:')
        flow.prop(makeup_node.inputs['Foundation Amount'], 'default_value',
                  text = 'Amount',
                  slider = True
                  )
        flow.prop(makeup_node.inputs['Foundation Color'], 'default_value',
                  text = 'Color'
                  )

        flow = self._get_skin_flow(boxbox, 'Blush:')
        flow.prop(makeup_node.inputs['Blush Opacity'], 'default_value',
                  text = 'Opacity',
                  slider = True
                  )
        flow.prop(makeup_node.inputs['Blush Color'], 'default_value',
                  text = 'Color'
                  )

        flow = self._get_skin_flow(boxbox, 'Eyeshadow:')
        flow.prop(makeup_node.inputs['Eyeshadow Opacity'], 'default_value',
                  text = 'Opacity',
                  slider = True
                  )
        flow.prop(makeup_node.inputs['Eyeshadow Color'], 'default_value',
                  text = 'Color'
                  )
        
        flow = self._get_skin_flow(boxbox, 'Lipstick:')
        flow.prop(makeup_node.inputs['Lipstick Opacity'], 'default_value',
                  text = 'Opacity',
                  slider = True
                  )
        flow.prop(makeup_node.inputs['Lipstick Color'], 'default_value',
                  text = 'Color'
                  )

        flow = self._get_skin_flow(boxbox, 'Eyeliner:')
        flow.prop(makeup_node.inputs['Eyeliner Opacity'], 'default_value',
                  text = 'Opacity',
                  slider = True
                  )
        flow.prop(makeup_node.inputs['Eyeliner Color'], 'default_value',
                  text = 'Color'
                  )

        return #TODO hide eyebrow section until issue resolved
        flow = self.skin_section_flow(boxbox, 'Eyebrows:')

        flow.prop(makeup_node.inputs['Eyebrows Opacity'], 'default_value', text = 'Opacity', slider = True)
        flow.prop(makeup_node.inputs['Eyebrows Color'], 'default_value', text = 'Color')

    def _get_skin_flow(self, layout, label):
        """Generates a property split layout

        Args:
            layout (UILayout): boxbox from makeup/beard section
            label (str): Name for the ui section

        Returns:
            UILayout: layout with property split and title bar
        """
        row = layout.row()
        row.alignment = 'CENTER'
        row.label(text = label, icon = 'HANDLETYPE_AUTO_CLAMP_VEC')
        
        flow = get_flow(self.sett, layout)
        flow.scale_y = 1.2

        return flow     

    def _draw_beautyspots_subsection(self, sett, box, nodes):
        """Collapsable section with sliders for beautyspots

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of the skin section
            nodes (Shadernode list): All nodes in the .human material
        """
        
        if platform == 'darwin': #not compatible with MacOS 8-texture material
            return

        is_open, boxbox = draw_sub_spoiler(
            box, sett, 'beautyspots_ui', 'Beauty Spots')
        if not is_open:
            return        

        bs_node = nodes['BS_Control']
        opacity_node = nodes['BS_Opacity']
        
        col = boxbox.column(align = True)
        col.scale_y = 1.2
        col.prop(bs_node.inputs[2], 'default_value',
                 text = 'Amount',
                 slider = True
                 )
        col.prop(opacity_node.inputs[1], 'default_value',
                 text = 'Opacity', 
                 slider = True
                 )
        col.prop(bs_node.inputs[1], 'default_value',
                 text = 'Seed [Randomize]'
                 )

    def _draw_beard_shadow_subsection(self, sett, box, nodes):
        """Collapsable section with sliders for beard shadow

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of the skin section
            nodes (Shadernode list): All nodes in the .human material
        """
        is_open, boxbox = draw_sub_spoiler(
            box, sett, 'beard_shadow_ui', 'Beard Shadow')
        if not is_open:
            return 

        beard_node = nodes['Gender_Group']

        flow = get_flow(sett, boxbox)
        flow.scale_y = 1.2
        flow.prop(beard_node.inputs[2], 'default_value',
                  text = 'Mustache',
                  slider = True
                  )   
        flow.prop(beard_node.inputs[3], 'default_value',
                  text = 'Beard',
                  slider = True
                  )   

    #  ___________    ____  _______     _______.
    # |   ____\   \  /   / |   ____|   /       |
    # |  |__   \   \/   /  |  |__     |   (----`
    # |   __|   \_    _/   |   __|     \   \    
    # |  |____    |  |     |  |____.----)   |   
    # |_______|   |__|     |_______|_______/

    def _draw_eyes_section(self):
        """Options for changing eyebrows and eye shader
        """
        spoiler_open, box = draw_spoiler_box(self, 'eyes')    
        if not spoiler_open:   
            return

        if 'hg_baked' in self.hg_rig:
            box.label(text = 'Textures are baked', icon = 'INFO') 
            self._draw_eyebrow_switch(box)
            return

        hg_eyes = [child for child in self.hg_rig.children if 'hg_eyes' in child][0]
        mat = hg_eyes.data.materials[1]
        nodes = mat.node_tree.nodes

        boxbox = box.box()
        row = boxbox.row()
        row.alignment = 'CENTER'
        row.label(text = 'Color:', icon = 'RESTRICT_COLOR_OFF')
        
        col = boxbox.column(align = True)
        col.use_property_split = True
        col.use_property_decorate = False
        row = col.row(align = True)
        row.prop(nodes['HG_Eye_Color'].inputs[2], 'default_value',
                 text = 'Iris Color'
                 )
        row.operator('hg3d.random', text = '', icon = 'FILE_REFRESH').random_type = 'iris_color'
        col.prop(nodes['HG_Scelera_Color'].inputs[2],
                 'default_value', text = 'Sclera Color'
                 )

        boxbox = self._draw_eyebrow_switch(box)

        eye_systems = self._get_eye_systems(self.hg_rig.HG.body_obj)
        
        self._draw_hair_length_ui(eye_systems, box)

    def _draw_eyebrow_switch(self, box) -> bpy.types.UILayout:
        """UI for switching between different types of eyebrows

        Args:
            box (UILayout): eye section layout.box

        Returns:
            UILayout: box in box for other hair controls to be placed in
        """
        boxbox = box.box()
        
        row = boxbox.row()
        row.alignment = 'CENTER'
        hair_icon = ('OUTLINER_OB_CURVES' if bpy.app.version >= (3, 2, 0) 
                    else "OUTLINER_OB_HAIR")
        row.label(text = 'Eyebrows:', icon = hair_icon)
        row = boxbox.row(align = True)
        row.operator('hg3d.eyebrowswitch',
                     text = 'Previous',
                     icon = 'TRIA_LEFT'
                     ).forward = False
        row.operator('hg3d.eyebrowswitch',
                     text = 'Next',
                     icon = 'TRIA_RIGHT'
                     ).forward = True
        
        return boxbox

    def _get_eye_systems(self, body_obj) -> list:
        """Get a list of all particle systems belojnging to eyeborws and eyelashes

        Args:
            body_obj (Object): HumGen body object

        Returns:
            list: list of modifiers belonging to eyebrow and eyelash systems
        """
        eye_systems = []
        
        for mod in body_obj.modifiers:
            if (mod.type == 'PARTICLE_SYSTEM' 
                and mod.particle_system.name.startswith(('Eyebrows', 'Eyelashes')) 
                and (mod.show_viewport or mod.show_render)
                ):
                eye_systems.append(mod.particle_system)
        
        return eye_systems

    
   
    #  __    __       ___       __  .______      
    # |  |  |  |     /   \     |  | |   _  \     
    # |  |__|  |    /  ^  \    |  | |  |_)  |    
    # |   __   |   /  /_\  \   |  | |      /     
    # |  |  |  |  /  _____  \  |  | |  |\  \----.
    # |__|  |__| /__/     \__\ |__| | _| `._____|

    def _draw_hair_section(self, context):
        spoiler_open, box = draw_spoiler_box(self, 'hair')
        if not spoiler_open:
            return
        
        sett = self.sett
        hg_rig   = find_human(context.active_object)
        body_obj = hg_rig.HG.body_obj

        hair_systems = self._get_hair_systems(body_obj)

        box.template_icon_view(
            sett, "pcoll_hair",
            show_labels=True,
            scale=10,
            scale_popup=6
            )   
        
        col_h = box.column()
        col_h.scale_y =1.5
        col_h.prop(sett, 'hair_sub', text = '')
        if hg_rig.HG.gender == 'male':
            self._draw_facial_hair_section(box, sett)
        
        self._draw_hair_length_ui(hair_systems, box)
        self._draw_hair_material_ui(box)
        
        return #disable hair cards UI until operator works
        
        if hair_systems:
            self._draw_hair_cards_ui(box)

    def _draw_facial_hair_section(self, box, sett):
        """shows template_icon_view for facial hair systems

        Args:
            box (UILayout): box of hair section
            sett (PropertyGroup): HumGen props
        """
        
        
        is_open, boxbox = draw_sub_spoiler(
            box, sett, 'face_hair_ui', 'Face Hair')
        if not is_open:
            return 
        col=box.column(align=True)
        
        col.template_icon_view(
            sett, "pcoll_face_hair",
            show_labels=True,
            scale=10,
            scale_popup=6
            )  
        
        col_h = col.column()
        col_h.scale_y =1.5
        col_h.prop(sett, 'face_hair_sub', text = '')

    def _draw_hair_children_switch(self, hair_systems, layout):
        """ Draws a switch for turning children to render amount or back to 1

        Args:
            hair_systems (list): List of hair particle systems 
            layout (UILayout): layout to draw switch in
        """
        
        
        row = layout.row(align = True)
        if not hair_systems:
            row.label(text = 'No hair systems found')
            return
        
        row.label(text = ('Hair children are hidden' 
                          if hair_systems[0].settings.child_nbr <= 1 
                          else 'Hair children are visible')
                  )
        row.operator('hg3d.togglechildren',
                     text = '',
                     icon=('HIDE_ON' 
                           if hair_systems[0].settings.child_nbr <= 1 
                           else 'HIDE_OFF'
                           )
                     )
        
        row.separator()
        
        row.operator('hg3d.showinfo',
                     icon = 'QUESTION',
                     emboss = False
                     ).info = 'hair_children'

    def _draw_hair_length_ui(self, hair_systems, box):
        """shows a collapsable list of hair systems, with a slider for length

        Args:
            hair_systems (list): list of particle hair systems
            box (UILayout): layout.box of hair section
        """
        boxbox = box.box()
        boxbox.prop(
            self.sett, 'hair_length_ui',
            icon="TRIA_DOWN" if self.sett.hair_length_ui else "TRIA_RIGHT",
            emboss=False,
            toggle=True
            )
        if not self.sett.hair_length_ui:
            return
        
        if not hair_systems:
            box.label(text = 'No hairstyles loaded')
            return
        
        flow = get_flow(self.sett, box)
        for ps in hair_systems: 
            ps_name = ps.name.replace('fh_', '').replace('_', ' ').title()
            
            row = flow.row()
            row.prop(
                ps.settings, 'child_length',
                text = ps_name
                )
            row.operator(
                'hg3d.removehair',
                text = '',
                icon = 'TRASH'
                ).hair_system = ps.name

    def _draw_hair_material_ui(self, box):
        """draws subsection with sliders for the three hair materials

        Args:
            box (UILayout): layout.box of hair section
        """
        boxbox = box.box()
        boxbox.prop(
            self.sett, 'hair_mat_ui',
            icon="TRIA_DOWN" if self.sett.hair_mat_ui else "TRIA_RIGHT",
            emboss=False,
            toggle=True
            )        
        if not self.sett.hair_mat_ui:
            return

        gender = self.hg_rig.HG.gender
   
        categ = (self.sett.hair_mat_male 
                 if gender == 'male' 
                 else self.sett.hair_mat_female
                 )

        mat_names = {
            'eye' : '.HG_Hair_Eye',
            'face': '.HG_Hair_Face',
            'head': '.HG_Hair_Head'
            }
        hair_mat = next(
            mat for mat in self.hg_rig.HG.body_obj.data.materials
            if mat.name.startswith(mat_names[categ])
            )
        if 'HG_Hair_V3' in [n.name for n in hair_mat.node_tree.nodes]:
            hair_node = hair_mat.node_tree.nodes['HG_Hair_V3']
            new_hair_node = True
        elif 'HG_Hair_V2' in [n.name for n in hair_mat.node_tree.nodes]:
            hair_node = hair_mat.node_tree.nodes['HG_Hair_V2']
            new_hair_node = True
        else:
            hair_node = hair_mat.node_tree.nodes['HG_Hair']
            new_hair_node = False   
        
        if new_hair_node:
            boxbox.prop(self.sett, 'hair_shader_type', text = 'Shader')        
        

        row = boxbox.row(align = True)
        row.scale_y = 1.5
        row.prop(self.sett, 'hair_mat_{}'.format(gender),
                 expand = True
                 )

        col = boxbox.column()
        
        col.prop(hair_node.inputs['Hair Lightness'], 'default_value',
                 text = 'Lightness',
                 slider = True
                 )
        col.prop(hair_node.inputs['Hair Redness'], 'default_value',
                 text = 'Redness',
                 slider = True
                 )
        col.prop(hair_node.inputs['Roughness'], 'default_value',
                 text = 'Roughness'
                 )
        
        if 'Hue' in hair_node.inputs:
            col.prop(hair_node.inputs['Hue'], 'default_value',
                    text = 'Hue (For dyed hair)'
                    )            
        
        if categ == 'eye':
            return
        
        col.label(text = 'Effects:')
        col.prop(hair_node.inputs['Pepper & Salt'], 'default_value',
                 text = 'Pepper & Salt',
                 slider = True
                 )
        col.prop(hair_node.inputs['Roots'], 'default_value',
                 text = 'Roots',
                 slider = True
                 )
        
        if hair_node.inputs['Roots'].default_value > 0:
            col.prop(hair_node.inputs['Root Lightness'],
                     'default_value',
                     text = 'Root Lightness'
                     )
            col.prop(hair_node.inputs['Root Redness'], 'default_value',
                     text = 'Root Redness'
                     )
            if 'Roots Hue' in hair_node.inputs:
                col.prop(hair_node.inputs['Roots Hue'], 'default_value',
                        text = 'Root Hue'
                        )   

    def _draw_hair_cards_ui(self, box):
        """draws button for adding hair cards

        Args:
            box (UILayout): layout.box of hair section
        """
        boxbox = box.box()
        boxbox.prop(
            self.sett, 'hair_cards_ui',
            icon="TRIA_DOWN" if self.sett.hair_cards_ui else "TRIA_RIGHT",
            emboss=False,
            toggle=True)

        if self.sett.hair_cards_ui:
            box.operator('hg3d.haircards')

    def _get_hair_systems(self, body_obj, eyesystems = False) -> list:
        """get a list of hair systems on this object

        Args:
            body_obj (Object): HumGen body object, can be any mesh object

        Returns:
            list: list of hair particle systems
        """
        
        hair_systems = []
        for mod in body_obj.modifiers:
            if (mod.type == 'PARTICLE_SYSTEM'
                and (eyesystems
                    or not mod.particle_system.name.startswith(
                    ('Eyebrows', 'Eyelashes'))
                    )
                ):
                hair_systems.append(mod.particle_system)
        
        return hair_systems

    def _draw_finish_creation_button(self, layout):
        """pink button to finish creation phase

        Args:
            layout (UILayout): layout to draw button in
        """
        col = layout.column() 
        col.alert   = True
        col.scale_y = 1.5
        col.operator('hg3d.finishcreation',
                    text = 'Finish Creation Phase' ,
                    icon = 'FILE_ARCHIVE',
                    depress = True
                    )


#   ______ .______       _______     ___   .___________. __    ______   .__   __.    .______        ___       ______  __  ___  __    __  .______   
#  /      ||   _  \     |   ____|   /   \  |           ||  |  /  __  \  |  \ |  |    |   _  \      /   \     /      ||  |/  / |  |  |  | |   _  \  
# |  ,----'|  |_)  |    |  |__     /  ^  \ `---|  |----`|  | |  |  |  | |   \|  |    |  |_)  |    /  ^  \   |  ,----'|  '  /  |  |  |  | |  |_)  | 
# |  |     |      /     |   __|   /  /_\  \    |  |     |  | |  |  |  | |  . `  |    |   _  <    /  /_\  \  |  |     |    <   |  |  |  | |   ___/  
# |  `----.|  |\  \----.|  |____ /  _____  \   |  |     |  | |  `--'  | |  |\   |    |  |_)  |  /  _____  \ |  `----.|  .  \  |  `--'  | |  |      
#  \______|| _| `._____||_______/__/     \__\  |__|     |__|  \______/  |__| \__|    |______/  /__/     \__\ \______||__|\__\  \______/  | _|

    def draw_creation_backup_section(self):  
        """Se3ction for options that are still accesible from creation phase
        """
        spoiler_open, box = draw_spoiler_box(self, 'creation_phase')
        if not spoiler_open:
            return
        
        sett = self.sett
        hg_icons = preview_collections["hg_icons"]

        col_h = box.column()
        col_h.scale_y = 1.5
        col_h.alert= True
        col_h.operator('hg3d.revert',
                       text = 'Revert to Creation Phase',
                       icon = 'ERROR',
                       depress = True
                       )

        boxbox = box.box()
        
        row = boxbox.row()
        row.alignment = 'CENTER'
        row.label(text = 'Skin Settings', icon_value = hg_icons['skin'].icon_id)
        
        nodes = self.hg_rig.HG.body_obj.data.materials[0].node_tree.nodes
        
        self._draw_main_skin_subsection(sett, boxbox, nodes)
        
        if self.hg_rig.HG.gender == 'female':
            self._draw_makeup_subsection(sett, boxbox, nodes)

        if not self.pref.hair_section == 'creation':
            return
        
        boxbox = box.box()
        
        hair_systems = self._get_hair_systems(self.hg_rig.HG.body_obj, eyesystems = True)
        
        row = boxbox.row()
        row.alignment = 'CENTER'
        row.label(text = 'Hair Settings',
                  icon_value = hg_icons['hair'].icon_id
                  )
        
        
        
        self._draw_hair_length_ui(hair_systems, boxbox)
        self._draw_hair_material_ui(boxbox)
          

    #   ______  __        ______   .___________. __    __   __  .__   __.   _______ 
    #  /      ||  |      /  __  \  |           ||  |  |  | |  | |  \ |  |  /  _____|
    # |  ,----'|  |     |  |  |  | `---|  |----`|  |__|  | |  | |   \|  | |  |  __  
    # |  |     |  |     |  |  |  |     |  |     |   __   | |  | |  . `  | |  | |_ | 
    # |  `----.|  `----.|  `--'  |     |  |     |  |  |  | |  | |  |\   | |  |__| | 
    #  \______||_______| \______/      |__|     |__|  |__| |__| |__| \__|  \______|

    def _draw_clothing_section(self):
        """draws a template_icon_view for adding outfits
        """
        spoiler_open, box = draw_spoiler_box(self, 'clothing')
        if not spoiler_open:
            return

        sett = self.sett
        
        searchbox(sett, 'outfit', box)

        row = box.row(align = True)
        row.template_icon_view(
            sett, "pcoll_outfit",
            show_labels=True,
            scale=10,
            scale_popup=6
            )

        row_h = box.row(align = True)
        row_h.scale_y = 1.5
        row_h.prop(sett, 'outfit_sub', text = '')
        row_h.operator('hg3d.random',
                       text = 'Random',
                       icon = 'FILE_REFRESH'
                       ).random_type = 'outfit'

#      _______. __    __    ______    _______ 
#     /       ||  |  |  |  /  __  \  |   ____|
#    |   (----`|  |__|  | |  |  |  | |  |__   
#     \   \    |   __   | |  |  |  | |   __|  
# .----)   |   |  |  |  | |  `--'  | |  |____ 
# |_______/    |__|  |__|  \______/  |_______|

    def _draw_footwear_section(self):
        """draws a template icon view to add footwear to the human
        """
        spoiler_open, box = draw_spoiler_box(self, 'footwear')
        if not spoiler_open:
            return
        
        sett = self.sett
        
        searchbox(sett, 'footwear', box)

        row = box.row(align = True)
        row.template_icon_view(
            sett, "pcoll_footwear",
            show_labels=True,
            scale=10,
            scale_popup=6
            )

        row_h = box.row(align = True)
        row_h.scale_y = 1.5
        row_h.prop(sett, 'footwear_sub', text = '')
        row_h.operator('hg3d.random',
                       text = 'Random',
                       icon = 'FILE_REFRESH'
                       ).random_type = 'footwear'

    # .______     ______        _______. _______ 
    # |   _  \   /  __  \      /       ||   ____|
    # |  |_)  | |  |  |  |    |   (----`|  |__   
    # |   ___/  |  |  |  |     \   \    |   __|  
    # |  |      |  `--'  | .----)   |   |  |____ 
    # | _|       \______/  |_______/    |_______|

    #pose
    def _draw_pose_section(self):
        spoiler_open, box = draw_spoiler_box(self, 'pose')
        if not spoiler_open:
            return
       
        sett = self.sett
       
        row_h = box.row(align= True)
        row_h.scale_y = 1.5
        row_h.prop(sett, 'pose_choice', expand = True)

        if sett.pose_choice == 'library':
            self._draw_pose_library(sett, box)
        elif sett.pose_choice == 'rigify':
            self._draw_rigify_subsection(box)

    def _draw_rigify_subsection(self, box):
        """draws ui for adding rigify, context info if added

        Args:
            box (UILayout): layout.box of pose section
        """
        if 'hg_rigify' in self.hg_rig.data:
            box.label(text = 'Rigify rig active')
            box.label(text = 'Use Rigify add-on to adjust', icon = 'INFO')
        elif addon_utils.check("rigify"):
            box.label(text = 'Load facial rig first', icon = 'INFO')
            col = box.column()
            col.scale_y = 1.5
            col.alert = True
            col.operator('hg3d.rigify', depress = True)
        else:
            box.label(text = 'Rigify is not enabled')

    def _draw_pose_library(self, sett, box):
        """draws template_icon_view for selecting poses from the library

        Args:
            sett (PropertyGroup): HumGen properties
            box (UILayout): layout.box of pose section
        """
        
        if 'hg_rigify' in self.hg_rig.data:
            row = box.row(align = True)
            row.label(text = 'Rigify not supported', icon ='ERROR')
            row.operator('hg3d.showinfo',
                         text = '',
                         icon = 'QUESTION'
                         ).info = 'rigify_library'
            return
        
        searchbox(sett, 'poses', box)
        
        box.template_icon_view(
            sett, "pcoll_poses",
            show_labels=True,
            scale=10,
            scale_popup=6
            ) 
        
        row_h = box.row(align = True)
        row_h.scale_y = 1.5
        row_h.prop(sett, 'pose_sub', text = '')
        row_h.operator('hg3d.random',
                       text = 'Random',
                       icon = 'FILE_REFRESH'
                       ).random_type = 'poses'

    #  __________   ___ .______   .______       _______     _______.     _______. __    ______   .__   __. 
    # |   ____\  \ /  / |   _  \  |   _  \     |   ____|   /       |    /       ||  |  /  __  \  |  \ |  | 
    # |  |__   \  V  /  |  |_)  | |  |_)  |    |  |__     |   (----`   |   (----`|  | |  |  |  | |   \|  | 
    # |   __|   >   <   |   ___/  |      /     |   __|     \   \        \   \    |  | |  |  |  | |  . `  | 
    # |  |____ /  .  \  |  |      |  |\  \----.|  |____.----)   |   .----)   |   |  | |  `--'  | |  |\   | 
    # |_______/__/ \__\ | _|      | _| `._____||_______|_______/    |_______/    |__|  \______/  |__| \__|
    
    def _draw_expression_section(self): 
        """section for selecting expressions from template_icon_view or adding 
        facial rig
        """
        spoiler_open, box = draw_spoiler_box(self, 'expression')
        if not spoiler_open:
            return

        sett = self.sett

        row = box.row(align = True)
        row.scale_y = 1.5
        row.prop(sett, 'expression_type', expand = True)

        if sett.expression_type == '1click':
            self._draw_oneclick_subsection(box, sett)
        else:
            self._draw_frig_subsection(box)

    def _draw_oneclick_subsection(self, box, sett):
        if 'facial_rig' in self.hg_rig.HG.body_obj:
            box.label(text = 'Library not compatible with face rig')
            
            col = box.column()
            col.alert = True    
            col.scale_y = 1.5   
            col.operator('hg3d.removefrig',
                         text = 'Remove facial rig',
                         icon = 'TRASH',
                         depress = True
                         )
            return

        searchbox(sett, 'expressions', box)
        
        box.template_icon_view(
            sett, "pcoll_expressions",
            show_labels=True,
            scale=10,
            scale_popup=6
            )  
        
        row_h = box.row(align= True)
        row_h.scale_y = 1.5
        row_h.prop(sett, 'expressions_sub', text = '')
        row_h.operator('hg3d.random',
                       text = 'Random',
                       icon = 'FILE_REFRESH'
                       ).random_type = 'expressions'
        
        filtered_obj_sks = self.hg_rig.HG.body_obj.data.shape_keys
        if filtered_obj_sks:
            self._draw_sk_sliders_subsection(sett, box, filtered_obj_sks)  

    def _draw_sk_sliders_subsection(self, sett, box, filtered_obj_sks):
        """draws sliders for each non-corrective shapekey to adjust the strength

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of expression section
            obj_sks (list): list of non-basis and non-corrective shapekeys
        """
        expr_sks = [sk for sk in filtered_obj_sks.key_blocks
            if sk.name != 'Basis' 
            and not sk.name.startswith('cor')
            and not sk.name.startswith('eyeLook')
            ]
        if not expr_sks:
            return
        
        is_open, boxbox = draw_sub_spoiler(
            box, sett, 'expression_slider_ui', 'Strength')
        if not is_open:
            return 
        
        flow = get_flow(sett, box, animation = True)
        for sk in [sk for sk in expr_sks if not sk.mute]:
            display_name = sk.name.replace('expr_', '').replace('_', ' ') +':'
            
            row = flow.row(align = True)
            row.prop(sk, 'value', text = display_name.capitalize())
            row.operator('hg3d.removesk',
                         text = '',
                         icon = 'TRASH'
                         ).shapekey = sk.name

    def _draw_frig_subsection(self, box):
        """draws subsection for adding facial rig

        Args:
            box (UILayout): layout.box of expression section
        """
        col = box.column()
        if 'facial_rig' in self.hg_rig.HG.body_obj:
            col.label(text = 'Facial rig added')
            col.label(text = 'Use pose mode to adjust', icon = 'INFO')
            col_h = col.column()
            col_h.scale_y = 1.5
            tutorial_op = col_h.operator(
                'hg3d.draw_tutorial',
                text='ARKit tutorial',
                icon='HELP'
            )
            tutorial_op.first_time = False
            tutorial_op.tutorial_name = 'arkit_tutorial'
        else:
            col.scale_y = 2
            col.alert = True
            col.operator('hg3d.addfrig',
                         text = 'Add facial rig',
                         depress = True
                         )



    # .___  ___.      ___   .___________. _______ .______       __       ___       __      
    # |   \/   |     /   \  |           ||   ____||   _  \     |  |     /   \     |  |     
    # |  \  /  |    /  ^  \ `---|  |----`|  |__   |  |_)  |    |  |    /  ^  \    |  |     
    # |  |\/|  |   /  /_\  \    |  |     |   __|  |      /     |  |   /  /_\  \   |  |     
    # |  |  |  |  /  _____  \   |  |     |  |____ |  |\  \----.|  |  /  _____  \  |  `----.
    # |__|  |__| /__/     \__\  |__|     |_______|| _| `._____||__| /__/     \__\ |_______|

    #TODO add compatibility with any material, not just standard material
    def _draw_cloth_material_ui(self, context, layout):
        """draws ui for changing the material of the active clothing object

        Args:
            context (bpy.context): Blender context
            layout (UILayout): main HumGen panel layout
        """
        if 'hg_baked' in self.hg_rig:
            layout.label(text = 'Textures are baked', icon = 'INFO')
            return

        sett = self.sett
        hg_icons = preview_collections['hg_icons']

        col = layout.column(align = True)
        
        self._draw_clothmat_header(context, hg_icons, col)

        nodes = context.object.data.materials[0].node_tree.nodes
        control_node = nodes['HG_Control']

        self._draw_clothmat_color_subsection(layout, control_node)
        self._draw_clothmat_options_subsection(layout, control_node)
    
        if 'Pattern' in control_node.inputs:
            self._draw_pattern_subsection(sett, layout, control_node)

    def _draw_clothmat_header(self, context, hg_icons, col):
        """Draws header for the clothing material UI, with clothing name, 
        button to go back to normal UI and button to delete clothing item

        Args:
            context (bpy.context): Blender context
            hg_icons (list): icon preview collection 
            col (UILayout): column of clothing material UI
        """
        box = col.box().row()
        box.scale_y =1.5 
        box.alignment = 'CENTER'
        box.label(
            text = context.object.name.replace('_', ' ').replace('HG', ''),
            icon_value = (hg_icons['clothing'].icon_id 
                         if 'cloth' in context.object 
                         else hg_icons['footwear'].icon_id)
            )

        col.operator(
            'hg3d.backhuman',
            text= 'Go back to human',
            icon = 'RESTRICT_SELECT_OFF',
            depress = True
            )
        alert_col = col.column(align = True)
        alert_col.alert = True
        alert_col.operator(
            'hg3d.deletecloth',
            text = 'Delete clothing item',
            icon = 'TRASH',
            depress = True
            )

    def _draw_clothmat_color_subsection(self, layout, control_node):
        """draws subsection for changing colors of the different zones on this
        clothing material

        Args:
            layout (UILAyout): layout of clothmat section
            control_node (ShaderNodeGroup): node that controls the clot material
        """
        color_flow, _ = self.make_box_flow(layout, 'Colors', 'COLOR')
        
        for node_input in [control_node.inputs[i] for i in (4,5,6)]: 
            if node_input.name:           
                self._draw_color_row(color_flow, node_input)

    def _draw_color_row(self, color_flow, node_input):
        """Draws color picker and color randomize button on row

        Args:
            color_flow (UILayout): indented list where color pickers are placed
            node_input (ShaderNodeInput): input of the color value on group node
        """
        color_groups = tuple(['_{}'.format(name) for name in color_dict])     
        color_group = (
            node_input.name[-2:] 
            if node_input.name.endswith(color_groups) 
            else None
            )
        
        row = color_flow.row(align=False)
        row.prop(node_input, 'default_value',
                 text = node_input.name[:-3] if color_group else node_input.name
                 )
        
        if not color_group:
            return
        
        c_random = row.operator(
            'hg3d.color_random',
            text = '',
            icon = 'FILE_REFRESH'
            )
        c_random.input_name = node_input.name
        c_random.color_group = color_group

    def _draw_clothmat_options_subsection(self, layout, control_node):
        """draws sliders for roughness, normal and any custom values on group

        Args:
            layout (UILAyout): main layout of clothmat section
            control_node (ShaderNodeGroup): control node group of cloth material
        """
        flow, _ = self.make_box_flow(layout, 'Options', 'OPTIONS')
        
        for input_idx, node_input in enumerate(control_node.inputs):
            if ((input_idx  > 13 and not node_input.is_linked)
                or node_input.name in ['Roughness Multiplier', 'Normal Strength']
                ):
                flow.prop(
                    node_input, 'default_value',
                    text = node_input.name
                    )

    def _draw_pattern_subsection(self, sett, layout, control_node):
        """draws subsection for adding patterns to this clothing item

        Args:
            sett (PropertyGroup): HumGen props
            layout (UILayout): layout of clothmat section
            control_node (ShaderNodeGroup): control nodegroup of cloth material
        """
        p_flow, p_box = self.make_box_flow(layout, 'Pattern', 'NODE_TEXTURE')
        
        pattern = True if control_node.inputs[9].is_linked else False
        
        if pattern:
            self._draw_pattern_selector_ui(sett, control_node, p_flow)
            self._draw_pattern_color_ui(sett, control_node, p_flow)

        row = p_box.row(align = True)
        row.scale_y = 1.3
        row.operator('hg3d.pattern',
                     text = 'Remove' if pattern else 'Add Pattern',
                     icon = 'TRASH' if pattern else 'TEXTURE'
                     ).add = False if pattern else True
        
        if pattern:
            row.popover(panel='HG_PT_ROT_LOC_SCALE',
                        text='Transform',
                        icon='ORIENTATION_GLOBAL'
                        )

    def _draw_pattern_selector_ui(self, sett, control_node, p_flow):
        """draws template_icon_view for adding patterns

        Args:
            sett (PropertyGroup): HumGen props
            control_node (ShaderNodeGroup): control nodegroup of cloth material
            p_flow (UILayout): layout where the pattern stuff is drawn in
        """
        searchbox(sett, 'patterns', p_flow)

        col = p_flow.column(align = False)
        col.scale_y = .8
        col.template_icon_view(
            sett, "pcoll_patterns",
            show_labels=True,
            scale=5,
            scale_popup=6
            )
            
    def _draw_pattern_color_ui(self, sett, control_node, p_flow):
        """shows sliders and options for manipulating the pattern colors

        Args:
            sett (PropertyGroup): HumGen props
            control_node (ShaderNodeGRoup): control nodegroup of cloth materiaL
            p_flow (UILAyout): layout pattern ui is drawn in
        """
        row_h = p_flow.row(align= True)
        row_h.scale_y = 1.5*0.8 #quick fix because history
        row_h.prop(sett, 'patterns_sub', text = '')
        row_h.operator('hg3d.random',
                       text = 'Random',
                       icon = 'FILE_REFRESH'
                       ).random_type = 'patterns'
        
        p_flow.separator()

        for input_idx, node_input in enumerate(
                [control_node.inputs[i] for i in ('PC1', 'PC2', 'PC3')]
                ):
            p_flow.prop(node_input, 'default_value',
                        text = 'Color {}'.format(input_idx + 1)
                        )

        p_flow.prop(control_node.inputs['Pattern Opacity'], 'default_value',
                    text = 'Opacity',
                    slider = True
                    )

    def make_box_flow(self, layout, name, icon):
        """creates a box with title 

        Args:
            layout (UILayout): layout to draw box in
            name (str): name to show as title
            icon (str): code for icon to display next to title

        Returns:
            tuple(flow, box): 
                UILayout: flow below box
                UILayout: box itself
        """
        box = layout.box()
        
        row = box.row()
        row.alignment = 'CENTER'
        row.label(text= name, icon = icon)
        
        flow = get_flow(self.sett, box)
        flow.scale_y = 1.2
        
        return flow, box


    def _draw_batch_result_ui(self):
        self._draw_batch_info_box()
        
        return self._draw_batch_hair_box()

    def _draw_batch_hair_box(self):
        spoiler_open, box = draw_spoiler_box(self, 'hair')
        if not spoiler_open:
            return
        
        hair_systems = self._get_hair_systems(self.hg_rig.HG.body_obj, eyesystems = True)
        
        self._draw_hair_length_ui(hair_systems, box)
        self._draw_hair_material_ui(box)

    def _draw_batch_info_box(self):
        box = self.layout.box()
        row = box.row(align = True)
        row.alignment = 'CENTER'
        row.scale_y = 2
        row.label(text = 'This is a batch human', icon = 'INFO')
        row.operator('hg3d.showinfo',
                     text = '',
                     icon ='QUESTION',
                     emboss = False
                     ).info = 'batch_result'
          

#TODO incorrect naming per Blender scheme
class HG_PT_ROT_LOC_SCALE(bpy.types.Panel):
    '''
    Popover for the rot, loc and scale of the pattern
    '''

    bl_label = 'Pattern RotLocScale'
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'HEADER'

    def draw (self,context): 
        layout = self.layout  
            
        mat = context.object.active_material
        mapping_node = mat.node_tree.nodes['HG_Pattern_Mapping']

        col = layout.column()
        
        col.label(text = 'Location')
        col.prop(mapping_node.inputs['Location'], 'default_value', text = '')
        
        col.label(text = 'Rotation')
        col.prop(mapping_node.inputs['Rotation'], 'default_value', text = '')
        
        col.label(text = 'Scale')
        col.prop(mapping_node.inputs['Scale'], 'default_value', text = '')
