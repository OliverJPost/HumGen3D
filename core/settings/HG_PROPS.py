
import bpy  #type: ignore
from bpy.props import (         #type: ignore
    BoolProperty,
    StringProperty,
    EnumProperty,
    PointerProperty,
    IntProperty,
    FloatProperty,
    )
from ... features.common.HG_COMMON_FUNC import make_path_absolute
from ... features.utility_section.HG_UTILITY_FUNC import (
    refresh_hair_ul,
    refresh_modapply)
from . HG_PROP_FUNCTIONS import (
    find_folders,
    get_resolutions,
    poll_mtc_armature)
from ... core.HG_PCOLL import (
    refresh_pcoll,
    get_pcoll_enum_items)
from ... features.finalize_phase.HG_POSE import apply_pose
from ... features.finalize_phase.HG_CLOTHING import load_pattern 
from ... features.finalize_phase.HG_CLOTHING_LOAD import load_outfit
from ... features.finalize_phase.HG_EXPRESSION import load_expression
from ... features.creation_phase.HG_HAIR import load_hair
from ... features.creation_phase.HG_MATERIAL import load_textures
from ... features.creation_phase.HG_BODY import scale_bones
from ... user_interface import HG_BATCH_UILIST
from ... features.creation_phase.HG_SKIN import toggle_sss
from ... core.HG_CALLBACK import tab_change_update
from ... features.creation_phase.HG_LENGTH import update_length_v2
from ... features.utility_section.HG_UTILITY_FUNC import (
    get_preset_thumbnail,
    refresh_shapekeys_ul)


