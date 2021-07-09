#core
from . core.HG_CALLBACK import HG_ACTIVATE
from . core.settings.HG_PREFERENCES import (
    HG_ICON_LEGEND,
    HG_PATHCHANGE,
    HG_PREF)
from . core.settings.HG_PROPS import (
    HG_OBJECT_PROPS,
    HG_SETTINGS)
from . core.content.HG_CONTENT_PACKS import (
    HG_CONTENT_PACK,
    HG_DELETE_CPACK,
    HG_DELETE_INSTALLPACK,
    HG_INSTALL_CPACK,
    HG_INSTALLPACK,
    HG_REFRESH_CPACKS,
    HG_SELECT_CPACK,
    HG_UL_CONTENTPACKS,
    HG_UL_INSTALLPACKS,
    cpacks_refresh)
from . core.content.HG_CUSTOM_CONTENT_PACKS import (
    CUSTOM_CONTENT_ITEM,
    HG_OT_CREATE_CPACK,
    HG_OT_EDIT_CPACK,
    HG_OT_SAVE_CPACK,
    HG_OT_EXIT_CPACK_EDIT,
)
from . core.content.HG_UPDATE import (
    check_update,
    UPDATE_INFO_ITEM
)
#features
    #common
from . features.common.HG_INFO_POPUPS import HG_OT_INFO
from . features.common.HG_COMMON_OPS import (
    HG_CLEAR_SEARCH,
    HG_DELETE,
    HG_DESELECT,
    HG_NEXT_PREV_HUMAN,
    HG_OPENPREF,
    HG_SECTION_TOGGLE)
from . features.common.HG_RANDOM import (
    HG_COLOR_RANDOM,
    HG_RANDOM)
    #creation phase
from . features.creation_phase.HG_BACKUP import HG_REVERT_TO_CREATION
from . features.creation_phase.HG_CREATION import HG_START_CREATION
from . features.creation_phase.HG_FACE import HG_RESET_FACE
from . features.creation_phase.HG_HAIR import (
    HG_EYEBROW_SWITCH,
    HG_REMOVE_HAIR,
    HG_TOGGLE_HAIR_CHILDREN)
from . features.creation_phase.HG_HAIRCARDS import HG_CONVERT_HAIRCARDS
from . features.creation_phase.HG_LENGTH import HG_RANDOM_LENGTH
from . features.creation_phase.HG_FINISH_CREATION_PHASE import HG_FINISH_CREATION
    #finalize phase
from . features.finalize_phase.HG_CLOTHING import (
    HG_BACK_TO_HUMAN,
    HG_DELETE_CLOTH,
    HG_OT_PATTERN)
from . features.finalize_phase.HG_EXPRESSION import (
    HG_ADD_FRIG,
    HG_REMOVE_FRIG,
    HG_REMOVE_SHAPEKEY)
from . features.finalize_phase.HG_POSE import HG_RIGIFY
    #utility section
from . features.utility_section.HG_BAKE import HG_BAKE
from . features.utility_section.HG_DEVTOOLS import *
from . features.utility_section.HG_UTILITY_OPS import (
    HG_MAKE_EXPERIMENTAL,
    HG_OT_MODAPPLY,
    HG_OT_PREPARE_FOR_ARKIT,
    HG_OT_REFRESH_UL,
    HG_OT_SELECTMODAPPLY)
from . features.utility_section.HG_CONTENT_SAVING import (
    HG_OT_SAVEOUTFIT,
    HG_OT_SAVE_SHAPEKEY,
    HG_OT_SAVEHAIR,
    HG_OT_OPEN_FOLDER,
    HG_OT_SAVEPRESET)
from . features.utility_section.HG_MESH_TO_CLOTH import (
    HG_OT_ADDCLOTHMATH,
    HG_OT_ADDCORRECTIVE,
    HG_OT_ADDMASKS,
    HG_OT_AUTOWEIGHT
)
#user interface
from . user_interface import (
    HG_MAIN_PANEL,
    HG_UTILITY_PANEL,
    HG_BATCH_PANEL,
    HG_UTILITY_UILISTS)
#tutorial operator
from . tutorial_operator import HG_TUTORIAL_OP

