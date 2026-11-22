# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""A small settings file outside Blender.

Blender keeps add-on preferences per package name and per Blender version, so
the content folder was lost whenever someone moved from the legacy add-on to
the extension, or from Blender 4.2 to 4.3. The things that must survive that
live here instead: the content folder and the trial request id. The file is
plain JSON in the user's application support folder, one per user, shared by
every Blender version.

Keys in use:
    content_folder   the folder the packs are installed in
    trial_rid        the trial request id found in the add-on's trial.json
    trial_notice     "strict" or "none" from the same file: which wording the
                     trial screen shows (see trial_events.trial_notice)
    setup_shown_at   ISO time the setup first opened (by itself, which it
                     does once, or from its button)
    trial_events     what happened on an install from the trial page and what
                     of it was sent: {"trial": id, "seen": [...], "sent": [...]}
                     (see trial_events.py)
    catalogue_checked_at  epoch seconds of the last successful catalogue fetch
    catalogue_failed_at   epoch seconds of the last failed one (backoff)
    skipped_updates  pack key -> the version whose update the user put off
                     ("Hide"); hidden until a newer one comes out
"""
import json
import os
import platform
import tempfile
import threading
import time
from typing import Any, Dict, Optional, Sequence, Tuple

APP_FOLDER = "HumGen3D"
FILE_NAME = "settings.json"
ENV_OVERRIDE = "HUMGEN_SETTINGS_FILE"

# Re-entrant: update() holds it around load() and save(), which takes it too
_lock = threading.RLock()


def settings_folder() -> str:
    """The per-user, per-OS folder the settings and caches live in."""
    system = platform.system()
    if system == "Darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif system == "Windows":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP_FOLDER)


def settings_path() -> str:
    override = os.environ.get(ENV_OVERRIDE)
    if override:
        return override
    return os.path.join(settings_folder(), FILE_NAME)


def load() -> Dict[str, Any]:
    """The settings, or an empty dict when there is no file or it is unreadable."""
    path = settings_path()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(data: Dict[str, Any]) -> bool:
    """Write the whole settings dict. False when the folder is not writable."""
    path = settings_path()
    with _lock:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".settings-", suffix=".json", dir=os.path.dirname(path))
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
            os.replace(tmp, path)
        except OSError:
            return False
    return True


def get(key: str, default: Any = None) -> Any:
    return load().get(key, default)


def update(**values: Any) -> bool:
    """Set some keys and keep the rest. A value of None removes the key.
    One step under the lock: threads write here too (`trial_events`)."""
    with _lock:
        data = load()
        for key, value in values.items():
            if value is None:
                data.pop(key, None)
            else:
                data[key] = value
        return save(data)


def content_folder() -> Optional[str]:
    folder = get("content_folder")
    return folder if isinstance(folder, str) and folder else None


def skipped_updates() -> Dict[str, Tuple[int, ...]]:
    """Pack key -> the version whose update the user put off."""
    raw = get("skipped_updates")
    if not isinstance(raw, dict):
        return {}
    skipped = {}
    for key, version in raw.items():
        try:
            skipped[str(key)] = tuple(int(n) for n in version)
        except (TypeError, ValueError):
            continue
    return skipped


def skip_updates(versions: Dict[str, Sequence[int]]) -> bool:
    """Put off these pack versions, keeping what was put off before."""
    merged = {key: list(version) for key, version in skipped_updates().items()}
    merged.update({key: [int(n) for n in version] for key, version in versions.items()})
    return update(skipped_updates=merged)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def mark_setup_shown() -> bool:
    return update(setup_shown_at=_now_iso())


def setup_shown() -> bool:
    return bool(get("setup_shown_at"))
