# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Contains the check_update function for online checking for cpack and code updates."""

import bpy



def check_update() -> None:
    """Fill the update flags from the cached catalogue. Never blocks.

    The fetch itself runs in a thread started by `backend.setup.update_check`
    a few seconds after load, at most once a day and only when Blender's
    online access is on.
    """
    from ..setup import update_check

    update_check.apply()


class UPDATE_INFO_ITEM(bpy.types.PropertyGroup):
    """Line item to show what features are included in new update."""

    categ: bpy.props.StringProperty()
    version: bpy.props.IntVectorProperty(default=(0, 0, 0))
    line: bpy.props.StringProperty()
