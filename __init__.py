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
    "version" : (3, 0, 4), #RELEASE update version number
    "location" : "Add-On Sidepanel > HumGen",
    "wiki_url": "http://humgen3d.com",
    "tracker_url": "http://humgen3d.com",
    "warning" : "",
    "category" : ""
}


import os
import sys

import bpy  # type: ignore
import bpy.utils.previews  # type: ignore # Has to be imported like this, otherwise returns error for some users
from bpy.app.handlers import persistent  # type: ignore

from .core.content.HG_CONTENT_PACKS import (
    HG_CONTENT_PACK,
    HG_INSTALLPACK,
    cpacks_refresh,
)
from .core.content.HG_CUSTOM_CONTENT_PACKS import CUSTOM_CONTENT_ITEM
from .core.content.HG_UPDATE import UPDATE_INFO_ITEM, check_update
from .core.settings.HG_PROPS import HG_OBJECT_PROPS, HG_SETTINGS
from .user_interface import HG_BATCH_UILIST, HG_UTILITY_UILISTS
from .user_interface.HG_ADD_PRIMITIVE_MENU import add_hg_primitive_menu
from .user_interface.HG_TIPS_SUGGESTIONS_UI import TIPS_ITEM

if __name__ != "HG3D":
    sys.modules['HG3D'] = sys.modules[__name__]

########### startup procedure #########
@persistent
def HG_start(dummy):
    """Runs the activating class when a file is loaded or blender is opened
    """    
    bpy.ops.HG3D.activate()
    cpacks_refresh(None, bpy.context)
    check_update()

from .core.HG_PCOLL import preview_collections


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
    for root, dir, fns in os.walk(hg_dir):
        for fn in [f for f in fns if f.endswith('.png')]:
            hg_icons.load(os.path.splitext(fn)[0], os.path.join(hg_dir, fn), 'IMAGE')
    preview_collections["hg_icons"] = hg_icons

def _initiate_ui_lists():
    sc = bpy.types.Scene
    
    sc.batch_clothing_col            = bpy.props.CollectionProperty(type = HG_BATCH_UILIST.BATCH_CLOTHING_ITEM)
    sc.batch_clothing_col_index      = bpy.props.IntProperty(name = "Index", default = 0)
    
    sc.batch_expressions_col        = bpy.props.CollectionProperty(type = HG_BATCH_UILIST.BATCH_EXPRESSION_ITEM)
    sc.batch_expressions_col_index  = bpy.props.IntProperty(name = "Index", default = 0)
    
    sc.contentpacks_col         = bpy.props.CollectionProperty(type = HG_CONTENT_PACK)
    sc.contentpacks_col_index   = bpy.props.IntProperty(name = "Index", default = 0)
    
    sc.installpacks_col         = bpy.props.CollectionProperty(type = HG_INSTALLPACK)
    sc.installpacks_col_index   = bpy.props.IntProperty(name = "Index", default = 0)
    
    sc.modapply_col             = bpy.props.CollectionProperty(type = HG_UTILITY_UILISTS.MODAPPLY_ITEM)
    sc.modapply_col_index       = bpy.props.IntProperty(name = "Index", default = 0)
    
    sc.shapekeys_col            = bpy.props.CollectionProperty(type = HG_UTILITY_UILISTS.SHAPEKEY_ITEM)
    sc.shapekeys_col_index      = bpy.props.IntProperty(name = "Index", default = 0)
    
    sc.savehair_col             = bpy.props.CollectionProperty(type = HG_UTILITY_UILISTS.SAVEHAIR_ITEM)
    sc.savehair_col_index       = bpy.props.IntProperty(name = "Index", default = 0)
    
    sc.saveoutfit_col           = bpy.props.CollectionProperty(type = HG_UTILITY_UILISTS.SAVEOUTFIT_ITEM)
    sc.saveoutfit_col_index     = bpy.props.IntProperty(name = "Index", default = 0)
    
    sc.custom_content_col       = bpy.props.CollectionProperty(type = CUSTOM_CONTENT_ITEM)
    sc.custom_content_col_index = bpy.props.IntProperty(name = "Index", default = 0)
    
    sc.hg_update_col            = bpy.props.CollectionProperty(type = UPDATE_INFO_ITEM)
    sc.hg_update_col_index      = bpy.props.IntProperty(name = "Index", default = 0)
    
    sc.hg_tips_and_suggestions       = bpy.props.CollectionProperty(type = TIPS_ITEM)
    sc.hg_tips_and_suggestions_index = bpy.props.IntProperty(name = "Index", default = 0)            

from .HG_CLASSES import hg_classes


def register():
    #RELEASE remove print statements
    for cls in hg_classes:    
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.HG3D = bpy.props.PointerProperty(type=HG_SETTINGS) #Main props
    bpy.types.Object.HG = bpy.props.PointerProperty(type=HG_OBJECT_PROPS) #Object specific props

    _initiate_preview_collections()
    _initiate_custom_icons()
    _initiate_ui_lists()  

    bpy.types.VIEW3D_MT_add.append(add_hg_primitive_menu)

    #load handler
    if not HG_start in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(HG_start)

def unregister():
    for cls in hg_classes:
        bpy.utils.unregister_class(cls)
    
    #remove handler
    if HG_start in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(HG_start)

    bpy.types.VIEW3D_MT_add.remove(add_hg_primitive_menu)

    #remove pcolls
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()

if __name__ == "__main__":
    register()
