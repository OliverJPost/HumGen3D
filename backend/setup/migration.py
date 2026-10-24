# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Finding the content of an earlier install, and tidying after a new one.

Where the content folder can come from, in order: the add-on preferences of
this Blender (the normal case), the settings file (another Blender version or
the other package name), the preferences of the other copy of the add-on (the
legacy `HumGen3D` package next to the extension, or the other way round), and
the default folder the setup installs into. Whichever has content is written
to the other places, so the next lookup is the easy one.

A content folder is in one of four states (`content_state`): not set, set but
unreachable (an unplugged drive, an unmounted share, a deleted folder), empty,
or installed. An unreachable folder is never replaced, created or installed
into: the drive may simply not be connected yet.
"""
import ntpath
import os
import platform
from typing import Iterator, List, Optional, Tuple

import bpy

from ...package import PUBLIC_NAME, addon_package, is_extension
from . import downloader, user_settings
from .catalogue import BASE_KEY, TRIAL_KEY, has_humans, installed_packs

CONTENT_STATES = ("unset", "unreachable", "empty", "installed")


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


def _pref_folder(pref) -> str:
    try:
        return str(pref.filepath_ or "") if pref is not None else ""
    except (AttributeError, ReferenceError):
        return ""


def _other_copy_folders() -> List[str]:
    """Content folders in the preferences of the other copy of the add-on:
    the legacy `HumGen3D` when this is the extension, any
    `bl_ext.*.humgen3d` when this is the legacy add-on. Blender only keeps
    the preferences of enabled add-ons, so a disabled copy gives nothing."""
    own = addon_package()
    found = []
    try:
        addons = bpy.context.preferences.addons
        names = [a.module for a in addons]
    except (AttributeError, TypeError):
        return found
    for name in names:
        if name == own:
            continue
        other = name == PUBLIC_NAME if is_extension() else (name.startswith("bl_ext.") and name.rsplit(".", 1)[-1] == "humgen3d")
        if not other:
            continue
        try:
            folder = addons[name].preferences.filepath_
        except (AttributeError, KeyError, TypeError):
            continue
        if folder:
            found.append(folder)
    return found


def _legacy_folder() -> Optional[str]:
    """The content folder of the other copy of the add-on, if it has one."""
    folders = _other_copy_folders()
    return folders[0] if folders else None


def folder_has_content(folder: str) -> bool:
    return bool(folder) and has_humans(installed_packs(folder))


def drive_missing(folder: str) -> bool:
    """True when the drive or share the folder lives on is not there: an
    unplugged /Volumes/<name> or /media/<user>/<name>, an unmapped Windows
    drive letter, an unreachable \\\\server\\share. A deleted folder on a present
    drive is not a missing drive."""
    if not folder:
        return False
    drive, _rest = ntpath.splitdrive(folder) if (platform.system() == "Windows" or folder.startswith("\\\\")) else ("", folder)
    if drive:
        return not os.path.isdir(drive + "\\")
    parts = os.path.abspath(folder).split(os.sep)
    for prefix, depth in ((["", "Volumes"], 3), (["", "media"], 4), (["", "run", "media"], 5), (["", "mnt"], 3)):
        if parts[: len(prefix)] == prefix and len(parts) >= depth:
            return not os.path.isdir(os.sep.join(parts[:depth]))
    return False


def content_state(folder: str) -> str:
    """"unset", "unreachable" (set, but not an existing directory, or its
    drive is not connected), "empty" (a folder without humans) or "installed"."""
    if not folder:
        return "unset"
    if drive_missing(folder) or not os.path.isdir(folder):
        return "unreachable"
    return "installed" if folder_has_content(folder) else "empty"


def _candidates(pref) -> Iterator[Tuple[str, str]]:
    folder = _pref_folder(pref)
    if folder:
        yield "prefs", folder
    saved = user_settings.content_folder()
    if saved:
        yield "settings", saved
    for folder in _other_copy_folders():
        yield "legacy", folder
    yield "default", default_folder()


def find_existing_content() -> Optional[str]:
    """The first folder with humans among the preferences, the settings file,
    the other copy's preferences and the default folder. None when none has."""
    try:
        pref = _prefs()
    except Exception:  # noqa: BLE001
        pref = None
    for _source, folder in _candidates(pref):
        if folder_has_content(folder):
            return folder
    return None


