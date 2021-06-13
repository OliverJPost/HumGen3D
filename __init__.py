'''
    Created by Oliver J Post & Alexander Lashko

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

bl_info = {
    "name" : "Human Generator 3D",
    "author" : "OliverJPost",
    "description" : "Human Generator allows you to generate humans including clothing, poses and emotions",
    "blender" : (2, 83, 0),
    "version" : (2, 0, 4), #RELEASE update version number
    "location" : "Add-On Sidepanel > HumGen",
    "wiki_url": "http://humgen3d.com",
    "tracker_url": "http://humgen3d.com",
    "warning" : "",
    "category" : ""
}

import bpy #type: ignore
import sys, os
from bpy.utils import previews #type: ignore
from bpy.app.handlers import persistent #type: ignore

if __name__ != "HG3D":
    sys.modules['HG3D'] = sys.modules[__name__]

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
from . core.content.HG_UPDATE import check_update
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
from . features.creation_phase.HG_CREATION import (
    HG_REVERT_TO_CREATION,
    HG_START_CREATION)
from . features.creation_phase.HG_FACE import HG_RESET_FACE
from . features.creation_phase.HG_HAIR import (
    HG_EYEBROW_SWITCH,
    HG_REMOVE_HAIR,
    HG_TOGGLE_HAIR_CHILDREN)
from . features.creation_phase.HG_HAIRCARDS import HG_CONVERT_HAIRCARDS
from . features.creation_phase.HG_LENGTH import (
    HG_RANDOM_LENGTH,
    HG_UPDATE_LENGTH)
from . features.creation_phase.HG_NEXTPHASE import HG_FINISH_CREATION
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
    HG_OT_AUTOWEIGHT,
    HG_OT_ADDCLOTHMATH,
    HG_OT_ADDCORRECTIVE,
    HG_OT_MODAPPLY,
    HG_OT_OPEN_FOLDER,
    HG_OT_SAVE_SHAPEKEY,
    HG_OT_SAVEHAIR,
    HG_OT_SAVEPRESET,
    HG_OT_REFRESH_UL,
    HG_OT_SELECTMODAPPLY,
    HG_OT_SAVEOUTFIT,
    HG_SHAPEKEY_CALCULATOR)
#user interface
from . user_interface import (
    HG_MAIN_PANEL,
    HG_UTILITY_PANEL,
    HG_BATCH_PANEL,
    HG_UTILITY_UILISTS)
#tutorial operator
from . tutorial_operator import HG_TUTORIAL_OP

# from . HG_NEXTPHASE import HG_FINISH_CREATION
# from . HG_PREFERENCES import (
#     HG_PREFERENCES,
#     HG_PATHCHANGE,
#     HG_ICON_LEGEND)
# from . HG_CALLBACK import HG_ACTIVATE
# from . HG_PROPS import (
#     HG_SETTINGS,
#     HG_OBJECT_PROPS)
# from . user_interface import (
#     HG_MAIN_PANEL,
#     HG_UTILITY_PANEL,
#     HG_BATCH_PANEL,
#     HG_UTILITY_UILISTS)
# from . HG_CREATION import (
#     HG_START_CREATION,
#     HG_REVERT_TO_CREATION)
# from . HG_LENGTH import (
#     HG_UPDATE_LENGTH,
#     HG_RANDOM_LENGTH)
# from . HG_POSE import HG_RIGIFY
# from . HG_COMMON_OPS import (
#     HG_DESELECT,
#     HG_NEXT_PREV_HUMAN,
#     HG_SECTION_TOGGLE,
#     HG_DELETE,
#     HG_CLEAR_SEARCH,
#     HG_OPENPREF)
# from . HG_RANDOM import (
#     HG_RANDOM,
#     HG_COLOR_RANDOM
#     )
# from . HG_CLOTHING import (
#     HG_BACK_TO_HUMAN,
#     HG_OT_PATTERN,
#     HG_DELETE_CLOTH)
# from . HG_HAIR import (
#     HG_TOGGLE_HAIR_CHILDREN,
#     HG_REMOVE_HAIR,
#     HG_EYEBROW_SWITCH)
# from . HG_INFO_POPUPS import HG_OT_INFO
# from . tutorial_operator import HG_TUTORIAL_OP
# from . HG_EXPRESSION import (
#     HG_REMOVE_SHAPEKEY,
#     HG_ADD_FRIG, HG_REMOVE_FRIG)
# from . HG_DEVTOOLS import (
#     HG_SHAPEKEY_CALCULATOR,
#     HG_CHECK_DISTANCE,
#     HG_DELETE_EMPTIES,
#     HG_PURGE_FILE,
#     HG_CREATOR_MODEL,
#     HG_DELETE_STRETCH,
#     HG_MAKE_HAIR_JSON,
#     HG_MASK_PROP,
#     HG_RENDER_THUMBS,
#     HG_CLOTH_CALCULATOR,
#     HG_TESTOP)
# from . HG_CONTENT_PACKS import (
#     HG_CONTENT_PACK,
#     HG_UL_CONTENTPACKS,
#     HG_REFRESH_CPACKS,
#     HG_DELETE_CPACK,
#     HG_INSTALL_CPACK,
#     HG_INSTALLPACK,
#     HG_SELECT_CPACK,
#     HG_UL_INSTALLPACKS,
#     HG_DELETE_INSTALLPACK,
#     cpacks_refresh)
# from . HG_FACE import HG_RESET_FACE
# from . HG_UTILITY_OPS import (
#     HG_MAKE_EXPERIMENTAL,
#     HG_OT_REFRESH_UL,
#     HG_OT_MODAPPLY,
#     HG_OT_SELECTMODAPPLY,
#     HG_OT_SAVEPRESET,
#     HG_OT_OPEN_FOLDER,
#     HG_OT_SAVE_SHAPEKEY,
#     HG_OT_SAVEHAIR,
#     HG_OT_SAVEOUTFIT,
#     HG_OT_AUTOWEIGHT,
#     HG_OT_ADDCORRECTIVE,
#     HG_OT_ADDCLOTHMATH)
# from . HG_HAIRCARDS import HG_CONVERT_HAIRCARDS
# from . features.utility_section.HG_BAKE import HG_BAKE
# from . HG_UPDATE import check_update

print(HG_PREF)

classes = (
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
    HG_UTILITY_PANEL.HG_PT_T_OUTFIT,
    HG_UTILITY_PANEL.HG_PT_T_CLOTH,
        HG_UTILITY_PANEL.HG_PT_T_CLOTHMAT,
        HG_UTILITY_PANEL.HG_PT_T_MASKS,
        HG_UTILITY_PANEL.HG_PT_T_CLOTHWEIGHT,
        HG_UTILITY_PANEL.HG_PT_T_CLOTHSK,
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
    HG_UPDATE_LENGTH,
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
    
    #Devtools
    HG_SHAPEKEY_CALCULATOR,
    HG_CHECK_DISTANCE,
    HG_DELETE_EMPTIES,
    HG_PURGE_FILE,
    HG_CREATOR_MODEL,
    HG_DELETE_STRETCH,
    HG_MAKE_HAIR_JSON,
    HG_MASK_PROP,
    HG_RENDER_THUMBS,
    HG_CLOTH_CALCULATOR,
    HG_TESTOP
    )

########### startup procedure #########
@persistent
def HG_start(dummy):
    """Runs the activating class when a file is loaded or blender is opened
    """    
    bpy.ops.HG3D.activate()
    cpacks_refresh(None, bpy.context)
    check_update()

from . core.HG_PCOLL import  preview_collections

def _initiate_preview_collections():
    #initiate preview collections
    pcoll_names = [
    'humans',
    'poses',
    'outfit',
    'footwear',
    'hair',
    'face_hair',
    'expressions',
    'patterns',
    'textures'
    ]
    
    for pcoll_name in pcoll_names:
        preview_collections.setdefault(
            f"pcoll_{pcoll_name}",
            bpy.utils.previews.new()
            )
def _initiate_custom_icons():
    #load custom icons
    hg_icons = preview_collections.setdefault("hg_icons", bpy.utils.previews.new())
    hg_dir = os.path.join(os.path.dirname(__file__), 'icons') 
    icons = [
        'hair',
        'body',
        'face',
        'skin',
        'clothing',
        'footwear',
        'expression',
        'finalize',
        'simulation',
        'pose',
        'length',
        'cold',
        'warm',
        'normal',
        'inside',
        'outside',
        'male_true', 
        'male_false',
        'female_true',
        'female_false',
        'HG_icon',
        'humans',
        'textures',
        'eyes'
        ]
    for icon in icons:
        hg_icons.load(icon, os.path.join(hg_dir, icon + '.png'), 'IMAGE')
    preview_collections["hg_icons"] = hg_icons

def _initiate_ui_lists():
    sc = bpy.types.Scene
    # sc.outfits_col_m = bpy.props.CollectionProperty(type = HG_BATCH_UILIST.CLOTHING_ITEM_M) 
    # sc.outfits_col_m_index = bpy.props.IntProperty(name = "Index", default = 0)
    # sc.pose_col = bpy.props.CollectionProperty(type = HG_BATCH_UILIST.POSE_ITEM) 
    # sc.pose_col_index = bpy.props.IntProperty(name = "Index", default = 0)        
    # sc.expressions_col = bpy.props.CollectionProperty(type = HG_BATCH_UILIST.EXPRESSION_ITEM) 
    # sc.expressions_col_index = bpy.props.IntProperty(name = "Index", default = 0)      
    sc.contentpacks_col = bpy.props.CollectionProperty(type = HG_CONTENT_PACK) 
    sc.contentpacks_col_index = bpy.props.IntProperty(name = "Index", default = 0)     
    sc.installpacks_col = bpy.props.CollectionProperty(type = HG_INSTALLPACK) 
    sc.installpacks_col_index = bpy.props.IntProperty(name = "Index", default = 0)    
    sc.modapply_col = bpy.props.CollectionProperty(type = HG_UTILITY_UILISTS.MODAPPLY_ITEM) 
    sc.modapply_col_index = bpy.props.IntProperty(name = "Index", default = 0)     
    sc.shapekeys_col = bpy.props.CollectionProperty(type = HG_UTILITY_UILISTS.SHAPEKEY_ITEM) 
    sc.shapekeys_col_index = bpy.props.IntProperty(name = "Index", default = 0)   
    sc.savehair_col = bpy.props.CollectionProperty(type = HG_UTILITY_UILISTS.SAVEHAIR_ITEM) 
    sc.savehair_col_index = bpy.props.IntProperty(name = "Index", default = 0)  
    sc.saveoutfit_col = bpy.props.CollectionProperty(type = HG_UTILITY_UILISTS.SAVEOUTFIT_ITEM) 
    sc.saveoutfit_col_index = bpy.props.IntProperty(name = "Index", default = 0)

def register():
    #RELEASE remove print statements
    #RELEASE TURN OFF SSS
    for cls in classes:    
        #print('registering', cls)
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.HG3D = bpy.props.PointerProperty(type=HG_SETTINGS) #Main props
    bpy.types.Object.HG = bpy.props.PointerProperty(type=HG_OBJECT_PROPS) #Object specific props

    _initiate_preview_collections()
    _initiate_custom_icons()
    _initiate_ui_lists()  

    #load handler
    if not HG_start in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(HG_start)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    
    #remove handler
    if HG_start in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(HG_start)

    #remove pcolls
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()

if __name__ == "__main__":
    register()