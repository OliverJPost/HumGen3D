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
content folder, planned in the install's own mode (a trial install sees the
trial packs, never the licensed ones as "missing"), and also fills the
preference flags the older preference UI still reads.

Content notices are banners, never a lock: a pack that is not installed is
never "required", only installed packs below what the add-on needs are. The
server can silence every notice (`notices: false` in the catalogue), and a
catalogue of a schema this add-on does not know shows none either.
"""
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import bpy

from . import api_client, migration, online, user_settings
from .catalogue import (
    REQUIRED,
    Catalogue,
    PackStatus,
    addon_update_available,
    install_mode,
    installed_packs,
    plan,
    updates,
)

CACHE_FILE = "catalogue.json"
CHECK_INTERVAL = 24 * 3600.0
FAILURE_BACKOFF = 3600.0  # after a failed check, wait this long before the next automatic one
CLOCK_SLACK = 3600.0  # a last check further in the future than this means the clock was ahead
START_DELAY = 6.0


@dataclass
class UpdateStatus:
    catalogue: Optional[Catalogue] = None
    statuses: List[PackStatus] = field(default_factory=list)
    addon_update: bool = False
    checked_at: float = 0.0
    failed_at: float = 0.0
    error: str = ""
    error_code: str = ""
    checking: bool = False
    mode: str = "licensed"  # catalogue.install_mode of the content folder
    content_state: str = "unset"  # migration.content_state of the content folder

    @property
    def updates(self) -> List[PackStatus]:
        return updates(self.statuses)

    @property
    def required(self) -> List[PackStatus]:
        """Installed packs the add-on needs a newer version of: below
        REQUIRED with an update on offer, or (for a pack in REQUIRED) only
        offered for a newer add-on. A pack that is not installed never is."""
        return [
            s
            for s in self.statuses
            if s.installed is not None and (s.status == "update_required" or (s.status == "needs_newer_addon" and s.key in REQUIRED))
        ]

    @property
    def blocked_by_addon(self) -> bool:
        """An installed required pack is only offered for a newer add-on."""
        return any(s.status == "needs_newer_addon" for s in self.required)

    @property
    def notices_enabled(self) -> bool:
        """The server allows notices and the catalogue is one this add-on reads."""
        return self.catalogue is not None and self.catalogue.notices and self.catalogue.supported

    @property
    def message(self) -> str:
        """A sentence from the server to show (an outage, a known problem), or ""."""
        return self.catalogue.message if self.catalogue is not None and self.catalogue.supported else ""

    @property
    def message_url(self) -> str:
        return self.catalogue.message_url if self.message else ""

    def notice(self) -> str:
        """What the sidebar banner should say: "", "required" (an installed
        pack needs an update the user can install), "addon" (a newer add-on
        is out, or is needed for the content) or "available"."""
        if not self.notices_enabled:
            return ""
        if any(s.status == "update_required" for s in self.required):
            return "required"
        if self.blocked_by_addon or self.addon_update:
            return "addon"
        if self.updates:
            return "available"
        return ""


status = UpdateStatus()
_results: "queue.Queue[tuple]" = queue.Queue()
# Bumped by stop(): a thread started under an older generation is abandoned
# and its result ignored
_generation = 0
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
    """The folder in the preferences, else the one in the settings file."""
    try:
        from ..preferences.preference_func import get_prefs

        folder = get_prefs().filepath or ""
    except Exception:  # noqa: BLE001  preferences not registered (tests)
        folder = ""
    return folder or user_settings.content_folder() or ""


def addon_version() -> tuple:
    from ...package import addon_version as _version

    return _version()


def apply(catalogue: Optional[Catalogue] = None) -> UpdateStatus:
    """Recompute the status from the catalogue and the content folder. Main thread."""
    if catalogue is not None:
        status.catalogue = catalogue
    if status.catalogue is None:
        status.catalogue = cached_catalogue()
    folder = content_folder()
    status.content_state = migration.content_state(folder)
    installed = installed_packs(folder)
    status.mode = install_mode(installed)
    if status.catalogue is None:
        status.statuses = []
        status.addon_update = False
        _fill_preferences(status)
        return status
    version = addon_version()
    status.statuses = plan(status.catalogue, installed, version, status.mode)
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
    shown = st.notices_enabled
    pref.cpack_update_required = shown and bool(st.required)
    pref.cpack_update_available = shown and bool(st.updates)
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
    """Time for an automatic check: a day after the last one (or at once when
    that lies in the future, after a clock that was ahead), but not within an
    hour of a failed one."""
    now = time.time()
    if status.failed_at and 0 <= now - status.failed_at < FAILURE_BACKOFF:
        return False
    if status.checked_at > now + CLOCK_SLACK:
        return True
    return now - status.checked_at > CHECK_INTERVAL


def schedule(delay: float = START_DELAY) -> None:
    """Fetch the catalogue in the background soon, if it is time and allowed."""
    if bpy.app.background:
        return
    status.checked_at = _last_check_time()
    status.failed_at = _last_check_time("catalogue_failed_at")
    apply()
    if not due():
        return
    if not bpy.app.timers.is_registered(_scheduled_check):
        bpy.app.timers.register(_scheduled_check, first_interval=delay)


def _scheduled_check() -> None:
    check_now()


def stop() -> None:
    """Remove the timers and abandon a running check (its result is
    ignored). For unregister()."""
    global _generation
    _generation += 1
    for timer in (_scheduled_check, _drain):
        try:
            if bpy.app.timers.is_registered(timer):
                bpy.app.timers.unregister(timer)
        except (ValueError, AttributeError):
            pass
    status.checking = False
    while True:
        try:
            _results.get_nowait()
        except queue.Empty:
            break


def _last_check_time(key: str = "catalogue_checked_at") -> float:
    value = user_settings.get(key)
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
    generation = _generation

    def work() -> None:
        try:
            payload = api_client.request_json("GET", "/api/addon/catalogue")
            catalogue = Catalogue.from_dict(payload)
            import json

            _results.put((generation, "ok", catalogue, json.dumps(payload), on_done))
        except api_client.ApiError as e:
            _results.put((generation, "error", (e.code, e.message), None, on_done))
        except Exception as e:  # noqa: BLE001
            _results.put((generation, "error", ("bad_response", api_client.MESSAGES["bad_response"] + f" ({e!r})"), None, on_done))

    threading.Thread(target=work, name="hg-update-check", daemon=True).start()
    if not bpy.app.timers.is_registered(_drain):
        bpy.app.timers.register(_drain, first_interval=0.2, persistent=True)
    return True


def _drain() -> Optional[float]:
    try:
        generation, kind, payload, text, on_done = _results.get_nowait()
    except queue.Empty:
        return 0.2 if status.checking else None
    if generation != _generation:
        return 0.2 if status.checking else None  # from a check stop() abandoned
    status.checking = False
    if kind == "ok":
        _save_cache(text)
        status.checked_at = time.time()
        status.failed_at = 0.0
        status.error_code = ""
        user_settings.update(catalogue_checked_at=status.checked_at, catalogue_failed_at=None)
        apply(payload)
        error = None
    else:
        status.error_code, status.error = payload
        status.failed_at = time.time()
        user_settings.update(catalogue_failed_at=status.failed_at)
        error = status.error
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
