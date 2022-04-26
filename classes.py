# Core
from .backend.callback import HG_ACTIVATE
from .backend.preferences import HG_PATHCHANGE, HG_PREF, HG_PT_ICON_LEGEND
from .backend.properties import HG_OBJECT_PROPS, HG_SETTINGS
from .backend.update import UPDATE_INFO_ITEM
from .human.base.operator import HG_RANDOM
from .human.creation_phase.operators import HG_START_CREATION
from .old.blender_backend.content.content_packs import (
    HG_CONTENT_PACK,
    HG_DELETE_CPACK,
    HG_DELETE_INSTALLPACK,
    HG_INSTALL_CPACK,
    HG_INSTALLPACK,
    HG_REFRESH_CPACKS,
    HG_SELECT_CPACK,
    HG_UL_CONTENTPACKS,
    HG_UL_INSTALLPACKS,
)
from .old.blender_backend.content.custom_content_packs import (
    CUSTOM_CONTENT_ITEM,
    HG_OT_CREATE_CPACK,
    HG_OT_EDIT_CPACK,
    HG_OT_EXIT_CPACK_EDIT,
    HG_OT_SAVE_CPACK,
)
from .old.blender_operators.batch_section.modal import HG_BATCH_GENERATE
from .old.blender_operators.batch_section.primitives import (
    HG_OT_ADD_BATCH_MARKER,
)
from .old.blender_operators.batch_section.quick_generator import (
    HG_QUICK_GENERATE,
)
from .old.blender_operators.common.common_operators import (
    HG_CLEAR_SEARCH,
    HG_DELETE,
    HG_DESELECT,
    HG_NEXT_PREV_HUMAN,
    HG_NEXTPREV_CONTENT_SAVING_TAB,
    HG_OPENPREF,
    HG_SECTION_TOGGLE,
)
from .old.blender_operators.common.info_popups import HG_OT_INFO
from .old.blender_operators.common.random import HG_COLOR_RANDOM
from .old.blender_operators.creation_phase.backup import HG_REVERT_TO_CREATION
from .old.blender_operators.creation_phase.face import HG_RESET_FACE
from .old.blender_operators.creation_phase.finish_creation_phase import (
    HG_FINISH_CREATION,
)
from .old.blender_operators.creation_phase.hair import (
    HG_EYEBROW_SWITCH,
    HG_REMOVE_HAIR,
    HG_TOGGLE_HAIR_CHILDREN,
)
from .old.blender_operators.creation_phase.haircards import (
    HG_CONVERT_HAIRCARDS,
)
from .old.blender_operators.creation_phase.length import HG_RANDOM_LENGTH

# Tutorial operator
from .old.blender_operators.documentation.tutorial_operator import (
    tutorial_operator,
)
from .old.blender_operators.finalize_phase.clothing import (
    HG_BACK_TO_HUMAN,
    HG_DELETE_CLOTH,
    HG_OT_PATTERN,
)
from .old.blender_operators.finalize_phase.expression import (
    HG_ADD_FRIG,
    HG_REMOVE_FRIG,
    HG_REMOVE_SHAPEKEY,
)
from .old.blender_operators.finalize_phase.pose import HG_RIGIFY
from .old.blender_operators.utility_section.baking import HG_BAKE
from .old.blender_operators.utility_section.content_saving import (
    HG_OT_AUTO_RENDER_THUMB,
    HG_OT_OPEN_FOLDER,
    HG_OT_SAVE_POSE,
    HG_OT_SAVE_SHAPEKEY,
    HG_OT_SAVEHAIR,
    HG_OT_SAVEOUTFIT,
    HG_OT_SAVEPRESET,
)
from .old.blender_operators.utility_section.devtools import (
    HG_CONVERT_HAIR_SHADER,
    HG_DELETE_STRETCH,
    HG_MASK_PROP,
    HG_RESET_BATCH_OPERATOR,
    HG_TESTOP,
)
from .old.blender_operators.utility_section.mesh_to_cloth import (
    HG_MTC_TO_A_POSE,
    HG_OT_ADDCLOTHMATH,
    HG_OT_ADDCORRECTIVE,
    HG_OT_ADDMASKS,
    HG_OT_AUTOWEIGHT,
)
from .old.blender_operators.utility_section.utility_operators import (
    HG_MAKE_EXPERIMENTAL,
    HG_OT_MODAPPLY,
    HG_OT_PREPARE_FOR_ARKIT,
    HG_OT_REFRESH_UL,
    HG_OT_SELECTMODAPPLY,
)
from .tests.api import HG_API_TESTS
from .tests.batch import HG_BATCH_TESTS
from .tests.content import HG_CONTENT_TESTS
from .tests.main_operators import HG_MAIN_OPERATORS_TESTS
from .tests.utility import HG_UTILITY_TESTS

# User interface
from .user_interface import (
    batch_panel,
    batch_ui_lists,
    main_panel,
    utility_panel,
    utility_ui_lists,
)
from .user_interface.content_saving_panel import (
    HG_OT_CANCEL_CONTENT_SAVING_UI,
    HG_OT_OPEN_CONTENT_SAVING_TAB,
    HG_PT_CONTENT_SAVING,
)
from .user_interface.primitive_menu import VIEW3D_MT_HG_Marker_Add
from .user_interface.tips_suggestions_ui import (
    HG_OT_HIDE_TIP,
    HG_OT_UNHIDE_TIP,
    TIPS_ITEM,
)