hg_classes = (
    #Add-on backbones
    HG_ACTIVATE,
    HG_PREF,
    
    #Props
    HG_SETTINGS,
    HG_OBJECT_PROPS,
    
    #Installation & content packs
    HG_PATHCHANGE,
    HG_CONTENT_PACK,
    HG_UL_CONTENTPACKS,
    HG_REFRESH_CPACKS,
    HG_DELETE_CPACK,
    HG_INSTALL_CPACK,
    HG_INSTALLPACK,
    HG_SELECT_CPACK,
    HG_UL_INSTALLPACKS,
    HG_DELETE_INSTALLPACK,
    
    #Custom content packs
    HG_OT_SAVE_CPACK,
    HG_OT_EDIT_CPACK,
    HG_OT_EXIT_CPACK_EDIT,
    CUSTOM_CONTENT_ITEM,
    HG_OT_CREATE_CPACK,
    
    #Panels
    HG_MAIN_PANEL.HG_PT_PANEL, 
    HG_MAIN_PANEL.HG_ROT_LOC_SCALE,
        #utility
    HG_UTILITY_PANEL.HG_PT_UTILITY,
    HG_UTILITY_PANEL.HG_PT_T_BAKE,
    HG_UTILITY_PANEL.HG_PT_T_MODAPPLY,
    HG_UTILITY_PANEL.HG_PT_T_PRESET,
    HG_UTILITY_PANEL.HG_PT_T_SHAPEKEY,
    HG_UTILITY_PANEL.HG_PT_T_HAIR,
    HG_UTILITY_PANEL.HG_PT_T_CLOTH,
        HG_UTILITY_PANEL.HG_PT_T_CLOTHMAT,
        HG_UTILITY_PANEL.HG_PT_T_MASKS,
        HG_UTILITY_PANEL.HG_PT_T_CLOTHWEIGHT,
        HG_UTILITY_PANEL.HG_PT_T_CLOTHSK,
    HG_UTILITY_PANEL.HG_PT_T_OUTFIT,
    HG_UTILITY_PANEL.HG_PT_T_DEV,
        #uilists for utility
    HG_UTILITY_UILISTS.HG_UL_MODAPPLY,
    HG_UTILITY_UILISTS.MODAPPLY_ITEM,
    HG_UTILITY_UILISTS.HG_UL_SHAPEKEYS,
    HG_UTILITY_UILISTS.SHAPEKEY_ITEM,
    HG_UTILITY_UILISTS.SAVEHAIR_ITEM,
    HG_UTILITY_UILISTS.HG_UL_SAVEHAIR,
    HG_UTILITY_UILISTS.SAVEOUTFIT_ITEM,
    HG_UTILITY_UILISTS.HG_UL_SAVEOUTFIT,
        #batch
    HG_BATCH_PANEL.HG_PT_BATCH_Panel,
    HG_BATCH_PANEL.HG_PT_B_HUMAN,
    HG_BATCH_PANEL.HG_PT_B_QUALITY,
    HG_BATCH_PANEL.HG_PT_B_HAIR,
    HG_BATCH_PANEL.HG_PT_B_POSING,
    HG_BATCH_PANEL.HG_PT_B_CLOTHING,
    HG_BATCH_PANEL.HG_PT_B_EXPRESSION,
        #pref
    HG_ICON_LEGEND,
    #custom ui
    HG_TUTORIAL_OP.HG_DRAW_PANEL,

    #Panel ops
    HG_CLEAR_SEARCH,
    HG_FINISH_CREATION,
    HG_NEXT_PREV_HUMAN,
    HG_RANDOM,
    HG_SECTION_TOGGLE,
    HG_OT_INFO,
    HG_OPENPREF,

    #Model ops
    HG_DELETE,
    HG_DESELECT,   

    #eyes
    HG_EYEBROW_SWITCH,

    #Face
    HG_RESET_FACE,

    #Posing
    HG_RIGIFY,
    
    #Clothing
    HG_BACK_TO_HUMAN,
    HG_OT_PATTERN,
    HG_COLOR_RANDOM,   
    HG_DELETE_CLOTH,

    #Creation
    HG_START_CREATION,
    HG_REVERT_TO_CREATION,

    #Length
    HG_RANDOM_LENGTH,

    #Hair
    HG_TOGGLE_HAIR_CHILDREN,
    HG_REMOVE_HAIR,
    HG_CONVERT_HAIRCARDS,

    #expression
    HG_REMOVE_SHAPEKEY,
    HG_ADD_FRIG,
    HG_REMOVE_FRIG,

    #extras
    HG_MAKE_EXPERIMENTAL,
    HG_BAKE,
    HG_OT_REFRESH_UL,
    HG_OT_MODAPPLY,
    HG_OT_SELECTMODAPPLY,
    HG_OT_SAVEPRESET,
    HG_OT_OPEN_FOLDER,
    HG_OT_SAVE_SHAPEKEY,
    HG_OT_SAVEHAIR,
    HG_OT_SAVEOUTFIT,
    HG_OT_AUTOWEIGHT,
    HG_OT_ADDCORRECTIVE,
    HG_OT_ADDCLOTHMATH,
    HG_OT_ADDMASKS,
    
    #Devtools
    HG_DELETE_STRETCH,
    HG_MASK_PROP,
    HG_TESTOP,
    HG_OT_PREPARE_FOR_ARKIT,
    
    #Update
    UPDATE_INFO_ITEM
    )