class HG_SETTINGS(bpy.types.PropertyGroup):   
    ######### back end #########
    diagnostics : BoolProperty(
        name="Diagnostic boolean",
        default=False)
    load_exception  : BoolProperty(
        name="load_exception",
        default=False)
    subscribed : BoolProperty(
        name="subscribed",
        default=False)
    update_exception: BoolProperty(default = False)

    ######### ui back end ###############
    ui_phase : EnumProperty(
        name="phase",
        items = [
                ("body",            "body",           "", 0),
                ("face",            "face",           "", 1),
                ("skin",            "skin",           "", 2),
                ("hair",            "hair",           "", 3),
                ("length",          "length",         "", 4),
                ("creation_phase",  "Creation Phase", "", 5),
                ("clothing",        "clothing",       "", 6),
                ("footwear",        "footwear",       "", 7),
                ("pose",            "pose",           "", 8),
                ("expression",      "expression",     "", 9),
                ("simulation",      "simulation",     "", 10),
                ("compression",     "compression",    "", 11),
                ("closed",          "closed",         "", 12),
                ("hair2",           "Hair Length",    "", 13),
                ("eyes",            "Eyes",           "", 14),
            ],
        default = "body",
        )   

    active_ui_tab : EnumProperty(
        name = "ui_tab",
        items = [
                ("CREATE", "Create", "", "OUTLINER_OB_ARMATURE", 0),
                #("BATCH", "Batch", "","COMMUNITY", 1),
                ("TOOLS", "Tools", "","SETTINGS", 1), #2
            ],
        default = "CREATE",
        update  = tab_change_update
        )   


    ########### ui toggles #################
    #body
    indiv_scale_ui: BoolProperty(name="Individual Scaling", default=False)
    
    #hair
    hair_length_ui : BoolProperty(name="Hair Length", default=False)
    face_hair_ui   : BoolProperty(name="Facial Hair",
                                  description="Click to unfold facial hair ui",
                                  default=False)
    hair_mat_ui    : BoolProperty(name="Hair Material", default=False)
    hair_cards_ui  : BoolProperty(name="Hair Cards", default=False)

    #skin
    makeup_ui      : BoolProperty(default=False)
    beard_shadow_ui: BoolProperty(default=False)
    main_skin_ui   : BoolProperty(default=True)
    light_dark_ui  : BoolProperty(default=False)
    freckles_ui    : BoolProperty(default=False)
    age_ui         : BoolProperty(default=False)
    beautyspots_ui : BoolProperty(default=False)
    eyes_section   : BoolProperty(default=False)
    texture_ui     : BoolProperty(default=True)

    #pose
    pose_choice : EnumProperty(
        name = "posing",
        items = [
                ("library", "Library", "", 0),
                ("rigify",  "Rigify",  "", 1),
            ],
        default = "library",
        )   

    #expression
    expression_slider_ui: BoolProperty(
        name="Expression sliders",
        description="Click to unfold panel",
        default=True)
    expression_type : EnumProperty(
        name="Expression",
        items = [
                ("1click", "1-Click",  "", 0),
                ("frig",   "Face Rig", "", 1),
            ],
        default = "1click",
        )   


    #material mode
    material_ui : BoolProperty(name = "",         default=False)
    pattern_bool: BoolProperty(name = "Bottom",   default=False)
    decal_bool  : BoolProperty(name = "Footwear", default=False)

    #face
    ui_nose   : BoolProperty(name = "Nose",        default=False)
    ui_cheeks : BoolProperty(name = "Cheeks",      default=False)
    ui_eyes   : BoolProperty(name = "Eyes",        default=False)
    ui_l_skull: BoolProperty(name = "Lower Skull", default=False)
    ui_u_skull: BoolProperty(name = "Upper Skull", default=False)
    ui_chin   : BoolProperty(name = "Chin",        default=False)
    ui_ears   : BoolProperty(name = "Ears",        default=False)
    ui_mouth  : BoolProperty(name = "Mouth",       default=False)
    ui_jaw    : BoolProperty(name = "Jaw",         default=False)
    ui_other  : BoolProperty(name = "Other",       default=False)
    ui_custom : BoolProperty(name = "Custom",      default=False)
    ui_presets: BoolProperty(name = "Presets",     default=False)


    thumb_ui: BoolProperty(default=False)

    ############# creation ##############
    gender: EnumProperty(
        name        = "Gender",
        description = "Choose a gender",
        items       = [
                ("male",   "Male",   "", 0),
                ("female", "Female", "", 1),
            ],
        default     = "male",
        update      = lambda a, b: refresh_pcoll(a,b,"humans")
        )    

    human_length: FloatProperty(
        default = 183,
        soft_min = 150,
        soft_max = 200,
        min = 120,
        max = 250,
        update = update_length_v2
        )

    head_size: FloatProperty(
        default = .5,
        soft_min = 0,
        soft_max = 1,
        update = lambda a,b: scale_bones(a,b,"head")
        )
    neck_size: FloatProperty(
        default = .5,
        soft_min = 0,
        soft_max = 1,
        update = lambda a,b: scale_bones(a,b,"neck")
        )
    
    chest_size: FloatProperty(
        default = .5,
        soft_min = 0,
        soft_max = 1,
        update = lambda a,b: scale_bones(a,b,"chest")
        )
    shoulder_size: FloatProperty(
        default = .5,
        soft_min = 0,
        soft_max = 1,
        update = lambda a,b: scale_bones(a,b,"shoulder")
        )
    breast_size: FloatProperty(
        default = .5,
        soft_min = 0,
        soft_max = 1,
        update = lambda a,b: scale_bones(a,b,"breast")
        )
    hips_size: FloatProperty(
        default=.5,
        soft_min=0,
        soft_max=1,
        update=lambda a,b: scale_bones(a, b, "hips")
    )
    
    upper_arm_size: FloatProperty(
        default=.5,
        soft_min=0,
        soft_max=1,
        update=lambda a,b: scale_bones(a, b, "upper_arm")
    )
    forearm_size: FloatProperty(
        default=.5,
        soft_min=0,
        soft_max=1,
        update=lambda a,b: scale_bones(a, b, "forearm")
    )
    hand_size: FloatProperty(
        default=.5,
        soft_min=0,
        soft_max=1,
        update=lambda a, b: scale_bones(a, b, "hand")
    )

    thigh_size: FloatProperty(
        default=.5,
        soft_min=0,
        soft_max=1,
        update=lambda a, b: scale_bones(a, b, "thigh")
    )
    shin_size: FloatProperty(
        default=.5,
        soft_min=0,
        soft_max=1,
        update=lambda a, b: scale_bones(a, b, "shin")
    )
    foot_size: FloatProperty(
        default=.5,
        soft_min=0,
        soft_max=1,
        update=lambda a, b: scale_bones(a, b, "foot")
    )


    ####### preview collections ########
    #creation
    pcoll_humans: EnumProperty(
        items = lambda a,b: get_pcoll_enum_items(a,b,"humans")
        )  

    #posing
    pcoll_poses: EnumProperty(
        items  = lambda a,b: get_pcoll_enum_items(a,b,"poses"),
        update = apply_pose
        )   
    pose_sub : EnumProperty(
        name="Pose Library",
        items  = lambda a,b: find_folders(a,b,"poses", False),
        update = lambda a,b: refresh_pcoll(a,b,"poses")
        )   
    search_term_poses: StringProperty(
        name='Search:',
        default='',
        update=lambda a, b: refresh_pcoll(a, b, "poses")
    )

    #outfit
    pcoll_outfit: EnumProperty(
        items  = lambda a,b: get_pcoll_enum_items(a,b,"outfit"),
        update = lambda a,b: load_outfit(a,b, footwear = False)
        )  
    outfit_sub : EnumProperty(
        name="Outfit Library",
        items  = lambda a,b: find_folders(a,b,'outfits', True),
        update = lambda a,b: refresh_pcoll(a,b,"outfit")
        ) 
    search_term_outfit: StringProperty(
        name='Search:',
        default='',
        update=lambda a, b: refresh_pcoll(a, b, "outfit")
    )

    #hair
    pcoll_hair: EnumProperty(
        items  = lambda a,b: get_pcoll_enum_items(a,b,"hair"),
        update = lambda a,b: load_hair(a,b,"head")
        )  
    hair_sub : EnumProperty(
        name="Hair Library",
        items  = lambda a,b: find_folders(a,b,'hair/head', True),
        update = lambda a,b: refresh_pcoll(a,b,"hair")
        ) 
    pcoll_face_hair: EnumProperty(
        items  = lambda a,b: get_pcoll_enum_items(a,b,"face_hair"),
        update = lambda a,b: load_hair(a,b,"face")
        )  
    face_hair_sub : EnumProperty(
        name="Facial Hair Library",
        items  = lambda a,b: find_folders(a,b,'hair/face_hair', False),
        update = lambda a,b: refresh_pcoll(a,b,"face_hair")
        ) 

    #expression
    pcoll_expressions: EnumProperty(
        items  = lambda a,b: get_pcoll_enum_items(a,b,"expressions"),
        update = load_expression
        )  
    expressions_sub : EnumProperty(
        name="Expressions Library",
        items  = lambda a,b: find_folders(a,b,'expressions', False),
        update = lambda a,b: refresh_pcoll(a,b,"expressions")
        ) 
    search_term_expressions: StringProperty(
        name='Search:',
        default='',
        update=lambda a, b: refresh_pcoll(a, b, "expressions")
    )

    #footwear
    pcoll_footwear: EnumProperty(
        items  = lambda a,b: get_pcoll_enum_items(a,b,"footwear"),
        update = lambda a,b: load_outfit(a,b, footwear = True)
        )  
    footwear_sub : EnumProperty(
        name="Footwear Library",
        items  = lambda a,b: find_folders(a,b,'footwear', True),
        update = lambda a,b: refresh_pcoll(a,b,"footwear")
        ) 
    search_term_footwear: StringProperty(
        name='Search:',
        default='',
        update=lambda a, b: refresh_pcoll(a, b, "footwear")
    )

    #patterns
    pcoll_patterns: EnumProperty(
        items = lambda a,b: get_pcoll_enum_items(a,b,"patterns"),
        update = load_pattern
        )  
    patterns_sub : EnumProperty(
        name="Pattern Library",
        items  = lambda a,b: find_folders(a,b,"patterns", False),
        update = lambda a,b: refresh_pcoll(a,b,"patterns")
        )  
    search_term_patterns: StringProperty(
        name='Search:',
        default='',
        update=lambda a, b: refresh_pcoll(a, b, "patterns")
    )

    pcoll_textures: EnumProperty(
        items  = lambda a,b: get_pcoll_enum_items(a,b,"textures"),
        update = load_textures
        )  
    texture_library : EnumProperty(
        name="Texture Library",
        items  = lambda a,b: find_folders(a,b,"textures",
                                          True,
                                          include_all = False),
        update = lambda a,b: refresh_pcoll(a,b,"textures")
        )  

    preset_thumbnail_enum: EnumProperty(
        items = get_preset_thumbnail,
        )  

    ######### skin props ###########
    skin_sss: EnumProperty(
        description="Turns on/off subsurface scattering on the skin shader",
        items = [
                ("on",  "On ", "", 0),
                ("off", "Off", "", 1),
            ],
        default = "off",
        update = toggle_sss
        )  

    ####### batch mode ###########
    generate_amount:IntProperty(name='Amount',
                                default=10,
                                min=1,
                                max=100)
    batch_progress: IntProperty(subtype='PERCENTAGE',
                                min=0,
                                max=100,
                                default=0)

    male_chance:    IntProperty(name='Male',
                                subtype="PERCENTAGE",
                                min=0,
                                max=100,
                                default=100)
    female_chance:  IntProperty(name='Female',
                                subtype="PERCENTAGE",
                                min=0,
                                max=100,
                                default=100)


    caucasian_chance: IntProperty(name='Caucasian',
                                  subtype="PERCENTAGE",
                                  min=0,
                                  max=100,
                                  default=100)
    black_chance:     IntProperty(name='Black',
                                  subtype="PERCENTAGE",
                                  min=0,
                                  max=100,
                                  default=100)
    asian_chance:     IntProperty(name='Asian',
                                  subtype="PERCENTAGE",
                                  min=0,
                                  max=100,
                                  default=100)

    batch_pose      : BoolProperty(default = False)
    batch_clothing  : BoolProperty(default = True)
    batch_expression: BoolProperty(default = False)
    batch_hair      : BoolProperty(default = True)

    batch_hairtype: EnumProperty(
        name="Hair Type",   
        items = [
                ("system", "Hair Systems", "", 0),
                ("cards",  "Hair Cards",   "", 1),
            ],
        default = "system",
        )    

    batch_clothing_inside: BoolProperty(
        name="Inside",
        default=True,
        update=lambda a, b: HG_BATCH_UILIST.uilist_refresh(a, b, "outfits")
    )
    batch_clothing_outside: BoolProperty(
        name="Outside",
        default=True,
        update=lambda a, b: HG_BATCH_UILIST.uilist_refresh(a, b, "outfits")
    )

    ######### Dev tools ######## 
    shapekey_calc_type: EnumProperty(
        name="calc type",   
        items = [
                ("pants", "Bottom",    "", 0),
                ("top",   "Top",       "", 1),
                ("shoe",  "Footwear",  "", 2),
                ("full",  "Full Body", "", 2),
            ],
        default = "top",
        )   
    dev_delete_unselected: BoolProperty(name="Delete unselected objs",
                                        default=True)
    dev_tools_ui: BoolProperty(name="Developer tools", default=True)
    calc_gender : BoolProperty(name="Calculate both genders", default=False)
    dev_mask_name: EnumProperty(
        name="mask_name",
        items = [
                ("lower_short", "Lower Short", "", 0),
                ("lower_long",  "Lower Long",  "", 1),
                ("torso",       "Torso",       "", 2),
                ("arms_short",  "Arms Short",  "", 3),
                ("arms_long",   "Arms Long",   "", 4),
                ("foot",        "Foot",        "", 5),
            ],
        default = "lower_short",
        )  

    hair_json_path: StringProperty(subtype = 'FILE_PATH')
    hair_json_name: StringProperty()

    pcoll_render: EnumProperty(
        items = [ 
                ("outfit",          "outfit",          "", 0),
                ("hair",            "hair",            "", 1),
                ("face_hair",       "facial hair",     "", 2),
                ("expressions",     "expressions",     "", 3),
                ("poses",           "poses",           "", 4),
                ("patterns",        "patterns",        "", 5),
                ("randomize_human", "randomize_human", "", 6),
            ],
        default = "outfit"
        )   

    thumb_render_path: StringProperty(
        default = '',
        subtype = 'DIR_PATH'
    )
    dont_export_thumb: BoolProperty(default = False)

    hair_mat_male : EnumProperty(
        name="posing",
        
        items = [
                ("eye",  "Eyebrows & Eyelashes", "", 0),
                ("face", "Facial Hair",          "", 1),
                ("head", "Hair",                 "", 2),
            ],
        default = "eye",
        )   

    hair_mat_female : EnumProperty(
        name="posing",
        
        items = [
                ("eye",  "Eyebrows & Eyelashes", "", 0),
                ("head", "Hair",                 "", 1),
            ],
        default = "eye",
        )   


    #baking
    bake_res_body: EnumProperty(
        items   = get_resolutions(),
        default = "4096",
        )  
    bake_res_eyes: EnumProperty(
        items   = get_resolutions(),
        default = "1024",
        )  
    bake_res_teeth: EnumProperty(
        items   = get_resolutions(),
        default = "1024",
        )  
    bake_res_clothes: EnumProperty(
        items   = get_resolutions(),
        default = "2048",
        )  

    bake_export_folder: StringProperty(
        name='Baking export',
        subtype='DIR_PATH',
        default='',
        update=lambda s, c: make_path_absolute('bake_export_folder')
    )

    bake_samples: EnumProperty(
        items = [
                ( "4",  "4", "", 0),
                ("16", "16", "", 1),
                ("64", "64", "", 2),
            ],
        default = "4",
        )  


    bake_file_type: EnumProperty(
        items = [
                ("png",   ".PNG", "", 0),
                ("jpeg", ".JPEG", "", 1),
                ("tiff", ".TIFF", "", 2),
            ],
        default = "png",
        )  

    modapply_search_objects: EnumProperty(
        name  = 'Objects to apply',
        items = [
                ("selected", "Selected objects", "", 0),
                ("full",     "Full human",       "", 1),
                ("all",       "All humans",      "", 2),
            ],
        default = "full",
        update  = refresh_modapply
        )  

    modapply_search_modifiers: EnumProperty(
        name = 'Modifier display method',
        items = [
                ("summary",    "Modifier summary",     "", 0),
                ("individual", "Individual modifiers", "", 1),
            ],
        default = "summary",
        update = refresh_modapply
        )  

    modapply_apply_hidden  : BoolProperty(default = False)
    modapply_keep_shapekeys: BoolProperty(default = True)
    save_shapekeys_as      : EnumProperty(
        name = 'Save as',
        items = [
                ("ff", "Facial features", "", 0),
                ("bp", "Body Proportions", "", 1),
                ("pr", "Ethnicity/Preset", "", 1),
            ],
        default = "ff",
        )  
    
    preset_thumbnail: PointerProperty(
        type=bpy.types.Image,
        description='Thumbnail image for starting human')
    preset_name     : StringProperty(default = '')

    shapekey_col_name: StringProperty(default = '')
    show_saved_sks   : BoolProperty(default = False,
                                    update = refresh_shapekeys_ul)

    hairstyle_name: StringProperty(default = '')
    save_hairtype: EnumProperty(
        name = 'Hairtype',
        items = [
                ("head",      "Regular Hair", "", 0),
                ("face_hair", "Facial Hair",  "", 1),
            ],
        default = "head",
        )  

    savehair_male  : BoolProperty(default = True)
    savehair_female: BoolProperty(default = True)
    show_eyesystems: BoolProperty(name = 'Show eye hairsystems',
                                  default = False,
                                  update = refresh_hair_ul)

    saveoutfit_name: StringProperty(default = '')
    saveoutfit_categ: EnumProperty(
        name = 'Clothing type',
        items = [
                ("outfits",   "Outfit", "", 0),
                ("footwear", "Footwear", "", 1),
            ],
        default = "outfits",
        )  

    saveoutfit_male  : BoolProperty(default = True)
    saveoutfit_female: BoolProperty(default = True)
    saveoutfit_human : PointerProperty(name = 'Human',
                                       type = bpy.types.Object)
    
    open_exported_outfits  : BoolProperty(default = False)
    open_exported_hair     : BoolProperty(default = False)
    open_exported_shapekeys: BoolProperty(default = False)

    mtc_armature        : PointerProperty(name = 'Armature',
                                          type = bpy.types.Object,
                                          poll = poll_mtc_armature)
    mtc_add_armature_mod: BoolProperty(default = True)
    mtc_parent          : BoolProperty(default = True)

