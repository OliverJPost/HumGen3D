# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Finding the content of an earlier install, and tidying after a new one.

Where the content folder can come from, in order: the add-on preferences of
this Blender (the normal case), the settings file (another Blender version or
the other package name), the preferences of the legacy `HumGen3D` package
when this copy runs as an extension next to it. Whichever is found is written
to the other places, so the next lookup is the easy one.
"""
import os
import platform
from typing import Optional

import bpy

from ...package import PUBLIC_NAME, is_extension
from . import downloader, user_settings
from .catalogue import BASE_KEY, TRIAL_KEY, has_humans, installed_packs


def default_folder() -> str:
    """A fixed per-OS folder outside Blender's versioned user folders."""
    system = platform.system()
    if system == "Darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif system == "Windows":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return os.path.join(base, "HumGen3D", "Content")


def _prefs():
    from ..preferences.preference_func import get_prefs

    return get_prefs()


def _legacy_folder() -> Optional[str]:
    """The content folder of the legacy add-on, when this copy is the extension."""
    if not is_extension():
        return None
    try:
        legacy = bpy.context.preferences.addons.get(PUBLIC_NAME)
        folder = legacy.preferences.filepath_ if legacy is not None else ""
    except (AttributeError, KeyError):
        return None
    return folder or None


def folder_has_content(folder: str) -> bool:
    return bool(folder) and has_humans(installed_packs(folder))


def resolve_content_folder() -> str:
    """The content folder, found wherever an earlier install left it. "" when none."""
    try:
        pref = _prefs()
    except Exception:  # noqa: BLE001
        pref = None
    candidates = []
    if pref is not None and pref.filepath_:
        candidates.append(("prefs", pref.filepath_))
    saved = user_settings.content_folder()
    if saved:
        candidates.append(("settings", saved))
    legacy = _legacy_folder()
    if legacy:
        candidates.append(("legacy", legacy))
    chosen = ""
    for source, folder in candidates:
        if folder_has_content(folder):
            chosen = folder
            break
    if not chosen and candidates:
        chosen = candidates[0][1]
    if chosen:
        if pref is not None and pref.filepath_ != chosen:
            pref.filepath_ = chosen
        if saved != chosen:
            user_settings.update(content_folder=chosen)
    return chosen


def cleanup_trial(folder: str) -> bool:
    """Remove the trial pack once the base pack is installed, so the add-on
    leaves trial mode. True when something was removed."""
    installed = installed_packs(folder)
    if BASE_KEY in installed and TRIAL_KEY in installed:
        return downloader.remove(folder, TRIAL_KEY)
    return False


def after_install(folder: str) -> None:
    """Main thread, after packs were installed: point the add-on at the folder
    and refresh what reads it."""
    pref = _prefs()
    normalized = os.path.join(folder, "")
    if pref.filepath_ != normalized:
        pref.filepath_ = normalized
    user_settings.update(content_folder=normalized)
    cleanup_trial(folder)
    downloader.clear_downloads(folder)
    try:
        bpy.ops.wm.save_userpref()
    except Exception:  # noqa: BLE001
        pass
    try:
        from ..content.content_packs import cpacks_refresh

        cpacks_refresh(None, bpy.context)
    except Exception as e:  # noqa: BLE001
        print("HumGen: could not refresh the content pack list:", repr(e))
    try:
        bpy.ops.hg3d.activate()
    except Exception as e:  # noqa: BLE001
        print("HumGen: could not refresh the previews:", repr(e))
