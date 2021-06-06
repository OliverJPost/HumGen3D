import bpy #type: ignore
from .. import bl_info
from sys import platform
from .. HG_PCOLL import preview_collections
from .. HG_COMMON_FUNC import find_human
from .. HG_COLORS import color_dict
from . HG_PANEL_FUNCTIONS import spoiler_box, next_phase, get_flow, searchbox, tab_switching_menu
from pathlib import Path
import addon_utils #type: ignore
import os


class HG_PT_PANEL(bpy.types.Panel):
    bl_idname = "HG_PT_Panel"
    bl_label = "HumGen"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"

    @classmethod
    def poll(cls, context):
        return context.scene.HG3D.active_ui_tab == 'CREATE'

    def draw_header(self, context):
        tab_switching_menu(self.layout, context.scene.HG3D)

    def draw(self,context):
        layout = self.layout
        self.sett = context.scene.HG3D
        self.pref = context.preferences.addons[os.path.splitext(__package__)[0]].preferences
        self.update = 'cpack_required' if self.pref.cpack_update_required else 'addon' if tuple(bl_info['version']) < tuple(self.pref.latest_version) else 'cpack_available' if self.pref.cpack_update_available else None 
        
        if not self.pref.filepath:
            layout.alert = True
            layout.label(text = 'No filepath selected')
            layout.label(text = 'Select one in the preferences')
            layout.operator('hg3d.openpref', text = 'Open preferences', icon ='PREFERENCES')
            return

        base_content = os.path.exists(self.pref.filepath + str(Path('content_packs/Base_Humans.json'))) 
        if not base_content:
            layout.alert = True
            layout.label(text = "Filepath selected, but couldn't")
            layout.label(text = 'find any humans.')
            layout.label(text = 'Check if filepath is correct and')
            layout.label(text = 'if the content packs are installed.')
            layout.operator('hg3d.openpref', text = 'Open preferences', icon ='PREFERENCES')
            return
        if not self.sett.subscribed:
            self.welcome_menu()
            return

        if self.update == 'cpack_required':
            layout.alert = True
            layout.label(text = 'One or more cpacks outdated!')
            layout.operator('hg3d.openpref', text = 'Open preferences', icon ='PREFERENCES')
            return

        self.hg_rig = find_human(context.active_object)
    
        if self.warning_header(context):
            return

        if self.update:
            label = 'Add-on update available!' if self.update == 'addon' else 'CPack updates available'
            layout.operator("hg3d.openpref", text = label, icon = 'PACKAGE', depress = True, emboss = True if self.update == 'addon' else False)#.url = 'https://humgen3d.com/support/update'

        self.top_widget()

        hg_rig = self.hg_rig
        if not hg_rig:
            self.create_human_ui()
        elif 'cloth' in context.object or 'shoe' in context.object:
            self.material_ui(context)
        elif hg_rig.HG.phase == 'creator':
            self.creator_ui()
            self.length_section()   
            self.clothing_section()
            self.footwear_section()
            self.layout.label(text = 'Remove stretch bones before posing')
            self.pose_section()
        elif hg_rig.HG.phase in ['body', 'face', 'skin', 'length']:
            self.creation_section()
            self.length_section() 
            self.face_section()
            self.skin_section()
            self.eyes_section()
            if self.pref.hair_section in ['both', 'creation']:
                self.hair_section(context)
            next_phase(self)    
        else:
            self.creation_backup()
            if self.pref.hair_section in ['both', 'finalize']:
                self.hair_section(context)
            self.clothing_section()
            self.footwear_section()
            self.pose_section()
            self.expression_section()
  

    def welcome_menu(self):
        col = self.layout.column()
        col.scale_y = 4
        col.operator('hg3d.showinfo', text = 'Welcome to Human Generator!', depress = True)

        col_h = col.column(align=True)
        col_h.scale_y = .5
        col_h.alert = True

        col_h.operator('hg3d.drawtutorial', text = 'Get Started!', depress = True, icon = 'FAKE_USER_ON').first_time = True

    def creator_ui(self):
        layout = self.layout
        box = layout.box()
        box.scale_y = 2
        box.operator('hg3d.showinfo', text = 'Creator Human', icon = 'INFO', depress = True)

    def warning_header(self, context):
        col = self.layout.column(align = True)
        col_h = col.column(align = True)
        col_h.scale_y = 1.5
        
        
        if not context.mode == 'OBJECT':
            col_h.alert = True
            col_h.label(text = 'HumGen only works in Object Mode')
            return True

        if self.hg_rig and 'no_body' in self.hg_rig:
            col_h.alert = True
            col_h.label(text = 'No body object found for this rig')
            return True
        
        return False

    def top_widget(self):
        hg_rig = self.hg_rig
        if not hg_rig:
            selection = 'No Human selected'  
            depress = False         
        else:
            name = hg_rig.name.replace('HG_', '').replace('_RIGIFY', '')     
            gender = hg_rig.HG.gender
            selection = 'This is {} [{}]'.format(name,gender.capitalize())
            depress = True

        col = self.layout.column(align = True)
        row_h = col.row(align = True)
        row_h.scale_y = 1.5
        row = row_h.row(align = True)
        if hg_rig and hg_rig.HG.experimental:        
            row.alert = True
        row.operator('view3d.view_selected', text = selection, depress = bool(hg_rig))
        if hg_rig and hg_rig.HG.phase in ['body', 'face', 'skin', 'length']:
            row = row_h.row(align = True)
            if not hg_rig.HG.experimental:
                row.alert = True
            row.operator('hg3d.experimental', text = '', icon = 'GHOST_{}'.format('DISABLED' if hg_rig.HG.experimental else 'ENABLED'), depress = True)


        if hg_rig and hg_rig.HG.phase == 'completed':
            row = col.row(align = True)
            row.alert = True
            row.operator('hg3d.showinfo', text='Completed Model', depress = True).info = 'completed'
            row.operator('hg3d.showinfo', icon = 'QUESTION', depress = True).info = 'completed'
        row = col.row(align=True)
        row.operator('hg3d.nextprev', text = 'Previous', icon = 'TRIA_LEFT').forward = False
        row.operator('hg3d.nextprev', text = 'Next', icon = 'TRIA_RIGHT').forward = True
        row = col.row(align=True)
        row.operator('hg3d.deselect', icon = 'RESTRICT_SELECT_ON')
        row.operator('hg3d.delete', text = 'Delete', icon = 'TRASH')

    #   ______ .______       _______     ___   .___________. _______ 
    #  /      ||   _  \     |   ____|   /   \  |           ||   ____|
    # |  ,----'|  |_)  |    |  |__     /  ^  \ `---|  |----`|  |__   
    # |  |     |      /     |   __|   /  /_\  \    |  |     |   __|  
    # |  `----.|  |\  \----.|  |____ /  _____  \   |  |     |  |____ 
    #  \______|| _| `._____||_______/__/     \__\  |__|     |_______|

    def create_human_ui(self):
        layout = self.layout
        sett = self.sett

        box = layout.box()
        col = box.column(align = True)
        col.label(text='Select a body type')
        col.template_icon_view(sett, "pcoll_humans", show_labels=True, scale=10, scale_popup=6)   
        
        row = col.row()
        row.scale_y = 2
        row.prop(sett, 'gender', expand = True)

        col = box.column()
        col.scale_y = 2
        col.alert = True
        col.operator('hg3d.startcreation', icon = 'COMMUNITY', depress = True)

    # .______     ______    _______  ____    ____ 
    # |   _  \   /  __  \  |       \ \   \  /   / 
    # |  |_)  | |  |  |  | |  .--.  | \   \/   /  
    # |   _  <  |  |  |  | |  |  |  |  \_    _/   
    # |  |_)  | |  `--'  | |  '--'  |    |  |     
    # |______/   \______/  |_______/     |__|

    def creation_section(self):
        sett = self.sett
        spoiler_open, box = spoiler_box(self, 'body')

        if not spoiler_open:   
            return

        
        col = box.column()
        col.scale_y = 1.25

        col_h = col.column()
        col_h.scale_y = 1.5
        col_h.operator('hg3d.random', text = 'Random', icon = 'FILE_REFRESH').type = 'body_type'

        col_h.separator()
        hg_body = self.hg_rig.HG.body_obj

            
        flow = get_flow(sett, col)
       
        sks = hg_body.data.shape_keys.key_blocks
        bp_sks = [sk for sk in sks if sk.name.startswith('bp_')]
        for sk in bp_sks:         
            flow.prop(sk, 'value', text = sk.name.replace('bp_', '').capitalize(), expand = True)

        #flow.operator('hg3d.random', text = 'Random', icon = 'FILE_REFRESH').type = 'body_type'
        col.separator()
        self.individual_scale_ui(col, sett)

    def individual_scale_ui(self, box, sett):
        boxbox = box.box()
        boxbox.prop(self.sett, 'indiv_scale_ui',
            icon="TRIA_DOWN" if sett.indiv_scale_ui else "TRIA_RIGHT",
            emboss=False,
            toggle=True)

        if self.sett.indiv_scale_ui:
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

    def length_section(self):
        spoiler_open, box = spoiler_box(self, 'length')

        if not spoiler_open:   
            return

        length = self.hg_rig.dimensions[2]
        col = box.column(align = True)

        row = col.box().row()
        row.scale_y = 2
        row.alignment = 'CENTER'
        length_feet = length / 0.3048
        length_inches = length_feet*12.0 - int(length_feet)*12.0
        length_label = '{} m   |   '.format(round(length, 2)) + "{}' ".format(int(length_feet)) + '{}"'.format(int(length_inches))
        row.label(text = length_label, icon = 'EMPTY_SINGLE_ARROW') #also in inches

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

    def face_section(self):
        sett = self.sett
        spoiler_open, box = spoiler_box(self, 'face')

        if not spoiler_open:   
            return

        if box.enabled:
            col = box.column()
            col.scale_y = 1.5
            row = col.row(align = True)
            row.operator('hg3d.random', text = 'Randomize all').type = 'face_all'
            row.operator('hg3d.resetface', text = '', icon = 'LOOP_BACK')

            hg_body = self.hg_rig.HG.body_obj
            face_sks = [sk for sk in hg_body.data.shape_keys.key_blocks if sk.name.startswith('ff')]
            col = box.column(align= True)
            
            col.label(text = 'Upper Face:')
            flow_u_skull = self.get_ff_flow(col, 'Upper Skull', 'u_skull')
            flow_eyes = self.get_ff_flow(col, 'Eyes', 'eyes')
            flow_ears = self.get_ff_flow(col, 'Ears', 'ears')
            flow_nose = self.get_ff_flow(col, 'Nose', 'nose')
            
            col.separator()
            col.label(text = 'Lower Face:')
            flow_l_skull = self.get_ff_flow(col, 'Lower Skull', 'l_skull')
            flow_mouth = self.get_ff_flow(col, 'Mouth', 'mouth')
            flow_cheeks = self.get_ff_flow(col, 'Cheeks', 'cheeks')  
            flow_jaw = self.get_ff_flow(col, 'Jaw', 'jaw')
            flow_chin = self.get_ff_flow(col, 'Chin', 'chin')       

            col.separator()
            col.label(text = 'Other:')            
            flow_custom = self.get_ff_flow(col, 'Custom', 'custom')   
            flow_presets = self.get_ff_flow(col, 'Presets', 'presets')       
            
            prefix_dict = {
                'ff_a': (flow_u_skull, sett.ui_u_skull),
                'ff_b': (flow_u_skull, sett.ui_u_skull),
                'ff_c_eye': (flow_eyes, sett.ui_eyes), 
                'ff_d': (flow_l_skull, sett.ui_l_skull),
                'ff_e_nose': (flow_nose, sett.ui_nose),
                'ff_f_lip': (flow_mouth, sett.ui_mouth),
                'ff_g_chin': (flow_chin, sett.ui_chin),
                'ff_h_cheek': (flow_cheeks, sett.ui_cheeks),
                'ff_i_jaw': (flow_jaw, sett.ui_jaw),
                'ff_j_ear': (flow_ears, sett.ui_ears),
                'ff_x': (flow_custom, sett.ui_custom),
                }
            
            for prefix in prefix_dict:
                if not prefix_dict[prefix][1]:
                    continue
                for sk in [sk for sk in face_sks if sk.name.startswith(prefix)]:
                    prefix_dict[prefix][0].prop(sk, 'value', text = self.build_sk_name(sk.name, prefix))

            if sett.ui_presets:
                sks = hg_body.data.shape_keys.key_blocks
                for sk in [sk for sk in sks if sk.name.startswith('pr_')]:
                    flow_presets.prop(sk, 'value', text = sk.name.replace('pr_', '').replace('_', ' ').capitalize())


    def build_sk_name(self, sk_name, prefix):
        
        sk_name = sk_name.replace(prefix, '')
        
        sk_name = sk_name.replace('_', ' ')
        sk_name = sk_name.replace('.Transferred', '')
        sk_name = sk_name.title()
        return sk_name

    def get_ff_flow(self, layout, name, ui_name):
        sett = self.sett
        boxbox = layout.box()
        boxbox.scale_y = 1 if self.pref.compact_ff_ui else 1.5 
       
        ui_bools = {
            'nose': sett.ui_nose,
            'u_skull': sett.ui_u_skull,
            'chin': sett.ui_chin,
            'mouth': sett.ui_mouth,
            'eyes': sett.ui_eyes,
            'cheeks': sett.ui_cheeks,
            'l_skull': sett.ui_l_skull,
            'jaw': sett.ui_jaw,
            'ears': sett.ui_ears,
            'other': sett.ui_other,
            'custom': sett.ui_custom,
            'presets': sett.ui_presets
            }

        row = boxbox.row()
        row.prop(sett, 'ui_{}'.format(ui_name), text = name,  icon="TRIA_DOWN" if ui_bools[ui_name] else "TRIA_RIGHT", toggle=True, emboss = False)
        if ui_name != 'presets':
            row.operator('hg3d.random', text = '', icon = 'FILE_REFRESH', emboss = False).type = 'face_{}'.format(ui_name)
        else:
            row.operator('hg3d.showinfo', text = '', icon = 'BLANK1', emboss = False)
        col = layout.column(align = True)
        col.scale_y = 1 if self.pref.compact_ff_ui else 1.5 
        return col

    #      _______. __  ___  __  .__   __. 
    #     /       ||  |/  / |  | |  \ |  | 
    #    |   (----`|  '  /  |  | |   \|  | 
    #     \   \    |    <   |  | |  . `  | 
    # .----)   |   |  .  \  |  | |  |\   | 
    # |_______/    |__|\__\ |__| |__| \__|

    def skin_section(self):
        spoiler_open, box = spoiler_box(self, 'skin')
        sett = self.sett 
        hg_body = self.hg_rig.HG.body_obj
        mat = hg_body.data.materials[0]
        nodes = mat.node_tree.nodes

        if not spoiler_open:   
            return

        if 'hg_baked' in self.hg_rig:
            box.label(text = 'Textures are baked', icon = 'INFO')
            return

        self.texture_section(sett, box)
        self.main_skin_section(sett, box, nodes)
        self.light_dark_areas(sett, box, nodes)
        self.freckles_section(sett, box, nodes)
        self.beautyspots_section(sett, box, nodes)
        self.age_section(sett, box, nodes)

        gender = self.hg_rig.HG.gender
        
        if gender == 'female':
            self.makeup_section(sett, box, nodes)
        else:
            self.beard_shadow_section(sett, box, nodes)

    def texture_section(self, sett, box):
        boxbox = box.box()
        row = boxbox.row()
        row.prop(sett, 'texture_ui', text = 'Base texture', icon = 'TRIA_RIGHT' if not sett.texture_ui else 'TRIA_DOWN' , emboss= False)

        if not sett.texture_ui:
            return        

        col = boxbox.column()
        col.template_icon_view(sett, "pcoll_textures", show_labels=True, scale=10, scale_popup=6)  
        
        col.prop(sett, 'texture_library', text = 'Library')

    def light_dark_areas(self, sett, box, nodes):
        boxbox = box.box()
        row = boxbox.row()
        row.prop(sett, 'light_dark_ui', text = 'Dark/Light areas', icon = 'TRIA_RIGHT' if not sett.light_dark_ui else 'TRIA_DOWN' , emboss= False)

        if not sett.light_dark_ui:
            return

        light_hsv = nodes['Lighten_hsv']
        dark_hsv = nodes['Darken_hsv']

        col = boxbox.column(align = False)
        col.scale_y = 1.2

        col.prop(dark_hsv.inputs['Value'], 'default_value', text = 'Dark areas', slider = True)
        col.prop(light_hsv.inputs['Value'], 'default_value', text = 'Light areas', slider = True)

    def age_section(self, sett, box, nodes):
        boxbox = box.box()
        row = boxbox.row()
        row.prop(sett, 'age_ui', text = 'Age', icon = 'TRIA_RIGHT' if not sett.age_ui else 'TRIA_DOWN' , emboss= False)

        if not sett.age_ui:
            return

        hg_body = self.hg_rig.HG.body_obj
        sk = hg_body.data.shape_keys.key_blocks
        age_sk = sk['age_old.Transferred']
        age_node = nodes['HG_Age']

        col = boxbox.column(align = True)
        col.scale_y = 1.2
        col.prop(age_sk, 'value', text = 'Skin sagging [Mesh]', slider = True)
        col.prop(age_node.inputs[1], 'default_value', text = 'Wrinkles', slider = True)

    def freckles_section(self, sett, box, nodes):
        boxbox = box.box()
        row = boxbox.row()
        row.prop(sett, 'freckles_ui', text = 'Freckles', icon = 'TRIA_RIGHT' if not sett.freckles_ui else 'TRIA_DOWN' , emboss= False)

        if not sett.freckles_ui:
            return

        freckles_node = nodes['Freckles_control']
        splotches_node = nodes['Splotches_control']

        col = boxbox.column(align = True)
        col.scale_y = 1.2
        col.prop(freckles_node.inputs['Pos2'], 'default_value', text = 'Freckles', slider = True)
        col.prop(splotches_node.inputs['Pos2'], 'default_value', text = 'Splotches', slider = True)


    def main_skin_section(self, sett, box, nodes):
        boxbox = box.box()
        row = boxbox.row()
        row.prop(sett, 'main_skin_ui', text = 'Main settings', icon = 'TRIA_RIGHT' if not sett.main_skin_ui else 'TRIA_DOWN' , emboss= False)

        if not sett.main_skin_ui:
            return

        col = boxbox.column(align = True)
        col.scale_y = 1.2
        
        tone_node = nodes['Skin_tone']
        col.prop(tone_node.inputs[1], 'default_value', text = 'Tone', slider = True)
        col.prop(tone_node.inputs[2], 'default_value', text = 'Redness', slider = True)
        col.separator()
        normal_node = nodes['Normal Map']
        col.prop(normal_node.inputs[0], 'default_value', text = 'Normal Strength')
        r_node =  nodes['R_Multiply']
        col.prop(r_node.inputs[1], 'default_value', text = 'Roughness mult.')
        col.separator()
        row = col.row()
        row.label(text = 'Subsurface scattering')
        row.operator('hg3d.showinfo', text = '', icon ='QUESTION', emboss = False).info = 'subsurface'
        row = col.row(align = True)
        row.prop(sett, 'skin_sss', expand = True)

    def makeup_section(self, sett, box, nodes):
        makeup_node = nodes['Gender_Group']
        
        boxbox = box.box()
        row = boxbox.row()
        row.prop(sett, 'makeup_ui', text = 'Makeup', icon = 'TRIA_RIGHT' if not sett.makeup_ui else 'TRIA_DOWN' , emboss= False)

        if not sett.makeup_ui:
            return

        #TODO make loop. First try failed, don't remember why
        flow = self.skin_section_flow(boxbox, 'Foundation:')
        flow.prop(makeup_node.inputs['Foundation Amount'], 'default_value', text = 'Amount', slider = True)
        flow.prop(makeup_node.inputs['Foundation Color'], 'default_value', text = 'Color')

        flow = self.skin_section_flow(boxbox, 'Blush:')
        flow.prop(makeup_node.inputs['Blush Opacity'], 'default_value', text = 'Opacity', slider = True)
        flow.prop(makeup_node.inputs['Blush Color'], 'default_value', text = 'Color')

        flow = self.skin_section_flow(boxbox, 'Eyeshadow:')
        flow.prop(makeup_node.inputs['Eyeshadow Opacity'], 'default_value', text = 'Opacity', slider = True)
        flow.prop(makeup_node.inputs['Eyeshadow Color'], 'default_value', text = 'Color')
        
        flow = self.skin_section_flow(boxbox, 'Lipstick:')
        flow.prop(makeup_node.inputs['Lipstick Opacity'], 'default_value', text = 'Opacity', slider = True)
        flow.prop(makeup_node.inputs['Lipstick Color'], 'default_value', text = 'Color')

        flow = self.skin_section_flow(boxbox, 'Eyeliner:')

        flow.prop(makeup_node.inputs['Eyeliner Opacity'], 'default_value', text = 'Opacity', slider = True)
        flow.prop(makeup_node.inputs['Eyeliner Color'], 'default_value', text = 'Color')

        flow = self.skin_section_flow(boxbox, 'Eyebrows:')

        flow.prop(makeup_node.inputs['Eyebrows Opacity'], 'default_value', text = 'Opacity', slider = True)
        flow.prop(makeup_node.inputs['Eyebrows Color'], 'default_value', text = 'Color')

    def beautyspots_section(self, sett, box, nodes):
        if platform == 'darwin':
            return

        boxbox = box.box()
        row = boxbox.row()
        row.prop(sett, 'beautyspots_ui', text = 'Beauty spots', icon = 'TRIA_RIGHT' if not sett.beautyspots_ui else 'TRIA_DOWN' , emboss= False)

        if not sett.beautyspots_ui:
            return        

        bs_node = nodes['BS_Control']
        opacity_node = nodes['BS_Opacity']
        col = boxbox.column(align = True)
        col.scale_y = 1.2

        col.prop(bs_node.inputs[2], 'default_value', text = 'Amount', slider = True)
        col.prop(opacity_node.inputs[1], 'default_value', text = 'Opacity', slider = True)
        col.prop(bs_node.inputs[1], 'default_value', text = 'Seed [Randomize]')

    def skin_section_flow(self, layout, label):
        row = layout.row()
        row.alignment = 'CENTER'
        row.label(text = label, icon = 'HANDLETYPE_AUTO_CLAMP_VEC')
        flow = get_flow(self.sett, layout)
        flow.scale_y = 1.2   

        return flow     

    def beard_shadow_section(self, sett, box, nodes):
        boxbox = box.box()
        row = boxbox.row()
        row.prop(sett, 'beard_shadow_ui', text = 'Beard shadow', icon = 'TRIA_RIGHT' if not sett.beard_shadow_ui else 'TRIA_DOWN' , emboss= False)

        if not sett.beard_shadow_ui:
            return

        beard_node = nodes['Gender_Group']

        flow = get_flow(sett, boxbox)
        flow.scale_y = 1.2
        flow.prop(beard_node.inputs[2], 'default_value', text = 'Mustache', slider = True)   
        flow.prop(beard_node.inputs[3], 'default_value', text = 'Beard', slider = True)   


