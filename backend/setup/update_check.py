# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The background check for add-on and content updates.

The old check fetched a JSON on the main thread inside the load handler, with
a timeout, and delayed every file open; it was off by default for that
reason. This one never blocks: the fetch runs in a thread, started from a
timer a few seconds after load, at most once a day, and only when Blender's
online access is allowed. The result is kept in a cache file next to the
settings, so the notice shows at once on the next start.

`status` is the single result the sidebar notice, the preferences and the
setup overlay read. `apply()` recomputes it from the catalogue and the
content folder, and also fills the preference flags the older preference UI
still reads.
"""
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import bpy

from . import api_client, online, user_settings
from .catalogue import (
    Catalogue,
    PackStatus,
    addon_update_available,
    installed_packs,
    plan,
    updates,
    version_blocks_packs,
)

CACHE_FILE = "catalogue.json"
CHECK_INTERVAL = 24 * 3600.0
START_DELAY = 6.0


@dataclass
class UpdateStatus:
    catalogue: Optional[Catalogue] = None
    statuses: List[PackStatus] = field(default_factory=list)
    addon_update: bool = False
    checked_at: float = 0.0
    error: str = ""
    checking: bool = False

    @property
    def updates(self) -> List[PackStatus]:
        return updates(self.statuses)

    @property
    def required(self) -> List[PackStatus]:
        """Updates without which the add-on does not work fully."""
        return [s for s in self.updates if s.status in ("update_required", "missing")]

    @property
    def blocked_by_addon(self) -> bool:
        return version_blocks_packs(self.statuses)

    def notice(self) -> str:
        """What the sidebar should say: "", "required", "addon" or "available"."""
        if self.required or self.blocked_by_addon:
            return "required"
        if self.addon_update:
            return "addon"
        if self.updates:
            return "available"
        return ""


status = UpdateStatus()
_results: "queue.Queue[tuple]" = queue.Queue()
_listeners: List[Callable[[], None]] = []


def cache_path() -> str:
    return os.path.join(os.path.dirname(user_settings.settings_path()), CACHE_FILE)


def cached_catalogue() -> Optional[Catalogue]:
    try:
        with open(cache_path(), encoding="utf-8") as f:
            return Catalogue.from_json(f.read())
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _save_cache(catalogue_text: str) -> None:
    path = cache_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(catalogue_text)
    except OSError:
        pass


def content_folder() -> str:
    try:
        from ..preferences.preference_func import get_prefs

        return get_prefs().filepath or ""
    except Exception:  # noqa: BLE001  preferences not registered (tests)
        return user_settings.content_folder() or ""


def addon_version() -> tuple:
    from ...package import addon_version as _version

    return _version()


def apply(catalogue: Optional[Catalogue] = None) -> UpdateStatus:
    """Recompute the status from the catalogue and the content folder. Main thread."""
    if catalogue is not None:
        status.catalogue = catalogue
    if status.catalogue is None:
        status.catalogue = cached_catalogue()
    if status.catalogue is None:
        status.statuses = []
        status.addon_update = False
        return status
    installed = installed_packs(content_folder())
    version = addon_version()
    status.statuses = plan(status.catalogue, installed, version, "licensed")
    status.addon_update = addon_update_available(status.catalogue, version)
    _fill_preferences(status)
    for listener in list(_listeners):
        try:
            listener()
        except Exception:  # noqa: BLE001
            pass
    return status


def _fill_preferences(st: UpdateStatus) -> None:
    """The flags and per-pack versions the preference UI shows."""
    try:
        from ..preferences.preference_func import get_prefs

        pref = get_prefs()
    except Exception:  # noqa: BLE001
        return
    pref.cpack_update_required = bool(st.required)
    pref.cpack_update_available = bool(st.updates)
    latest = st.catalogue.latest_addon if st.catalogue else (0,)
    pref.latest_version = tuple(latest) + (0,) * (3 - len(latest)) if len(latest) < 3 else tuple(latest[:3])
    try:
        col = bpy.context.scene.contentpacks_col
    except AttributeError:
        return
    by_name = {s.pack.name: s for s in st.statuses}
    for item in col:
        s = by_name.get(item.pack_name)
        if s is None:
            continue
        if s.target is not None:
            item.latest_version = tuple(s.target.version[:2]) + (0,) * (2 - len(s.target.version[:2]))
        if s.status == "update_required" and s.target is not None:
            item.required_version = item.latest_version


def due() -> bool:
    return time.time() - status.checked_at > CHECK_INTERVAL


def schedule(delay: float = START_DELAY) -> None:
    """Fetch the catalogue in the background soon, if it is time and allowed."""
    if bpy.app.background:
        return
    status.checked_at = _last_check_time()
    apply()
    if not due():
        return
    bpy.app.timers.register(lambda: (check_now() and None), first_interval=delay)


def _last_check_time() -> float:
    value = user_settings.get("catalogue_checked_at")
    try:
        return float(value) if value else 0.0
    except (TypeError, ValueError):
        return 0.0


def check_now(force: bool = True, on_done: Optional[Callable[[Optional[str]], None]] = None) -> bool:
    """Start a fetch in a thread. False when not allowed (offline) or already running."""
    if status.checking:
        return False
    if not online.allowed():
        status.error = "offline_mode"
        return False
    status.checking = True
    status.error = ""

    def work() -> None:
        try:
            payload = api_client.request_json("GET", "/api/addon/catalogue")
            catalogue = Catalogue.from_dict(payload)
            import json

            _results.put(("ok", catalogue, json.dumps(payload), on_done))
        except api_client.ApiError as e:
            _results.put(("error", e.message, None, on_done))
        except Exception as e:  # noqa: BLE001
            _results.put(("error", api_client.MESSAGES["bad_response"] + f" ({e!r})", None, on_done))

    threading.Thread(target=work, name="hg-update-check", daemon=True).start()
    if not bpy.app.timers.is_registered(_drain):
        bpy.app.timers.register(_drain, first_interval=0.2, persistent=True)
    return True


def _drain() -> Optional[float]:
    try:
        kind, payload, text, on_done = _results.get_nowait()
    except queue.Empty:
        return 0.2 if status.checking else None
    status.checking = False
    if kind == "ok":
        _save_cache(text)
        status.checked_at = time.time()
        user_settings.update(catalogue_checked_at=status.checked_at)
        apply(payload)
        error = None
    else:
        status.error = payload
        error = payload
    if on_done is not None:
        try:
            on_done(error)
        except Exception:  # noqa: BLE001
            pass
    _redraw()
    return None


def _redraw() -> None:
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in ("VIEW_3D", "PREFERENCES"):
                    area.tag_redraw()
    except AttributeError:
        pass


def add_listener(callback: Callable[[], None]) -> None:
    if callback not in _listeners:
        _listeners.append(callback)
