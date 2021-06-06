from . HG_COMMON_FUNC import make_path_absolute
from . HG_UTILITY_FUNC import refresh_hair_ul, refresh_modapply
import bpy #type: ignore
from . HG_PROP_FUNCTIONS import find_folders, get_resolutions
from . HG_PCOLL import refresh_pcoll, get_pcoll_items
from . HG_POSE import apply_pose
from . HG_CLOTHING import load_pattern #,load_outfit
from . HG_CLOTHING_LOAD import load_outfit
from . HG_EXPRESSION import load_expression
from . HG_HAIR import load_hair
from . HG_CREATION import scale_bones, load_textures
from . user_interface import HG_BATCH_UILIST
from . HG_SKIN import toggle_sss
from . HG_CALLBACK import tab_change_update
from . HG_LENGTH import update_length_v2
from . HG_UTILITY_FUNC import get_preset_thumbnail, refresh_shapekeys_ul

def poll_mtc_armature(self, object):
    return object.type == 'ARMATURE'

class HG_SETTINGS(bpy.types.PropertyGroup):   
    ######### back end #########
    diagnostics : bpy.props.BoolProperty(name="Diagnostic boolean", description="", default=False)
    load_exception : bpy.props.BoolProperty(name="load_exception", description="", default=False)
    subscribed : bpy.props.BoolProperty(name="subscribed", description="", default=False)
    update_exception: bpy.props.BoolProperty(default = False)

    ######### ui back end ###############
    ui_phase : bpy.props.EnumProperty(
        name="phase",
        description="",
        items = [
                ("body", "body", "", 0),
                ("face", "face", "", 1),
                ("skin", "skin", "", 2),
                ("hair", "hair", "", 3),
                ("length", "length", "", 4),
                ("creation_phase", "Creation Phase", "", 5),
                ("clothing", "clothing", "", 6),
                ("footwear", "footwear", "", 7),
                ("pose", "pose", "", 8),
                ("expression", "expression", "", 9),
                ("simulation", "simulation", "", 10),
                ("compression", "compression", "", 11),
                ("closed", "closed", "", 12),
                ("hair2", "Hair Length", "", 13),
                ("eyes", "Eyes", "", 14),
            ],
        default = "body",
        )   

    active_ui_tab : bpy.props.EnumProperty(
        name="ui_tab",
        description="",
        items = [
                ("CREATE", "Create", "", "OUTLINER_OB_ARMATURE", 0),
                #("BATCH", "Batch", "","COMMUNITY", 1),
                ("TOOLS", "Tools", "","SETTINGS", 1), #2
            ],
        default = "CREATE",
        update = tab_change_update
        )   


    ########### ui toggles #################
    #body
    indiv_scale_ui : bpy.props.BoolProperty(name="Individual Scaling", description="", default=False)
    
    #hair
    hair_length_ui : bpy.props.BoolProperty(name="Hair Length", description="", default=False)
    face_hair_ui: bpy.props.BoolProperty(name="Facial Hair", description="Click to unfold facial hair ui", default=False)
    hair_mat_ui: bpy.props.BoolProperty(name="Hair Material", description="", default=False)
    hair_cards_ui: bpy.props.BoolProperty(name="Hair Cards", description="", default=False)

    #skin
    makeup_ui: bpy.props.BoolProperty(default=False)
    beard_shadow_ui: bpy.props.BoolProperty(default=False)
    main_skin_ui: bpy.props.BoolProperty(default=True)
    light_dark_ui: bpy.props.BoolProperty(default=False)
    freckles_ui: bpy.props.BoolProperty(default=False)
    age_ui: bpy.props.BoolProperty(default=False)
    beautyspots_ui: bpy.props.BoolProperty(default=False)
    eyes_section: bpy.props.BoolProperty(default=False)
    texture_ui: bpy.props.BoolProperty(default=True)

    #clothes
    summer_toggle: bpy.props.BoolProperty(name="Summer Clothes", description="", default=True, update = lambda a,b: refresh_pcoll(a,b,"outfit"))
    normal_toggle: bpy.props.BoolProperty(name="Normal Clothes", description="", default=True, update = lambda a,b: refresh_pcoll(a,b,"outfit"))
    winter_toggle: bpy.props.BoolProperty(name="Winter Clothes", description="", default=True, update = lambda a,b: refresh_pcoll(a,b,"outfit"))
    inside_toggle: bpy.props.BoolProperty(name="Inside Clothes", description="", default=True, update = lambda a,b: refresh_pcoll(a,b,"outfit"))
    outside_toggle: bpy.props.BoolProperty(name="Outside Clothes", description="", default=True, update = lambda a,b: refresh_pcoll(a,b,"outfit"))
    clothing_sidebar_toggle:  bpy.props.BoolProperty(name="", description="Click to unfold sidebar", default=False)

    #pose
    pose_choice : bpy.props.EnumProperty(
        name="posing",
        description="",
        items = [
                ("library", "Library", "", 0),
                ("rigify", "Rigify", "", 1),
                #("retarget", "Retarget", "", 2),
            ],
        default = "library",
        )   

    #expression
    expression_slider_ui:  bpy.props.BoolProperty(name="Expression sliders", description="Click to unfold panel", default=True)
    expression_type : bpy.props.EnumProperty(
        name="Expression",
        description="",
        items = [
                ("1click", "1-Click", "", 0),
                ("frig", "Face Rig", "", 1),
                #("retarget", "Retarget", "", 2),
            ],
        default = "1click",
        )   


    #material mode
    material_ui : bpy.props.BoolProperty(name="", description="", default=False)
    pattern_bool : bpy.props.BoolProperty(name="Bottom", description="", default=False)
    decal_bool : bpy.props.BoolProperty(name="Footwear", description="", default=False)

    #face
    ui_nose: bpy.props.BoolProperty(name="Nose", description="", default=False)
    ui_cheeks: bpy.props.BoolProperty(name="Cheeks", description="", default=False)
    ui_eyes: bpy.props.BoolProperty(name="Eyes", description="", default=False)
    ui_l_skull: bpy.props.BoolProperty(name="Lower Skull", description="", default=False)
    ui_u_skull: bpy.props.BoolProperty(name="Upper Skull", description="", default=False)
    ui_chin: bpy.props.BoolProperty(name="Chin", description="", default=False)
    ui_ears: bpy.props.BoolProperty(name="Ears", description="", default=False)
    ui_mouth: bpy.props.BoolProperty(name="Mouth", description="", default=False)
    ui_jaw: bpy.props.BoolProperty(name="Jaw", description="", default=False)
    ui_other: bpy.props.BoolProperty(name="Other", description="", default=False)
    ui_custom: bpy.props.BoolProperty(name="Custom", description="", default=False)
    ui_presets: bpy.props.BoolProperty(name="Presets", description="", default=False)


    thumb_ui: bpy.props.BoolProperty(default=False)

    ############# creation ##############
    gender: bpy.props.EnumProperty(
        name="Gender",
        description="Choose a gender",
        items = [
                ("male", "Male", "", 0),
                ("female", "Female", "", 1),
            ],
        default = "male",
        update = lambda a,b: refresh_pcoll(a,b,"humans")
        )    

    human_length: bpy.props.FloatProperty(default = 183, soft_min = 150, soft_max = 200, min = 120, max = 250, update = update_length_v2)#, unit = 'LENGTH')

    head_size: bpy.props.FloatProperty(default = .5, soft_min = 0, soft_max = 1, update = lambda a,b: scale_bones(a,b,"head"))
    neck_size: bpy.props.FloatProperty(default = .5, soft_min = 0, soft_max = 1, update = lambda a,b: scale_bones(a,b,"neck"))
    
    chest_size: bpy.props.FloatProperty(default = .5, soft_min = 0, soft_max = 1, update = lambda a,b: scale_bones(a,b,"chest"))
    shoulder_size: bpy.props.FloatProperty(default = .5, soft_min = 0, soft_max = 1, update = lambda a,b: scale_bones(a,b,"shoulder"))
    breast_size: bpy.props.FloatProperty(default = .5, soft_min = 0, soft_max = 1, update = lambda a,b: scale_bones(a,b,"breast"))
    hips_size: bpy.props.FloatProperty(default = .5, soft_min = 0, soft_max = 1, update = lambda a,b: scale_bones(a,b,"hips"))
    
    upper_arm_size: bpy.props.FloatProperty(default = .5, soft_min = 0, soft_max = 1, update = lambda a,b: scale_bones(a,b,"upper_arm"))
    forearm_size: bpy.props.FloatProperty(default = .5, soft_min = 0, soft_max = 1, update = lambda a,b: scale_bones(a,b,"forearm"))
    hand_size: bpy.props.FloatProperty(default = .5, soft_min = 0, soft_max = 1, update = lambda a,b: scale_bones(a,b,"hand"))

    thigh_size: bpy.props.FloatProperty(default = .5, soft_min = 0, soft_max = 1, update = lambda a,b: scale_bones(a,b,"thigh"))
    shin_size: bpy.props.FloatProperty(default = .5, soft_min = 0, soft_max = 1, update = lambda a,b: scale_bones(a,b,"shin"))
    foot_size: bpy.props.FloatProperty(default = .5, soft_min = 0, soft_max = 1, update = lambda a,b: scale_bones(a,b,"foot"))




    ####### preview collections ########
    #creation
    pcoll_humans: bpy.props.EnumProperty(
        items = lambda a,b: get_pcoll_items(a,b,"humans")
        )  

    #posing
    pcoll_poses: bpy.props.EnumProperty(
        items = lambda a,b: get_pcoll_items(a,b,"poses"),
        update = apply_pose
        )   
    pose_sub : bpy.props.EnumProperty(
        name="Pose Library",
        items = lambda a,b: find_folders(a,b,"poses", False),
        update = lambda a,b: refresh_pcoll(a,b,"poses")
        )   
    search_term_poses : bpy.props.StringProperty(name = 'Search:', default = '', update = lambda a,b: refresh_pcoll(a,b,"poses") )

    #outfit
    pcoll_outfit: bpy.props.EnumProperty(
        items = lambda a,b: get_pcoll_items(a,b,"outfit"),
        update = lambda a,b: load_outfit(a,b, footwear = False)
        )  
    outfit_sub : bpy.props.EnumProperty(
        name="Outfit Library",
        items = lambda a,b: find_folders(a,b,'outfits', True),
        update = lambda a,b: refresh_pcoll(a,b,"outfit")
        ) 
    search_term_outfit : bpy.props.StringProperty(name = 'Search:', default = '', update = lambda a,b: refresh_pcoll(a,b,"outfit") )

    #hair
    pcoll_hair: bpy.props.EnumProperty(
        items = lambda a,b: get_pcoll_items(a,b,"hair"),
        update = lambda a,b: load_hair(a,b,"head")
        )  
    hair_sub : bpy.props.EnumProperty(
        name="Hair Library",
        items = lambda a,b: find_folders(a,b,'hair/head', True),
        update = lambda a,b: refresh_pcoll(a,b,"hair")
        ) 
    pcoll_face_hair: bpy.props.EnumProperty(
        items = lambda a,b: get_pcoll_items(a,b,"face_hair"),
        update = lambda a,b: load_hair(a,b,"face")
        )  
    face_hair_sub : bpy.props.EnumProperty(
        name="Facial Hair Library",
        items = lambda a,b: find_folders(a,b,'hair/face_hair', False),
        update = lambda a,b: refresh_pcoll(a,b,"face_hair")
        ) 

    #expression
    pcoll_expressions: bpy.props.EnumProperty(
        items = lambda a,b: get_pcoll_items(a,b,"expressions"),
        update = load_expression
        )  
    expressions_sub : bpy.props.EnumProperty(
        name="Expressions Library",
        items = lambda a,b: find_folders(a,b,'expressions', False),
        update = lambda a,b: refresh_pcoll(a,b,"expressions")
        ) 
    search_term_expressions : bpy.props.StringProperty(name = 'Search:', default = '', update = lambda a,b: refresh_pcoll(a,b,"expressions") )

    #footwear
    pcoll_footwear: bpy.props.EnumProperty(
        items = lambda a,b: get_pcoll_items(a,b,"footwear"),
        update = lambda a,b: load_outfit(a,b, footwear = True)
        )  
    footwear_sub : bpy.props.EnumProperty(
        name="Footwear Library",
        items = lambda a,b: find_folders(a,b,'footwear', True),
        update = lambda a,b: refresh_pcoll(a,b,"footwear")
        ) 
    search_term_footwear : bpy.props.StringProperty(name = 'Search:', default = '', update = lambda a,b: refresh_pcoll(a,b,"footwear") )

    #patterns
    pcoll_patterns: bpy.props.EnumProperty(
        items = lambda a,b: get_pcoll_items(a,b,"patterns"),
        update = load_pattern
        )  
    patterns_sub : bpy.props.EnumProperty(
        name="Pattern Library",
        items = lambda a,b: find_folders(a,b,"patterns", False),
        update = lambda a,b: refresh_pcoll(a,b,"patterns")
        )  
    search_term_patterns : bpy.props.StringProperty(name = 'Search:', default = '', update = lambda a,b: refresh_pcoll(a,b,"patterns") )

    pcoll_textures: bpy.props.EnumProperty(
        items = lambda a,b: get_pcoll_items(a,b,"textures"),
        update = load_textures
        )  
    texture_library : bpy.props.EnumProperty(
        name="Texture Library",
        items = lambda a,b: find_folders(a,b,"textures", True, include_all = False),
        update = lambda a,b: refresh_pcoll(a,b,"textures")
        )  


    preset_thumbnail_enum: bpy.props.EnumProperty(
        items = get_preset_thumbnail,
        )  

    ######### skin props ###########
    skin_sss: bpy.props.EnumProperty(
        description="Turns on/off subsurface scattering on the skin shader",
        items = [
                ("on", "On ", "", 0),
                ("off", "Off", "", 1),
            ],
        default = "off",
        update = toggle_sss
        )  

    ####### batch mode ###########
    generate_amount: bpy.props.IntProperty(name = 'Amount', default = 10, min = 1, max = 100)
    batch_progress: bpy.props.IntProperty(subtype='PERCENTAGE', min = 0, max = 100, default = 0)

    male_chance: bpy.props.IntProperty(name = 'Male', subtype="PERCENTAGE", min=0, max=100, default = 100)
    female_chance:  bpy.props.IntProperty(name = 'Female',subtype="PERCENTAGE", min=0, max=100, default = 100)

    caucasian_chance:  bpy.props.IntProperty(name = 'Caucasian',subtype="PERCENTAGE", min=0, max=100, default = 100)
    black_chance:  bpy.props.IntProperty(name = 'Black',subtype="PERCENTAGE", min=0, max=100, default = 100)
    asian_chance:  bpy.props.IntProperty(name = 'Asian',subtype="PERCENTAGE", min=0, max=100, default = 100)

    batch_pose: bpy.props.BoolProperty(default = False)
    batch_clothing: bpy.props.BoolProperty(default = True)
    batch_expression: bpy.props.BoolProperty(default = False)
    batch_hair: bpy.props.BoolProperty(default = True)

    batch_hairtype: bpy.props.EnumProperty(
        name="Hair Type",
        description="",
        items = [
                ("system", "Hair Systems", "", 0),
                ("cards", "Hair Cards", "", 1),
            ],
        default = "system",
        )    

    batch_clothing_inside:  bpy.props.BoolProperty(name="Inside", description="", default=True, update = lambda a,b: HG_BATCH_UILIST.uilist_refresh(a,b,"outfits"))
    batch_clothing_outside:  bpy.props.BoolProperty(name="Outside", description="", default=True, update = lambda a,b: HG_BATCH_UILIST.uilist_refresh(a,b,"outfits"))


    ######### Dev tools ######## 
    shapekey_calc_type: bpy.props.EnumProperty(
        name="calc type",
        description="",
        items = [
                ("pants", "Bottom", "", 0),
                ("top", "Top", "", 1),
                ("shoe", "Footwear", "", 2),
                ("full", "Full Body", "", 2),
            ],
        default = "top",
        )   
    dev_delete_unselected : bpy.props.BoolProperty(name="Delete unselected objs", description="", default=True)
    dev_tools_ui:  bpy.props.BoolProperty(name="Developer tools", description="", default=True)
    calc_gender:  bpy.props.BoolProperty(name="Calculate both genders", description="", default=False)
    dev_mask_name: bpy.props.EnumProperty(
        name="mask_name",
        description="",
        items = [
                ("lower_short", "Lower Short", "", 0),
                ("lower_long", "Lower Long", "", 1),
                ("torso", "Torso", "", 2),
                ("arms_short", "Arms Short", "", 3),
                ("arms_long", "Arms Long", "", 4),
                ("foot", "Foot", "", 5),
            ],
        default = "lower_short",
        )  

    hair_json_path: bpy.props.StringProperty(subtype = 'FILE_PATH')
    hair_json_name: bpy.props.StringProperty()

    pcoll_render: bpy.props.EnumProperty(
        items = [
                ("outfit", "outfit", "", 0),
                ("hair", "hair", "", 1),
                ("face_hair", "facial hair", "", 2),
                ("expressions", "expressions", "", 3),
                ("poses", "poses", "", 4),
                ("patterns", "patterns", "", 5),
                ("randomize_human", "randomize_human", "", 6),
            ],
        default = "outfit"
        )   

    thumb_render_path: bpy.props.StringProperty(
        default=  '',
        subtype = 'DIR_PATH'
    )

    hair_mat_male : bpy.props.EnumProperty(
        name="posing",
        description="",
        items = [
                ("eye", "Eyebrows & Eyelashes", "", 0),
                ("face", "Facial Hair", "", 1),
                ("head", "Hair", "", 2),
            ],
        default = "eye",
        )   

    hair_mat_female : bpy.props.EnumProperty(
        name="posing",
        description="",
        items = [
                ("eye", "Eyebrows & Eyelashes", "", 0),
                ("head", "Hair", "", 1),
            ],
        default = "eye",
        )   


    #baking
    bake_res_body: bpy.props.EnumProperty(
        items = get_resolutions(),
        default = "4096",
        )  
    bake_res_eyes: bpy.props.EnumProperty(
        items = get_resolutions(),
        default = "1024",
        )  
    bake_res_teeth: bpy.props.EnumProperty(
        items = get_resolutions(),
        default = "1024",
        )  
    bake_res_clothes: bpy.props.EnumProperty(
        items = get_resolutions(),
        default = "2048",
        )  


    bake_export_folder: bpy.props.StringProperty(name= 'Baking export', subtype = 'DIR_PATH', default = '', update = lambda s,c: make_path_absolute('bake_export_folder'))

    bake_samples: bpy.props.EnumProperty(
        items = [
                ("4", "4", "", 0),
                ("16", "16", "", 1),
                ("64", "64", "", 2),
            ],
        default = "4",
        )  


    bake_file_type: bpy.props.EnumProperty(
        items = [
                ("png", ".PNG", "", 0),
                ("jpeg", ".JPEG", "", 1),
                ("tiff", ".TIFF", "", 2),
            ],
        default = "png",
        )  

    modapply_search_objects: bpy.props.EnumProperty(
        name = 'Objects to apply',
        items = [
                ("selected", "Selected objects", "", 0),
                ("full", "Full human", "", 1),
                ("all", "All humans", "", 2),
            ],
        default = "full",
        update = refresh_modapply
        )  

    modapply_search_modifiers: bpy.props.EnumProperty(
        name = 'Modifier display method',
        items = [
                ("summary", "Modifier summary", "", 0),
                ("individual", "Individual modifiers", "", 1),
            ],
        default = "summary",
        update = refresh_modapply
        )  

    modapply_apply_hidden: bpy.props.BoolProperty(default = False)
    modapply_keep_shapekeys: bpy.props.BoolProperty(default = True)
    save_shapekeys_as: bpy.props.EnumProperty(
        name = 'Save as',
        items = [
                ("ff", "Facial features", "", 0),
                ("bp", "Body Proportions", "", 1),
                ("pr", "Ethnicity/Preset", "", 1),
            ],
        default = "ff",
        )  
    
    preset_thumbnail: bpy.props.PointerProperty(type=bpy.types.Image ,description='Thumbnail image for starting human')
    preset_name: bpy.props.StringProperty(default = '')

    shapekey_col_name: bpy.props.StringProperty(default = '')
    show_saved_sks: bpy.props.BoolProperty(default = False, update = refresh_shapekeys_ul)

    hairstyle_name: bpy.props.StringProperty(default = '')
    save_hairtype: bpy.props.EnumProperty(
        name = 'Hairtype',
        items = [
                ("head", "Regular Hair", "", 0),
                ("face_hair", "Facial Hair", "", 1),
            ],
        default = "head",
        )  

    savehair_male: bpy.props.BoolProperty(default = True)
    savehair_female: bpy.props.BoolProperty(default = True)
    show_eyesystems: bpy.props.BoolProperty(name = 'Show eye hairsystems', default = False, update = refresh_hair_ul)

    saveoutfit_name: bpy.props.StringProperty(default = '')
    saveoutfit_categ: bpy.props.EnumProperty(
        name = 'Clothing type',
        items = [
                ("outfits", "Outfit", "", 0),
                ("footwear", "Footwear", "", 1),
            ],
        default = "outfits",
        )  

    saveoutfit_male: bpy.props.BoolProperty(default = True)
    saveoutfit_female: bpy.props.BoolProperty(default = True)
    saveoutfit_human: bpy.props.PointerProperty(name = 'Human', type = bpy.types.Object)
    
    open_exported_outfits: bpy.props.BoolProperty(default = False)
    open_exported_hair: bpy.props.BoolProperty(default = False)
    open_exported_shapekeys: bpy.props.BoolProperty(default = False)

    mtc_armature: bpy.props.PointerProperty(name = 'Armature', type = bpy.types.Object, poll = poll_mtc_armature)
    mtc_add_armature_mod: bpy.props.BoolProperty(default = True)
    mtc_parent: bpy.props.BoolProperty(default = True)