#  ___________    ____  _______     _______.
# |   ____\   \  /   / |   ____|   /       |
# |  |__   \   \/   /  |  |__     |   (----`
# |   __|   \_    _/   |   __|     \   \    
# |  |____    |  |     |  |____.----)   |   
# |_______|   |__|     |_______|_______/

    def eyes_section(self):
        sett = self.sett
        spoiler_open, box = spoiler_box(self, 'eyes')    

        if not spoiler_open:   
            return

        if 'hg_baked' in self.hg_rig:
            box.label(text = 'Textures are baked', icon = 'INFO')
            
            boxbox = box.box()
            row = boxbox.row()
            row.alignment = 'CENTER'
            row.label(text = 'Eyebrows:', icon = 'OUTLINER_OB_HAIR')
            row = boxbox.row(align = True)
            row.operator('hg3d.eyebrowswitch', text = 'Previous', icon = 'TRIA_LEFT').forward = False
            row.operator('hg3d.eyebrowswitch', text = 'Next', icon = 'TRIA_RIGHT').forward = True
            return

        hg_eyes = [child for child in self.hg_rig.children if 'hg_eyes' in child][0]
        mat = hg_eyes.data.materials[1]
        nodes = mat.node_tree.nodes

        boxbox = box.box()
        row = boxbox.row()
        row.alignment = 'CENTER'
        row.label(text = 'Color:', icon = 'RESTRICT_COLOR_OFF')
        col = boxbox.column(align = True)
        row = col.row()
        row.prop(nodes['HG_Eye_Color'].inputs[2], 'default_value', text = 'Iris Color')
        row = col.row()
        row.prop(nodes['HG_Scelera_Color'].inputs[2], 'default_value', text = 'Sclera Color')

        boxbox = box.box()
        row = boxbox.row()
        row.alignment = 'CENTER'
        row.label(text = 'Eyebrows:', icon = 'OUTLINER_OB_HAIR')
        row = boxbox.row(align = True)
        row.operator('hg3d.eyebrowswitch', text = 'Previous', icon = 'TRIA_LEFT').forward = False
        row.operator('hg3d.eyebrowswitch', text = 'Next', icon = 'TRIA_RIGHT').forward = True

        eye_systems = self.get_eye_systems(self.hg_rig.HG.body_obj)
        self.secondary_hair_ui(eye_systems, boxbox)
        self.tertiary_hair_ui(eye_systems, box)

    def get_eye_systems(self, body_obj):
        eye_systems = []
        for mod in body_obj.modifiers:
            if mod.type == 'PARTICLE_SYSTEM' and mod.particle_system.name.startswith(('Eyebrows', 'Eyelashes')) and (mod.show_viewport or mod.show_render):
                eye_systems.append(mod.particle_system)
        return eye_systems


