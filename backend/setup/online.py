# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Blender's "Allow Online Access" preference (4.2 and later).

The add-on honours it for everything that talks to a server: the automatic
update check stays silent when it is off, and the setup asks for it with a
one-click button instead of sending the user to the preferences. When Blender
was started in offline mode from the command line the preference is locked,
and the button cannot help; `locked()` tells that apart.
"""
import bpy


def supported() -> bool:
    return hasattr(bpy.app, "online_access")


def allowed() -> bool:
    """True when the add-on may use the network."""
    return bool(getattr(bpy.app, "online_access", True))


def locked() -> bool:
    """True when the command line forced offline mode and the preference is read-only."""
    return bool(getattr(bpy.app, "online_access_override", False)) and not allowed()


def allow() -> bool:
    """Turn the preference on. False when it is locked or does not exist."""
    if not supported() or locked():
        return False
    try:
        bpy.context.preferences.system.use_online_access = True
    except (AttributeError, TypeError):
        return False
    return allowed()