class HG_OBJECT_PROPS(bpy.types.PropertyGroup):
    ishuman: BoolProperty(name="Is Human", default=False)
    phase  : EnumProperty(
        name="phase",
        
        items = [
                ("base_human", "base_human",   "",  0),
                ("body",        "body",        "",  1),
                ("face",        "face",        "",  2),
                ("skin",        "skin",        "",  3),
                ("hair",        "hair",        "",  4),
                ("length",      "length",      "",  5),
                ("clothing",    "clothing",    "",  6),
                ("footwear",    "footwear",    "",  7),
                ("pose",        "pose",        "",  8),
                ("expression",  "expression",  "",  9),
                ("simulation",  "simulation",  "", 10),
                ("compression", "compression", "", 11),
                ("completed",   "completed",   "", 12),
                ("creator",     "creator",     "", 13),
            ],
        default = "base_human",
        )    
    gender : EnumProperty(
        name        = "gender",
        description = "",
        items = [
                ("male",   "male",   "", 0),
                ("female", "female", "", 1),
            ],
        default = "male",
        )  
    body_obj    : PointerProperty(name="hg_body", type=bpy.types.Object)
    backup      : PointerProperty(name="hg_backup", type=bpy.types.Object)
    length      : FloatProperty()
    experimental: BoolProperty(default = False)