#   ______ .______       _______     ___   .___________. __    ______   .__   __.    .______        ___       ______  __  ___  __    __  .______   
#  /      ||   _  \     |   ____|   /   \  |           ||  |  /  __  \  |  \ |  |    |   _  \      /   \     /      ||  |/  / |  |  |  | |   _  \  
# |  ,----'|  |_)  |    |  |__     /  ^  \ `---|  |----`|  | |  |  |  | |   \|  |    |  |_)  |    /  ^  \   |  ,----'|  '  /  |  |  |  | |  |_)  | 
# |  |     |      /     |   __|   /  /_\  \    |  |     |  | |  |  |  | |  . `  |    |   _  <    /  /_\  \  |  |     |    <   |  |  |  | |   ___/  
# |  `----.|  |\  \----.|  |____ /  _____  \   |  |     |  | |  `--'  | |  |\   |    |  |_)  |  /  _____  \ |  `----.|  .  \  |  `--'  | |  |      
#  \______|| _| `._____||_______/__/     \__\  |__|     |__|  \______/  |__| \__|    |______/  /__/     \__\ \______||__|\__\  \______/  | _|


    def creation_backup(self):
        sett = self.sett
        spoiler_open, box = spoiler_box(self, 'creation_phase')
        hg_icons = preview_collections["hg_icons"]

        if not spoiler_open:
            return

        col_h = box.column()
        col_h.scale_y = 1.5
        col_h.alert= True
        col_h.operator('hg3d.revert', text = 'Revert to Creation Phase', icon = 'ERROR', depress = True)


        boxbox = box.box()
        row = boxbox.row()
        row.alignment = 'CENTER'
        row.label(text = 'Skin Settings', icon_value = hg_icons['skin'].icon_id)
        nodes = self.hg_rig.HG.body_obj.data.materials[0].node_tree.nodes
        self.main_skin_section(sett, boxbox, nodes)
        if self.hg_rig.HG.gender == 'female':
            self.makeup_section(sett, boxbox, nodes)

        if self.pref.hair_section == 'creation':
            boxbox = box.box()
            hair_systems = self.get_hair_systems(self.hg_rig.HG.body_obj)
            row = boxbox.row()
            row.alignment = 'CENTER'
            row.label(text = 'Hair Settings', icon_value = hg_icons['hair'].icon_id)
            self.secondary_hair_ui(hair_systems, boxbox)
            self.tertiary_hair_ui(hair_systems, boxbox)
            self.hair_material_ui(hair_systems, boxbox)
        
        
    #  __    __       ___       __  .______      
    # |  |  |  |     /   \     |  | |   _  \     
    # |  |__|  |    /  ^  \    |  | |  |_)  |    
    # |   __   |   /  /_\  \   |  | |      /     
    # |  |  |  |  /  _____  \  |  | |  |\  \----.
    # |__|  |__| /__/     \__\ |__| | _| `._____|

    def hair_section(self, context):
        sett = self.sett
        spoiler_open, box = spoiler_box(self, 'hair')
        
        if not spoiler_open:
            return
        
        hg_rig = find_human(context.active_object)
        body_obj = hg_rig.HG.body_obj

        hair_systems = self.get_hair_systems(body_obj)
        self.secondary_hair_ui(hair_systems, box)

        box.template_icon_view(sett, "pcoll_hair", show_labels=True, scale=10, scale_popup=6)   
        col_h = box.column()
        col_h.scale_y =1.5
        col_h.prop(sett, 'hair_sub', text = '')
        if hg_rig.HG.gender == 'male':
            col=box.column(align=True)
            boxbox = col.box()
            boxbox.prop(sett, 'face_hair_ui',
            icon="TRIA_DOWN" if sett.face_hair_ui else "TRIA_RIGHT",
            emboss=False,
            toggle=True)
            if sett.face_hair_ui:
                col.template_icon_view(sett, "pcoll_face_hair", show_labels=True, scale=10, scale_popup=6)  
                col_h = col.column()
                col_h.scale_y =1.5
                col_h.prop(sett, 'face_hair_sub', text = '')
        
        self.tertiary_hair_ui(hair_systems, box)
        self.hair_material_ui(hair_systems, box)
        self.hair_cards_ui(hair_systems, box)


    def secondary_hair_ui(self, hair_systems, box):
        if hair_systems:        
            row = box.row()
            row.label(text = 'Children are hidden' if hair_systems[0].settings.child_nbr <= 1 else 'Children are visible')
            row.operator('hg3d.togglechildren', text = '', icon='HIDE_ON' if hair_systems[0].settings.child_nbr <= 1 else 'HIDE_OFF')
            row.operator('hg3d.showinfo', icon = 'QUESTION', emboss = False).info = 'hair_children'

    def tertiary_hair_ui(self, hair_systems, box):
           
        boxbox = box.box()
        boxbox.prop(self.sett, 'hair_length_ui',
            icon="TRIA_DOWN" if self.sett.hair_length_ui else "TRIA_RIGHT",
            emboss=False,
            toggle=True)


        if self.sett.hair_length_ui:
            if not hair_systems:
                box.label(text = 'No hairstyles loaded')

            flow = get_flow(self.sett, box)
            for ps in hair_systems:
                row = flow.row()
                ps_name = ps.name.replace('fh_', '').replace('_', ' ').title()
                
                row.prop(ps.settings, 'child_length', text = ps_name)
                row.operator('hg3d.removehair', text = '', icon = 'TRASH').hair_system = ps.name

    def hair_material_ui(self, hair_systems, box):
        boxbox = box.box()
        boxbox.prop(self.sett, 'hair_mat_ui',
            icon="TRIA_DOWN" if self.sett.hair_mat_ui else "TRIA_RIGHT",
            emboss=False,
            toggle=True)        

        if self.sett.hair_mat_ui:
            row = boxbox.row(align = True)
            row.scale_y = 1.5
            gender = self.hg_rig.HG.gender
            row.prop(self.sett, 'hair_mat_{}'.format(gender), expand = True)

            categ = self.sett.hair_mat_male if gender == 'male' else self.sett.hair_mat_female

            mat_names = {'eye': '.HG_Hair_Eye', 'face': '.HG_Hair_Face', 'head': '.HG_Hair_Head'}
            hair_mat = [mat for mat in self.hg_rig.HG.body_obj.data.materials if mat.name.startswith(mat_names[categ])][0]
            hair_node = hair_mat.node_tree.nodes['HG_Hair']

            col = boxbox.column()
            col.prop(hair_node.inputs['Hair Lightness'], 'default_value', text = 'Lightness', slider = True)
            col.prop(hair_node.inputs['Hair Redness'], 'default_value', text = 'Redness', slider = True)
            col.prop(hair_node.inputs['Roughness'], 'default_value', text = 'Roughness')
            
            if categ != 'eye':
                col.label(text = 'Effects:')
                col.prop(hair_node.inputs['Pepper & Salt'], 'default_value', text = 'Pepper & Salt', slider = True)
                col.prop(hair_node.inputs['Roots'], 'default_value', text = 'Roots', slider = True)
                if hair_node.inputs['Roots'].default_value > 0:
                    col.prop(hair_node.inputs['Root Lightness'], 'default_value', text = 'Root Lightness')
                    col.prop(hair_node.inputs['Root Redness'], 'default_value', text = 'Root Redness')

    def hair_cards_ui(self, hair_systems, box):
        if hair_systems:    
            boxbox = box.box()
            boxbox.prop(self.sett, 'hair_cards_ui',
                icon="TRIA_DOWN" if self.sett.hair_cards_ui else "TRIA_RIGHT",
                emboss=False,
                toggle=True)

        if self.sett.hair_cards_ui:
            box.operator('hg3d.haircards')

    def get_hair_systems(self, body_obj):
        hair_systems = []
        for mod in body_obj.modifiers:
            if mod.type == 'PARTICLE_SYSTEM' and not mod.particle_system.name.startswith(('Eyebrows', 'Eyelashes')):
                hair_systems.append(mod.particle_system)
        return hair_systems


    #   ______  __        ______   .___________. __    __   __  .__   __.   _______ 
    #  /      ||  |      /  __  \  |           ||  |  |  | |  | |  \ |  |  /  _____|
    # |  ,----'|  |     |  |  |  | `---|  |----`|  |__|  | |  | |   \|  | |  |  __  
    # |  |     |  |     |  |  |  |     |  |     |   __   | |  | |  . `  | |  | |_ | 
    # |  `----.|  `----.|  `--'  |     |  |     |  |  |  | |  | |  |\   | |  |__| | 
    #  \______||_______| \______/      |__|     |__|  |__| |__| |__| \__|  \______|

    def clothing_section(self):
        sett = self.sett
        spoiler_open, box = spoiler_box(self, 'clothing')

        if not spoiler_open:
            return

        hg_icons =  preview_collections["hg_icons"]
        col_h = box.column()
        col_h.scale_y = 1.5
        

        searchbox(self, 'outfit', box)

        row = box.row(align = True)
        row.template_icon_view(sett, "pcoll_outfit", show_labels=True, scale=10, scale_popup=6)
        # sidebar = row.column(align = True)
        # sidebar.scale_y = 1.25
        # open = sett.clothing_sidebar_toggle
        # sidebar.scale_x = 1 if open else .35 
        # sidebar.prop(sett, 'clothing_sidebar_toggle', icon = 'TRIA_RIGHT' if open else 'TRIA_LEFT', text = 'Close sidebar' if open else '', emboss = True if open else False, invert_checkbox = True)
        # sidebar.prop(sett, 'clothing_sidebar_toggle', text = 'Season', emboss = False)
        # sidebar.prop(sett, 'summer_toggle', icon_value = hg_icons['warm'].icon_id, text = 'Hot' if open else '')
        # sidebar.prop(sett, 'normal_toggle', icon_value = hg_icons['normal'].icon_id, text = 'Normal' if open else '')
        # sidebar.prop(sett, 'winter_toggle', icon_value = hg_icons['cold'].icon_id, text = 'Cold' if open else '')
        # sidebar.prop(sett, 'clothing_sidebar_toggle', text = 'Environment', emboss = False)
        # sidebar.prop(sett, 'inside_toggle', icon_value = hg_icons['inside'].icon_id, text = 'Inside' if open else '')
        # sidebar.prop(sett, 'outside_toggle', icon_value = hg_icons['outside'].icon_id, text = 'Outisde' if open else '')

        row_h = box.row(align = True)
        row_h.scale_y = 1.5
        row_h.prop(sett, 'outfit_sub', text = '')
        row_h.operator('hg3d.random', text = 'Random', icon = 'FILE_REFRESH').type = 'outfit'

