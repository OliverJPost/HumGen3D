"""
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
"""

bl_info = {
    "name": "Human Generator 3D",
    "author": "OliverJPost",
    "description": "Human Generator allows you to generate humans including clothing, poses and emotions",
    "blender": (2, 83, 0),
    "version": (3, 0, 2),  # RELEASE update version number
    "location": "Add-On Sidepanel > HumGen",
    "wiki_url": "http://humgen3d.com",
    "tracker_url": "http://humgen3d.com",
    "warning": "",
    "category": "",
}


import os
import sys

import bpy  # type: ignore

# Has to be imported like this, otherwise returns error for some users
import bpy.utils.previews  # type: ignore
from bpy.app.handlers import persistent  # type: ignore

from .blender_backend.content.content_packs import (
    HG_CONTENT_PACK,
    HG_INSTALLPACK,
    cpacks_refresh,
)
from .blender_backend.content.custom_content_packs import CUSTOM_CONTENT_ITEM
from .blender_backend.content.update import UPDATE_INFO_ITEM, check_update
from .blender_backend.preview_collections import preview_collections
from .blender_backend.settings.properties import HG_OBJECT_PROPS, HG_SETTINGS
from .classes import hg_classes
from .user_interface import batch_ui_lists, utility_ui_lists
from .user_interface.primitive_menu import add_hg_primitive_menu
from .user_interface.tips_suggestions_ui import TIPS_ITEM

if __name__ != "HG3D":
    sys.modules["HG3D"] = sys.modules[__name__]


# Startup procedure
@persistent
def HG_start(dummy):
    """Runs the activating class when a file is loaded or blender is opened"""
    bpy.ops.HG3D.activate()
    cpacks_refresh(None, bpy.context)
    check_update()


def _initiate_preview_collections():
    # Initiate preview collections
    pcoll_names = [
        "humans",
        "poses",
        "outfit",
        "footwear",
        "hair",
        "face_hair",
        "expressions",
        "patterns",
        "textures",
    ]

    for pcoll_name in pcoll_names:
        preview_collections.setdefault(
            f"pcoll_{pcoll_name}", bpy.utils.previews.new()
        )


def _initiate_custom_icons():
    """Load custom icons"""
    hg_icons = preview_collections.setdefault(
        "hg_icons", bpy.utils.previews.new()
    )
    icon_dir = os.path.join(os.path.dirname(__file__), "data", "icons")
    for _, _, fns in os.walk(icon_dir):
        png_files = [f for f in fns if f.endswith(".png")]
        for fn in png_files:
            fn_base = os.path.splitext(fn)[0]
            full_path = os.path.join(icon_dir, fn)
            hg_icons.load(fn_base, full_path, "IMAGE")
    preview_collections["hg_icons"] = hg_icons


def _initiate_ui_lists():
    sc = bpy.types.Scene

    # Collection of batch clothing categories
    sc.batch_clothing_col = bpy.props.CollectionProperty(
        type=batch_ui_lists.BATCH_CLOTHING_ITEM
    )
    sc.batch_clothing_col_index = bpy.props.IntProperty(
        name="Index", default=0
    )

    # Collection of batch expression categories
    sc.batch_expressions_col = bpy.props.CollectionProperty(
        type=batch_ui_lists.BATCH_EXPRESSION_ITEM
    )
    sc.batch_expressions_col_index = bpy.props.IntProperty(
        name="Index", default=0
    )

    # Installed content packs
    sc.contentpacks_col = bpy.props.CollectionProperty(type=HG_CONTENT_PACK)
    sc.contentpacks_col_index = bpy.props.IntProperty(name="Index", default=0)

    # Collection of packs selected by user to be installed
    sc.installpacks_col = bpy.props.CollectionProperty(type=HG_INSTALLPACK)
    sc.installpacks_col_index = bpy.props.IntProperty(name="Index", default=0)

    # Collection of modifiers that are available for ModApply operator
    sc.modapply_col = bpy.props.CollectionProperty(
        type=utility_ui_lists.MODAPPLY_ITEM
    )
    sc.modapply_col_index = bpy.props.IntProperty(name="Index", default=0)

    # Collection of shapekeys that can be saved
    sc.shapekeys_col = bpy.props.CollectionProperty(
        type=utility_ui_lists.SHAPEKEY_ITEM
    )
    sc.shapekeys_col_index = bpy.props.IntProperty(name="Index", default=0)

    # Collection of hairstyles that can be saved
    sc.savehair_col = bpy.props.CollectionProperty(
        type=utility_ui_lists.SAVEHAIR_ITEM
    )
    sc.savehair_col_index = bpy.props.IntProperty(name="Index", default=0)

    # Collection of otufits that can be saved
    sc.saveoutfit_col = bpy.props.CollectionProperty(
        type=utility_ui_lists.SAVEOUTFIT_ITEM
    )
    sc.saveoutfit_col_index = bpy.props.IntProperty(name="Index", default=0)

    # Collection of all custom content that can be selected in the content pack
    # export screen
    sc.custom_content_col = bpy.props.CollectionProperty(
        type=CUSTOM_CONTENT_ITEM
    )
    sc.custom_content_col_index = bpy.props.IntProperty(
        name="Index", default=0
    )

    # Collection of items that were changed in the active content pack of the
    # content pack export screen
    sc.hg_update_col = bpy.props.CollectionProperty(type=UPDATE_INFO_ITEM)
    sc.hg_update_col_index = bpy.props.IntProperty(name="Index", default=0)

    # Collection of tips and suggestions to show to the user
    sc.hg_tips_and_suggestions = bpy.props.CollectionProperty(type=TIPS_ITEM)
    sc.hg_tips_and_suggestions_index = bpy.props.IntProperty(
        name="Index", default=0
    )


def register():
    # RELEASE remove print statements
    for cls in hg_classes:
        bpy.utils.register_class(cls)

    # Main props
    bpy.types.Scene.HG3D = bpy.props.PointerProperty(type=HG_SETTINGS)
    # Object specific props
    bpy.types.Object.HG = bpy.props.PointerProperty(type=HG_OBJECT_PROPS)

    _initiate_preview_collections()
    _initiate_custom_icons()
    _initiate_ui_lists()

    bpy.types.VIEW3D_MT_add.append(add_hg_primitive_menu)

    # load handler
    if not HG_start in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(HG_start)


def unregister():
    for cls in hg_classes:
        bpy.utils.unregister_class(cls)

    # remove handler
    if HG_start in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(HG_start)

    bpy.types.VIEW3D_MT_add.remove(add_hg_primitive_menu)

    # remove pcolls
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()


if __name__ == "__main__":
    register()