class HG_OBJECT_PROPS(bpy.types.PropertyGroup):
    ishuman : bpy.props.BoolProperty(name="Is Human", description="", default=False)
    phase : bpy.props.EnumProperty(
        name="phase",
        description="",
        items = [
                ("base_human", "base_human", "", 0),
                ("body", "body", "", 1),
                ("face", "face", "", 2),
                ("skin", "skin", "", 3),
                ("hair", "hair", "", 4),
                ("length", "length", "", 5),
                ("clothing", "clothing", "", 6),
                ("footwear", "footwear", "", 7),
                ("pose", "pose", "", 8),
                ("expression", "expression", "", 9),
                ("simulation", "simulation", "", 10),
                ("compression", "compression", "", 11),
                ("completed", "completed", "", 12),
                ("creator", "creator", "", 13),
            ],
        default = "base_human",
        )    
    gender : bpy.props.EnumProperty(
        name="gender",
        description="",
        items = [
                ("male", "male", "", 0),
                ("female", "female", "", 1),
            ],
        default = "male",
        )  
    body_obj : bpy.props.PointerProperty(name="hg_body", type=bpy.types.Object)
    backup: bpy.props.PointerProperty(name="hg_backup", type=bpy.types.Object)
    length: bpy.props.FloatProperty()
    experimental: bpy.props.BoolProperty(default = False)