#      _______. __    __    ______    _______ 
#     /       ||  |  |  |  /  __  \  |   ____|
#    |   (----`|  |__|  | |  |  |  | |  |__   
#     \   \    |   __   | |  |  |  | |   __|  
# .----)   |   |  |  |  | |  `--'  | |  |____ 
# |_______/    |__|  |__|  \______/  |_______|

    def footwear_section(self):
        sett = self.sett
        spoiler_open, box = spoiler_box(self, 'footwear')

        if not spoiler_open:
            return

        col_h = box.column()
        col_h.scale_y = 1.5
        
        searchbox(self, 'footwear', box)

        row = box.row(align = True)
        row.template_icon_view(sett, "pcoll_footwear", show_labels=True, scale=10, scale_popup=6)

        row_h = box.row(align = True)
        row_h.scale_y = 1.5
        row_h.prop(sett, 'footwear_sub', text = '')
        row_h.operator('hg3d.random', text = 'Random', icon = 'FILE_REFRESH').type = 'footwear'


    
 
    # .______     ______        _______. _______ 
    # |   _  \   /  __  \      /       ||   ____|
    # |  |_)  | |  |  |  |    |   (----`|  |__   
    # |   ___/  |  |  |  |     \   \    |   __|  
    # |  |      |  `--'  | .----)   |   |  |____ 
    # | _|       \______/  |_______/    |_______|

    #pose
    def pose_section(self):
        sett = self.sett
        spoiler_open, box = spoiler_box(self, 'pose')

        if not spoiler_open:
            return
       
        row_h = box.row(align= True)
        row_h.scale_y = 1.5
        row_h.prop(sett, 'pose_choice', expand = True)

        if sett.pose_choice == 'library':
            if 'hg_rigify' in self.hg_rig.data:
                row = box.row(align = True)
                row.label(text = 'Rigify not supported', icon ='ERROR')
                row.operator('hg3d.showinfo', text = '', icon = 'QUESTION').info = 'rigify_library'
            else:
                searchbox(self, 'poses', box)
                box.template_icon_view(sett, "pcoll_poses", show_labels=True, scale=10, scale_popup=6) 
                row_h = box.row(align = True)
                row_h.scale_y = 1.5
                row_h.prop(sett, 'pose_sub', text = '')
                row_h.operator('hg3d.random', text = 'Random', icon = 'FILE_REFRESH').type = 'poses'
        elif sett.pose_choice == 'rigify':
            if 'hg_rigify' in self.hg_rig.data:
                box.label(text = 'Rigify rig active')
                box.label(text = 'Use Rigify add-on to adjust', icon = 'INFO')
            elif addon_utils.check("rigify"):
                col = box.column()
                col.scale_y = 1.5
                col.alert = True
                col.operator('hg3d.rigify', depress = True)
            else:
                box.label(text = 'Rigify is not enabled')

        elif sett.pose_choice == 'retarget': 
            box.label(text='retarget')




    #  __________   ___ .______   .______       _______     _______.     _______. __    ______   .__   __. 
    # |   ____\  \ /  / |   _  \  |   _  \     |   ____|   /       |    /       ||  |  /  __  \  |  \ |  | 
    # |  |__   \  V  /  |  |_)  | |  |_)  |    |  |__     |   (----`   |   (----`|  | |  |  |  | |   \|  | 
    # |   __|   >   <   |   ___/  |      /     |   __|     \   \        \   \    |  | |  |  |  | |  . `  | 
    # |  |____ /  .  \  |  |      |  |\  \----.|  |____.----)   |   .----)   |   |  | |  `--'  | |  |\   | 
    # |_______/__/ \__\ | _|      | _| `._____||_______|_______/    |_______/    |__|  \______/  |__| \__|
    
    def expression_section(self):
        sett = self.sett
        spoiler_open, box = spoiler_box(self, 'expression')
        
        if not spoiler_open:
            return

        row = box.row(align = True)
        row.scale_y = 1.5
        row.prop(sett, 'expression_type', expand = True)

        if sett.expression_type == '1click':
            self.oneclick_section(box, sett)
        else:
            self.frig_section(box)

    def oneclick_section(self, box, sett):
        if 'facial_rig' in self.hg_rig.HG.body_obj:
            box.label(text = 'Library not compatible with face rig')
            col = box.column()
            col.alert = True    
            col.scale_y = 1.5   
            col.operator('hg3d.removefrig', text = 'Remove facial rig', icon = 'TRASH', depress = True)
            return

        searchbox(self, 'expressions', box)
        box.template_icon_view(sett, "pcoll_expressions", show_labels=True, scale=10, scale_popup=6)  
        
        row_h = box.row(align= True)
        row_h.scale_y = 1.5
        row_h.prop(sett, 'expressions_sub', text = '')
        row_h.operator('hg3d.random', text = 'Random', icon = 'FILE_REFRESH').type = 'expressions'
        
        obj_sks = self.hg_rig.HG.body_obj.data.shape_keys
        if obj_sks:
            sks = obj_sks.key_blocks
            if [sk for sk in sks if sk.name != 'Basis' and not sk.name.startswith('cor')]:
                boxbox = box.box()
                boxbox.prop(sett, 'expression_slider_ui',
                    icon="TRIA_DOWN" if sett.expression_slider_ui else "TRIA_RIGHT",
                    emboss=False,
                    toggle=True)

            if sett.expression_slider_ui:
                flow = get_flow(sett, box, animation = True)
                for sk in sks:
                    if sk.name != 'Basis' and sk.mute == False and not sk.name.startswith('cor'):
                        display_name = sk.name.replace('expr_', '').replace('_', ' ')+':'
                        row = flow.row(align = True)
                        row.prop(sk, 'value', text = display_name.capitalize())
                        row.operator('hg3d.removesk', text = '', icon = 'TRASH').shapekey = sk.name

    def frig_section(self, box):
        col = box.column()
        if 'facial_rig' in self.hg_rig.HG.body_obj:
            col.label(text = 'Facial rig added')
            col.label(text = 'Use pose mode to adjust', icon = 'INFO')
        else:
            col.scale_y = 2
            col.alert = True
            col.operator('hg3d.addfrig', text = 'Add facial rig', depress = True)



    # .___  ___.      ___   .___________. _______ .______       __       ___       __      
    # |   \/   |     /   \  |           ||   ____||   _  \     |  |     /   \     |  |     
    # |  \  /  |    /  ^  \ `---|  |----`|  |__   |  |_)  |    |  |    /  ^  \    |  |     
    # |  |\/|  |   /  /_\  \    |  |     |   __|  |      /     |  |   /  /_\  \   |  |     
    # |  |  |  |  /  _____  \   |  |     |  |____ |  |\  \----.|  |  /  _____  \  |  `----.
    # |__|  |__| /__/     \__\  |__|     |_______|| _| `._____||__| /__/     \__\ |_______|

    #TODO add compatibility with any material, not just standard material
    def material_ui(self, context):
        sett = self.sett
        layout = self.layout
        hg_icons = preview_collections['hg_icons']

        if 'hg_baked' in self.hg_rig:
            layout.label(text = 'Textures are baked', icon = 'INFO')
            return

        col = layout.column(align = True)
        box = col.box().row()
        box.scale_y =1.5 
        box.alignment = 'CENTER'
        box.label(text = context.object.name.replace('_', ' ').replace('HG', ''), icon_value = hg_icons['clothing'].icon_id if 'cloth' in context.object else hg_icons['footwear'].icon_id)

        col.operator('hg3d.backhuman', text= 'Go back to human', icon = 'RESTRICT_SELECT_OFF', depress = True)

        alert_col = col.column(align = True)
        alert_col.alert = True
        alert_col.operator('hg3d.deletecloth', text = 'Delete clothing item', icon = 'TRASH', depress = True)

        control_node = context.active_object.data.materials[0].node_tree.nodes['HG_Control']

        c_flow, _ = self.make_box_flow(layout, 'Colors', 'COLOR')
        s_flow, _ = self.make_box_flow(layout, 'Options', 'OPTIONS')
        for inp in [control_node.inputs[i] for i in (4,5,6)]: 
            if inp.name == 'None':
                continue
            color_groups = tuple(['_{}'.format(name) for name in color_dict])     
            color_group = inp.name[-2:] if inp.name.endswith(color_groups) else None
            row = c_flow.row(align=False)
            row.prop(inp, 'default_value', text = inp.name[:-3] if color_group else inp.name)
            if color_group:
                c_random = row.operator('hg3d.colorrandom', text = '', icon = 'FILE_REFRESH')
                c_random.input_name = inp.name
                c_random.color_group = color_group
        for i, inp in enumerate(control_node.inputs):
            if i  > 13 and not inp.is_linked:
                s_flow.prop(inp, 'default_value', text = inp.name)
        for i, inp in enumerate(control_node.inputs):
            if inp.name in ['Roughness Multiplier', 'Normal Strength']:
                s_flow.prop(inp, 'default_value', text = inp.name)
    
        if 'Pattern' not in control_node.inputs:
            return

        #pattern section
        p_flow, p_box = self.make_box_flow(layout, 'Pattern', 'NODE_TEXTURE')
        pattern = True if control_node.inputs[9].is_linked else False
        if pattern:
            searchbox(self, 'patterns', p_flow)

            col = p_flow.column(align = False)
            col.scale_y = .8
            col.template_icon_view(sett, "pcoll_patterns", show_labels=True, scale=5, scale_popup=6)
            
            row_h = col.row(align= True)
            row_h.scale_y = 1.5
            row_h.prop(sett, 'patterns_sub', text = '')
            row_h.operator('hg3d.random', text = 'Random', icon = 'FILE_REFRESH').type = 'patterns'
            col.separator()

            for i, inp in enumerate([control_node.inputs[i] for i in ('PC1', 'PC2', 'PC3')]):
                p_flow.prop(inp, 'default_value', text = 'Color {}'.format(i + 1))

            p_flow.prop(control_node.inputs['Pattern Opacity'], 'default_value', text = 'Opacity', slider = True)

        row = p_box.row(align = True)
        row.scale_y = 1.3
        row.operator('hg3d.pattern', text = 'Remove' if pattern else 'Add Pattern', icon = 'TRASH' if pattern else 'TEXTURE').add = False if pattern else True
        if pattern:
            row.popover(panel='HG_ROT_LOC_SCALE', text='Transform', icon='ORIENTATION_GLOBAL')
    
    def make_box_flow(self, layout, name, icon):
        box = layout.box()
        row = box.row()
        row.alignment = 'CENTER'
        row.label(text= name, icon = icon)
        flow = get_flow(self.sett, box)
        flow.scale_y = 1.2
        return flow, box

class HG_ROT_LOC_SCALE(bpy.types.Panel):
    '''
    Popover for the rot, loc and scale of the pattern
    '''

    bl_label = 'Pattern RotLocScale'
    bl_space_type = 'VIEW_3D'
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