def _same_folder(a: str, b: str) -> bool:
    if not a or not b:
        return a == b
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def resolve_content_folder() -> str:
    """The content folder, found wherever an earlier install left it. "" when none.

    The preferences win when their folder has content, or when it is merely
    unreachable: a drive that is not connected now must not lose its place.
    An empty or unset preference adopts a folder with content found
    elsewhere. With nothing found, an unset preference takes the settings
    file's folder only while that is a real folder or on a drive that is just
    not connected; a deleted folder is not adopted. Safe to call from a timer
    right after register.
    """
    try:
        pref = _prefs()
    except Exception:  # noqa: BLE001
        pref = None
    current = _pref_folder(pref)
    saved = user_settings.content_folder() or ""
    state = content_state(current)
    if state == "unreachable":
        return current
    chosen = current if state == "installed" else (find_existing_content() or "")
    if not chosen:
        if current:
            chosen = current  # an empty folder the user picked
        elif saved and (os.path.isdir(saved) or drive_missing(saved)):
            chosen = saved
    if not chosen:
        return ""
    if pref is not None and not _same_folder(current, chosen):
        try:
            pref.filepath_ = chosen
        except (AttributeError, TypeError, ReferenceError):
            pass
    if not _same_folder(saved, chosen) and content_state(chosen) != "unreachable":
        user_settings.update(content_folder=chosen)
    return chosen


def _trial_only(rel: str) -> bool:
    """A file only the trial has: its name says so (`*.trial.npz`,
    `Male Trial.png`). Older base pack JSONs do not list every file they
    installed (models/HG_HUMAN.blend is missing from some), so the trial's
    other files are kept even when no pack JSON claims them."""
    return "trial" in rel.replace("\\", "/").rsplit("/", 1)[-1].lower()


def cleanup_trial(folder: str) -> bool:
    """Remove the trial pack once the base pack is installed, so the add-on
    leaves trial mode. Only the trial's own files go, and none that another
    installed pack lists; the trial JSON goes. True when it was removed."""
    installed = installed_packs(folder)
    if BASE_KEY in installed and TRIAL_KEY in installed:
        return downloader.remove(folder, TRIAL_KEY, only=_trial_only)
    return False


def startup_cleanup(folder: Optional[str] = None) -> bool:
    """At load: tidy a leftover trial pack next to the full library (an older
    manual install, or an upgrade interrupted before its cleanup). Never
    raises. True when something was removed."""
    try:
        if folder is None:
            folder = _pref_folder(_prefs()) or user_settings.content_folder() or ""
        if content_state(folder) != "installed":
            return False
        return cleanup_trial(folder)
    except Exception as e:  # noqa: BLE001
        print("HumGen: could not tidy the trial content:", repr(e))
        return False


def after_install(folder: str) -> None:
    """Main thread, after packs were installed: point the add-on at the folder
    and refresh what reads it. The preferences are not saved here (that would
    also save changes the user meant to leave unsaved); the settings file
    keeps the folder, and `resolve_content_folder` restores it at the next start."""
    pref = _prefs()
    normalized = os.path.join(folder, "")
    if pref.filepath_ != normalized:
        pref.filepath_ = normalized
    user_settings.update(content_folder=normalized)
    cleanup_trial(folder)
    downloader.clear_downloads(folder)
    try:
        from ..content.content_packs import cpacks_refresh

        cpacks_refresh(None, bpy.context)
    except Exception as e:  # noqa: BLE001
        print("HumGen: could not refresh the content pack list:", repr(e))
    try:
        bpy.ops.hg3d.activate()
    except Exception as e:  # noqa: BLE001
        print("HumGen: could not refresh the previews:", repr(e))
