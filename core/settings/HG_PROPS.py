
import bpy  # type: ignore
from bpy.props import (BoolProperty, EnumProperty,  # type: ignore
                       FloatProperty, IntProperty, PointerProperty,
                       StringProperty)

from ...core.content.HG_CUSTOM_CONTENT_PACKS import build_content_collection
from ...core.HG_CALLBACK import tab_change_update
from ...core.HG_PCOLL import get_pcoll_enum_items, refresh_pcoll
from ...features.common.HG_COMMON_FUNC import make_path_absolute
from ...features.creation_phase.HG_BODY import scale_bones
from ...features.creation_phase.HG_HAIR import (load_hair,
                                                update_hair_shader_type)
from ...features.creation_phase.HG_LENGTH import update_length
from ...features.creation_phase.HG_MATERIAL import (load_textures, toggle_sss,
                                                    toggle_underwear)
from ...features.finalize_phase.HG_CLOTHING import load_pattern
from ...features.finalize_phase.HG_CLOTHING_LOAD import load_outfit
from ...features.finalize_phase.HG_EXPRESSION import load_expression
from ...features.finalize_phase.HG_POSE import load_pose
from ...features.utility_section.HG_UTILITY_FUNC import (get_preset_thumbnail,
                                                         refresh_hair_ul,
                                                         refresh_modapply,
                                                         refresh_shapekeys_ul)
from ...user_interface import HG_BATCH_UILIST
from .HG_PROP_FUNCTIONS import (add_image_to_thumb_enum, find_folders, get_resolutions,
                                poll_mtc_armature,
                                thumbnail_saving_prop_update)