hg_classes = (
    # Add-on backbones
    HG_ACTIVATE,
    HG_PREF,
    # Props
    HG_SETTINGS,
    HG_OBJECT_PROPS,
    # Installation & content packs
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
    # Custom content packs
    HG_OT_SAVE_CPACK,
    HG_OT_EDIT_CPACK,
    HG_OT_EXIT_CPACK_EDIT,
    CUSTOM_CONTENT_ITEM,
    HG_OT_CREATE_CPACK,
    # Panels
    main_panel.HG_PT_PANEL,
    main_panel.HG_PT_ROT_LOC_SCALE,
    # Utility
    utility_panel.HG_PT_UTILITY,
    utility_panel.HG_PT_T_BAKE,
    utility_panel.HG_PT_T_MODAPPLY,
    utility_panel.HG_PT_T_CLOTH,
    utility_panel.HG_PT_T_DEV,
    # Uilists for utility
    utility_ui_lists.HG_UL_MODAPPLY,
    utility_ui_lists.MODAPPLY_ITEM,
    utility_ui_lists.HG_UL_SHAPEKEYS,
    utility_ui_lists.SHAPEKEY_ITEM,
    utility_ui_lists.SAVEHAIR_ITEM,
    utility_ui_lists.HG_UL_SAVEHAIR,
    utility_ui_lists.SAVEOUTFIT_ITEM,
    utility_ui_lists.HG_UL_SAVEOUTFIT,
    # Batch
    batch_panel.HG_PT_BATCH_Panel,
    batch_panel.HG_PT_B_GENERATION_PROBABILITY,
    batch_panel.HG_PT_B_HEIGHT_VARIATION,
    batch_panel.HG_PT_B_HAIR,
    batch_panel.HG_PT_B_CLOTHING,
    batch_panel.HG_PT_B_EXPRESSION,
    batch_panel.HG_PT_B_QUALITY,
    batch_panel.HG_PT_B_BAKING,
    # Batch uilists
    batch_ui_lists.HG_UL_BATCH_CLOTHING,
    batch_ui_lists.HG_UL_BATCH_EXPRESSIONS,
    batch_ui_lists.BATCH_CLOTHING_ITEM,
    batch_ui_lists.BATCH_EXPRESSION_ITEM,
    batch_ui_lists.HG_REFRESH_UILISTS,
    # Pref
    HG_PT_ICON_LEGEND,
    # Custom ui
    tutorial_operator.HG_DRAW_PANEL,
    # Panel ops
    HG_CLEAR_SEARCH,
    HG_FINISH_CREATION,
    HG_NEXT_PREV_HUMAN,
    HG_RANDOM,
    HG_SECTION_TOGGLE,
    HG_OT_INFO,
    HG_OPENPREF,
    # Model ops
    HG_DELETE,
    HG_DESELECT,
    # Eyes
    HG_EYEBROW_SWITCH,
    # Face
    HG_RESET_FACE,
    # Posing
    HG_RIGIFY,
    # Clothing
    HG_BACK_TO_HUMAN,
    HG_OT_PATTERN,
    HG_COLOR_RANDOM,
    HG_DELETE_CLOTH,
    # Creation
    HG_START_CREATION,
    HG_REVERT_TO_CREATION,
    # Length
    HG_RANDOM_LENGTH,
    # Hair
    HG_TOGGLE_HAIR_CHILDREN,
    HG_REMOVE_HAIR,
    HG_CONVERT_HAIRCARDS,
    # Expression
    HG_REMOVE_SHAPEKEY,
    HG_ADD_FRIG,
    HG_REMOVE_FRIG,
    # Extras
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
    # Devtools
    HG_DELETE_STRETCH,
    HG_MASK_PROP,
    HG_TESTOP,
    HG_CONVERT_HAIR_SHADER,
    HG_OT_PREPARE_FOR_ARKIT,
    # Update
    UPDATE_INFO_ITEM,
    # Batch
    HG_BATCH_GENERATE,
    HG_QUICK_GENERATE,
    VIEW3D_MT_HG_Marker_Add,
    HG_OT_ADD_BATCH_MARKER,
    HG_RESET_BATCH_OPERATOR,
    # New content saving
    HG_OT_CANCEL_CONTENT_SAVING_UI,
    HG_PT_CONTENT_SAVING,
    HG_OT_AUTO_RENDER_THUMB,
    HG_NEXTPREV_CONTENT_SAVING_TAB,
    HG_OT_OPEN_CONTENT_SAVING_TAB,
    utility_panel.HG_PT_CUSTOM_CONTENT,
    HG_OT_SAVE_POSE,
    HG_MTC_TO_A_POSE,
    # TIPS and suggestions
    TIPS_ITEM,
    batch_panel.HG_PT_BATCH_TIPS,
    utility_panel.HG_PT_EXTRAS_TIPS,
    HG_OT_HIDE_TIP,
    HG_OT_UNHIDE_TIP,
    # Tests
    HG_CONTENT_TESTS,
    HG_MAIN_OPERATORS_TESTS,
    HG_BATCH_TESTS,
    HG_UTILITY_TESTS,
    HG_API_TESTS,
)
