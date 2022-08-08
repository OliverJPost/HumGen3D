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
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

bl_info = {
    "name": "Human Generator 3D",
    "author": "OliverJPost",
    "description": "Human Generator allows you to generate humans including clothing, poses and emotions",
    "blender": (2, 93, 0),
    "version": (4, 0, 0),  # RELEASE update version number
    "location": "Add-On Sidepanel > HumGen",
    "wiki_url": "https://humgen3d.com",
    "tracker_url": "https://humgen3d.com",
    "warning": "",
    "category": "",
}


import os
import sys

import bpy  # type: ignore

# Has to be imported like this, otherwise returns error for some users
import bpy.utils.previews  # type: ignore
from bpy.app.handlers import persistent as _persistent  # type: ignore

from HumGen3D.backend.content_packs.content_packs import (
    cpacks_refresh as _cpacks_refresh,
)

from .backend.auto_classes import _get_bpy_classes
from .backend.preview_collections import preview_collections as _preview_collections
from .backend.properties.object_props import HG_OBJECT_PROPS
from .backend.properties.scene_main_properties import HG_SETTINGS
from .backend.update import check_update as _check_update
from .human.human import Human

if __name__ != "HG3D":
    sys.modules["HG3D"] = sys.modules[__name__]


# Startup procedure
@_persistent
def HG_start(dummy):
    """Runs the activating class when a file is loaded or blender is opened"""
    bpy.ops.HG3D.activate()
    _cpacks_refresh(None, bpy.context)
    _check_update()


def _initiate_preview_collections():
    # Initiate preview collections
    pcoll_names = [
        "humans",
        "poses",
        "outfits",
        "footwear",
        "hair",
        "face_hair",
        "expressions",
        "patterns",
        "textures",
    ]

    for pcoll_name in pcoll_names:
        _preview_collections.setdefault(pcoll_name, bpy.utils.previews.new())


def _initiate_custom_icons():
    """Load custom icons"""
    hg_icons = _preview_collections.setdefault("hg_icons", bpy.utils.previews.new())
    icon_dir = os.path.join(os.path.dirname(__file__), "user_interface", "icons")
    for _, _, fns in os.walk(icon_dir):
        png_files = [f for f in fns if f.endswith(".png")]
        for fn in png_files:
            fn_base = os.path.splitext(fn)[0]
            full_path = os.path.join(icon_dir, fn)
            hg_icons.load(fn_base, full_path, "IMAGE")
    _preview_collections["hg_icons"] = hg_icons


def _initiate_ui_lists():
    # Import in local namespace to prevent cluttering package namespace
    from HumGen3D.backend import update
    from HumGen3D.backend.content_packs import content_packs, custom_content_packs
    from HumGen3D.user_interface import (
        batch_ui_lists,
        tips_suggestions_ui,
        utility_ui_lists,
    )

    collections = {
        "batch_clothing_col": batch_ui_lists.BATCH_CLOTHING_ITEM,
        "batch_expressions_col": batch_ui_lists.BATCH_EXPRESSION_ITEM,
        "contentpacks_col": content_packs.HG_CONTENT_PACK,
        "installpacks_col": content_packs.HG_INSTALLPACK,
        "modapply_col": utility_ui_lists.MODAPPLY_ITEM,
        "shapekeys_col": utility_ui_lists.SHAPEKEY_ITEM,
        "savehair_col": utility_ui_lists.SAVEHAIR_ITEM,
        "saveoutfit_col": utility_ui_lists.SAVEOUTFIT_ITEM,
        "custom_content_col": custom_content_packs.CUSTOM_CONTENT_ITEM,
        "hg_update_col": update.UPDATE_INFO_ITEM,
        "hg_tips_and_suggestions": tips_suggestions_ui.TIPS_ITEM,
    }

    scene = bpy.types.Scene
    for coll_name, coll_class in collections.items():
        coll_prop = bpy.props.CollectionProperty(type=coll_class)
        setattr(scene, coll_name, coll_prop)
        index = bpy.props.IntProperty(name="Index", default=0)
        setattr(scene, f"{coll_name}_index", index)


hg_classes = _get_bpy_classes()


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

    from .user_interface.primitive_menu import add_hg_primitive_menu

    bpy.types.VIEW3D_MT_add.append(add_hg_primitive_menu)

    # load handler
    if not HG_start in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(HG_start)


def unregister():
    # from .classes import hg_classes

    for cls in hg_classes:
        bpy.utils.unregister_class(cls)

    # remove handler
    if HG_start in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(HG_start)

    from .user_interface.primitive_menu import add_hg_primitive_menu

    bpy.types.VIEW3D_MT_add.remove(add_hg_primitive_menu)

    # remove pcolls
    for pcoll in _preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    _preview_collections.clear()


if __name__ == "__main__":
    register()
