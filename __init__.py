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

# flake8: noqa E402

bl_info = {
    "name": "Human Generator 3D",
    "author": "OliverJPost",
    "description": "Human Generator allows you to generate humans including clothing, poses and emotions",  # noqa
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
from typing import Any

import bpy  # type: ignore

# Has to be imported like this, otherwise returns error for some users
import bpy.utils.previews  # type: ignore
from bpy.app.handlers import persistent as _persistent  # type: ignore

from HumGen3D.human.base.exceptions import HumGenException
from HumGen3D.human.keys.keys import KeyItem, LiveKeyItem, ShapeKeyItem

from .backend.auto_classes import _get_bpy_classes
from .backend.content_packs.content_packs import cpacks_refresh as _cpacks_refresh
from .backend.preferences.preference_func import get_prefs
from .backend.preview_collections import PREVIEW_COLLECTION_DATA, PreviewCollection
from .backend.preview_collections import preview_collections as _preview_collections
from .backend.properties.object_props import HG_OBJECT_PROPS
from .backend.update import check_update as _check_update
from .backend.vscode_reload import _post_vscode_reload  # noqa
from .batch_generator.generator import BatchHumanGenerator
from .human.human import Human
from .human.keys.bpy_livekey import BpyLiveKey
from .user_interface.batch_panel import batch_ui_lists
from .user_interface.content_panel import utility_ui_lists
from .user_interface.icons.icons import hg_icons

__all__ = [
    "Human",
    "BatchHumanGenerator",
    "HumGenException",
    "LiveKeyItem",
    "ShapeKeyItem",
    "KeyItem",
    "get_prefs",
]


if __name__ != "HG3D":  # FIXME
    sys.modules["HG3D"] = sys.modules[__name__]


# Startup procedure
@_persistent
def HG_start(dummy: Any) -> None:
    """Runs the activating class when a file is loaded or blender is opened"""
    bpy.ops.HG3D.activate()
    _cpacks_refresh(None, bpy.context)
    _check_update()


def _initiate_preview_collections() -> None:
    # Initiate preview collections
    for pcoll_name in PREVIEW_COLLECTION_DATA:
        _preview_collections[pcoll_name] = PreviewCollection(
            pcoll_name, bpy.utils.previews.new()
        )


def _initiate_custom_icons() -> None:
    """Load custom icons"""

    hg_icons.append(bpy.utils.previews.new())

    icon_dir = os.path.join(os.path.dirname(__file__), "user_interface", "icons")
    for root, _, fns in os.walk(icon_dir):
        png_files = [f for f in fns if f.endswith(".png")]
        for fn in png_files:
            fn_base = os.path.splitext(fn)[0]
            full_path = os.path.join(root, fn)
            hg_icons[0].load(fn_base, full_path, "IMAGE")


def _initiate_ui_lists() -> None:
    # Import in local namespace to prevent cluttering package namespace
    from HumGen3D.backend import update
    from HumGen3D.backend.content_packs import content_packs, custom_content_packs
    from HumGen3D.user_interface.documentation import tips_suggestions_ui

    from .custom_content.possible_content import POSSIBLE_CONTENT_ITEM

    collections = {
        "batch_clothing_col": batch_ui_lists.BATCH_CLOTHING_ITEM,
        "contentpacks_col": content_packs.HG_CONTENT_PACK,
        "installpacks_col": content_packs.HG_INSTALLPACK,
        "modapply_col": utility_ui_lists.MODAPPLY_ITEM,
        "shapekeys_col": utility_ui_lists.SHAPEKEY_ITEM,
        "savehair_col": utility_ui_lists.SAVEHAIR_ITEM,
        "saveoutfit_col": utility_ui_lists.SAVEOUTFIT_ITEM,
        "custom_content_col": custom_content_packs.CUSTOM_CONTENT_ITEM,
        "hg_update_col": update.UPDATE_INFO_ITEM,
        "hg_tips_and_suggestions": tips_suggestions_ui.TIPS_ITEM,
        "possible_content_col": POSSIBLE_CONTENT_ITEM,
    }

    scene = bpy.types.Scene
    for coll_name, coll_class in collections.items():
        coll_prop = bpy.props.CollectionProperty(type=coll_class)  # type:ignore
        setattr(scene, coll_name, coll_prop)
        index = bpy.props.IntProperty(name="Index", default=0)  # type:ignore
        setattr(scene, f"{coll_name}_index", index)


hg_classes = _get_bpy_classes()


def register() -> None:
    _initiate_custom_icons()

    # RELEASE remove print statements
    for cls in hg_classes:
        bpy.utils.register_class(cls)

    # Main props
    from .backend.properties.scene_main_properties import HG_SETTINGS

    bpy.types.Scene.HG3D = bpy.props.PointerProperty(type=HG_SETTINGS)  # type:ignore
    # Object specific props
    bpy.types.Object.HG = bpy.props.PointerProperty(type=HG_OBJECT_PROPS)  # type:ignore

    _initiate_preview_collections()
    _initiate_ui_lists()

    from .user_interface.batch_panel.primitive_menu import add_hg_primitive_menu

    bpy.types.VIEW3D_MT_add.append(add_hg_primitive_menu)

    livekeys_coll = bpy.props.CollectionProperty(type=BpyLiveKey)  # type:ignore
    bpy.types.WindowManager.livekeys = livekeys_coll

    # load handler
    if HG_start not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(HG_start)


def unregister() -> None:
    # from .classes import hg_classes

    for cls in hg_classes:
        bpy.utils.unregister_class(cls)

    # remove handler
    if HG_start in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(HG_start)

    from .user_interface.batch_panel.primitive_menu import add_hg_primitive_menu

    bpy.types.VIEW3D_MT_add.remove(add_hg_primitive_menu)

    # remove pcolls
    for pcoll_item in _preview_collections.values():
        bpy.utils.previews.remove(pcoll_item.pcoll)
    bpy.utils.previews.remove(hg_icons.pop())

    _preview_collections.clear()


if __name__ == "__main__":
    register()
