# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import os

import bpy
from bpy.types import Operator  # type:ignore
from bpy_extras.io_utils import ImportHelper  # type:ignore
from ...backend import get_prefs


def refresh_content_folder(context) -> None:
    """After the content folder changed or came back: forget what was cached
    about it, reread the packs, the update status and the previews."""
    from ..content import content_state
    from ..content.content_packs import cpacks_refresh
    from ..setup import update_check
    from ..setup.migration import folder_has_content

    content_state.clear()
    try:
        cpacks_refresh(None, context)
    except Exception as e:  # noqa: BLE001
        print("HumGen: could not read the content packs:", repr(e))
    update_check.apply()
    if folder_has_content(get_prefs().filepath):
        bpy.ops.hg3d.activate()


class HG_PATHCHANGE(Operator, ImportHelper):
    """Changes the path via file browser popup."""

    bl_idname = "hg3d.pathchange"
    bl_label = "Change Path"
    bl_description = "Change the install path"

    def execute(self, context):
        from ..setup import user_settings

        pref = get_prefs()

        folder = os.path.join(os.path.dirname(self.filepath), "")  # use join to get slash at the end
        pref.filepath = folder
        # Every Blender version and both package names find it there
        user_settings.update(content_folder=folder)
        refresh_content_folder(context)

        bpy.ops.wm.save_userpref()
        return {"FINISHED"}


class HG_OT_CONTENT_FOLDER_RETRY(Operator):
    """Look for the content folder again, after connecting its drive"""

    bl_idname = "hg3d.content_folder_retry"
    bl_label = "Try again"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        from ..setup.migration import resolve_content_folder

        resolve_content_folder()
        refresh_content_folder(context)
        return {"FINISHED"}
