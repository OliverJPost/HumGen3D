"""
Contains functions that get used a lot by other operators
"""

import os
import time
from pathlib import Path

import bpy  # type: ignore


# MODULE
def find_human(obj, include_applied_batch_results=False) -> bpy.types.Object:
    """Checks if the passed object is part of a HumGen human

    This makes sure the add-on works as expected, even if a child object of the
    rig is selected.

    Args:
        obj (bpy.types.Object): Object to check for if it's part of a HG human
        include_applied_batch_results (bool): If enabled, this function will
            return the body object for humans that were created with the batch
            system and which armatures have been deleted instead of returning
            the rig. Defaults to False

    Returns:
        Object: Armature of human (hg_rig) or None if not part of human (or body object
        if the human is an applied batch result and include_applied_batch_results
        is True)
    """
    if not obj:
        return None
    elif not obj.HG.ishuman:
        if obj.parent:
            if obj.parent.HG.ishuman:
                return obj.parent
        else:
            return None
    else:
        if all(is_batch_result(obj)):
            if include_applied_batch_results:
                return obj
            else:
                return None

        return obj


def is_batch_result(obj) -> "tuple[bool, bool]":
    return obj.HG.batch_result, obj.HG.body_obj == obj


# def toggle_hair_visibility(obj, show=True):
#     for mod in obj.modifiers:
#         if mod.type == "PARTICLE_SYSTEM":
#             mod.show_viewport = show


# def unhide_human(obj):
#     """Makes sure the rig is visible. If not visible it might cause problems

#     Args:
#         obj (Object): object to unhide
#     """
#     obj.hide_viewport = False
#     obj.hide_set(False)