class HG_SETTINGS(bpy.types.PropertyGroup):   
    ######### back end #########
    load_exception: BoolProperty(
        name="load_exception",
        default=False)
    subscribed: BoolProperty(
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
                ("BATCH", "Batch", "","COMMUNITY", 1),
                ("TOOLS", "Tools", "","SETTINGS", 2),             ],
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
        update = update_length
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
        update = load_pose
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
    preset_thumbnail: PointerProperty(
        type=bpy.types.Image,
        description='Thumbnail image for starting human',
        update = add_image_to_thumb_enum
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

    underwear_switch: EnumProperty(
        description="Turns on/off underwear layer",
        items = [
                ("on",  "On ", "", 0),
                ("off", "Off", "", 1),
            ],
        default = "on",
        update = toggle_underwear
        )          

    ####### batch mode ###########
    generate_amount:IntProperty(name='Amount',
                                default=10,
                                min=1,
                                max=100)
    batch_progress: IntProperty(name = 'Progress',
                                subtype='PERCENTAGE',
                                min=0,
                                max=100,
                                default=0)
    batch_idx: IntProperty(default = 0)

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

    batch_performance_statistics: BoolProperty(default = False)

    batch_pose      : BoolProperty(default = False)
    batch_clothing  : BoolProperty(default = False)
    batch_expression: BoolProperty(default = False)
    batch_hair      : BoolProperty(default = False)
    batch_bake      : BoolProperty(default = False)

    batch_hairtype: EnumProperty(
        name="Hair Type",   
        items = [
                ("particle", "Particle hair", "", 0),
                ("haircards",  "Haircards",   "", 1),
            ],
        default = "particle",
        )    

    batch_clothing_inside: BoolProperty(
        name="Inside",
        default=True,
        update=lambda a, b: HG_BATCH_UILIST.batch_uilist_refresh(a, b, "outfits")
    )
    batch_clothing_outside: BoolProperty(
        name="Outside",
        default=True,
        update=lambda a, b: HG_BATCH_UILIST.batch_uilist_refresh(a, b, "outfits")
    )

    batch_marker_selection: EnumProperty(
        name="Generate batch markers",   
        items = [
                ("all", "All markers", "", 0),
                ("selected",  "Selected markers", "", 1),
                ("empty",  "Empty markers",  "", 2),
            ],
        default = "all",
        )    
    
    batch_height_system: EnumProperty(
        name="System",   
        items = [
                ("metric", "Metric", "", 0),
                ("imperial",  "Imperial", "", 1)
            ],
        default = "metric",
        )        
    batch_average_height_cm_male: IntProperty(name = 'Male [cm]', default = 175, min = 160, max = 190)
    batch_average_height_cm_female: IntProperty(name = 'Female [cm]', default = 170, min = 160, max = 190)
    
    batch_average_height_ft_male: IntProperty(name = 'ft', default = 5, min = 4, max = 6)
    batch_average_height_ft_female: IntProperty(name = 'ft', default = 5, min = 4, max = 6)
    batch_average_height_in_male: IntProperty(name = 'in', default = 10, min = 0, max = 12)
    batch_average_height_in_female: IntProperty(name = 'in', default = 10, min = 0, max = 12)
    
    batch_standard_deviation: IntProperty(name = 'Standard deviation', default = 5, subtype = 'PERCENTAGE', min = 0, max = 10)
    show_height_examples: BoolProperty(default = False)
    
    
    batch_delete_backup: BoolProperty(name = 'Delete backup human', default = True)
    batch_apply_shapekeys: BoolProperty(name = 'Apply shape keys', default = True)
    batch_apply_armature_modifier: BoolProperty(name = 'Apply armature modifier', default = True)
    batch_remove_clothing_solidify : BoolProperty(name = 'Remove clothing solidify', default = True)
    batch_remove_clothing_subdiv: BoolProperty(name = 'Remove clothing subdiv', default = True)
    batch_apply_clothing_geometry_masks: BoolProperty(name = 'Apply geometry masks', default = True)

    batch_texture_resolution: EnumProperty(
        name="Texture Resolution",   
        items = [
                ("high", "High (~4K)",    "", 0),
                ("optimised", "Optimised (~1K)",       "", 1),
                ("performance", "Performance (~512px)",  "", 2),
            ],
        default = "optimised",
        )

    batch_poly_reduction: EnumProperty(
        name="Polygon reduction",   
        items = [
                ("none", "Disabled (original topology)",    "", 0),
                ("medium", "Medium (33% polycount)", "", 1), #2x unsubdivide
                ("high", "High (15% polycount)",  "", 2), # 0.08 collapse
                ("ultra", "Ultra (5% polycount)",  "", 3), # 0.025 collapse
            ],
        default = "none",
        )
    batch_apply_poly_reduction: BoolProperty(name = 'Apply poly reduction', default = True)


    batch_hair_quality_particle: EnumProperty(
        name="Particle hair quality",   
        items = [
                ("high", "High",    "", 0),
                ("medium", "Medium", "", 1), 
                ("low", "Low",  "", 2), 
                ("ultralow", "Ultra Low",  "", 3),    
            ],
        default = "medium",
        )
    batch_hair_quality_haircards: EnumProperty(
        name="Haircard quality",   
        items = [
                ("low", "Low",  "", 1), 
                ("ultralow", "Ultra Low",  "", 2),    
            ],
        default = "low",
        )
        


    
    ######### Dev tools ######## 
    shapekey_calc_type: EnumProperty(
        name="calc type",   
        items = [
                ("pants", "Bottom",    "", 0),
                ("top",   "Top",       "", 1),
                ("shoe",  "Footwear",  "", 2),
                ("full",  "Full Body", "", 3),
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

    hair_mat_male: EnumProperty(
        name="posing",
        
        items = [
                ("eye",  "Eyebrows & Eyelashes", "", 0),
                ("face", "Facial Hair",          "", 1),
                ("head", "Hair",                 "", 2),
            ],
        default = "eye",
        )   

    hair_mat_female: EnumProperty(
        name="posing",
        
        items = [
                ("eye",  "Eyebrows & Eyelashes", "", 0),
                ("head", "Hair",                 "", 1),
            ],
        default = "eye",
        )   

    hair_shader_type: EnumProperty(
        name="Hair shader type",
        items = [
                ("fast",  "Fast", "", 0),
                ("accurate", "Accurate (Cycles only)", "", 1),
            ],
        default = "fast",
        update = update_hair_shader_type
        )   

    #baking
    bake_res_body: EnumProperty(
        items   = get_resolutions(),
        default = "1024",
        )  
    bake_res_eyes: EnumProperty(
        items   = get_resolutions(),
        default = "256",
        )  
    bake_res_teeth: EnumProperty(
        items   = get_resolutions(),
        default = "256",
        )  
    bake_res_clothes: EnumProperty(
        items   = get_resolutions(),
        default = "1024",
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

    bake_idx: IntProperty(default = 0)
    
    bake_total: IntProperty(default = 0)

    bake_progress: IntProperty(name = 'Progress',
                                subtype='PERCENTAGE',
                                min=0,
                                max=100,
                                default=0)

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
    preset_name : StringProperty(default = '')

    sk_collection_name: StringProperty(default = '')
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

    clothing_name: StringProperty(default = '')
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
    
    open_exported_outfits  : BoolProperty(default = False)
    open_exported_hair     : BoolProperty(default = False)
    open_exported_shapekeys: BoolProperty(default = False)

    mtc_armature        : PointerProperty(name = 'Armature',
                                          type = bpy.types.Object,
                                          poll = poll_mtc_armature)
    mtc_add_armature_mod: BoolProperty(default = True)
    mtc_parent          : BoolProperty(default = True)

    mask_long_arms : BoolProperty(default = False)
    mask_short_arms: BoolProperty(default = False)
    mask_long_legs : BoolProperty(default = False)
    mask_short_legs: BoolProperty(default = False)
    mask_torso     : BoolProperty(default = False)
    mask_foot      : BoolProperty(default = False)

    pose_name: StringProperty()
    pose_category_to_save_to: bpy.props.EnumProperty(
        name="Pose Category",
        items = [
            ("existing", "Existing",  "", 0),
            ("new", "Create new",  "", 1)
        ],
        default = "existing",
        )  
    pose_chosen_existing_category: EnumProperty(
        name="Pose Library",
        items  = lambda a,b: find_folders(a,b,"poses", False)
        )   
    pose_new_category_name: StringProperty()

    custom_content_categ : bpy.props.EnumProperty(
        name="Content type",
        description="",
        items = [
                ("starting_humans", "Starting Humans",  "", 0),
                ("texture_sets",    "Texture sets",     "", 1),
                ("shapekeys",       "Shapekeys",        "", 2),
                ("hairstyles",      "Hairstyles",       "", 3),
                ("poses",           "Poses",            "", 4),
                ("outfits",         "Outfits",          "", 5),
                ("footwear",        "Footwear",         "", 6)    
            ],
        default = "starting_humans",
        update = build_content_collection
        )  

    content_saving_ui: BoolProperty(default = False)
    content_saving_type: StringProperty()
    mtc_not_in_a_pose: BoolProperty(default = False)

    thumbnail_saving_enum: bpy.props.EnumProperty(
        name="Thumbnail",
        items = [
            ("none", "No thumbnail",  "", 0),
            ("auto", "Automatic render",  "", 1),
            ("custom", "Select custom image",  "", 2),
            ("last_render", "Use last render result",  "", 3)
        ],
        default = "auto",
        update = thumbnail_saving_prop_update
        )  

    
    content_saving_tab_index: IntProperty(default = 0)
    
    content_saving_active_human: PointerProperty(type = bpy.types.Object)
    content_saving_object: PointerProperty(type = bpy.types.Object)

    show_hidden_tips: bpy.props.BoolProperty(default = False)

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
    batch_result: BoolProperty(default = False)
