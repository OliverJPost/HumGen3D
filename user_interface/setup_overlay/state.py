# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""State of the setup, shared by the overlay and the sidebar panel.

The setup is a sequence of steps (`SetupState.screen`): welcome, choose,
licence, packs, slides (the download) and done. The overlay and the fallback
in the sidebar panel are two views of the same step, so the user can go on in
either.

Which step comes first depends on what is already known (`begin_setup`,
`begin_update`, `begin_add_packs`, `begin_upgrade`, `begin_change_credential`):
installed content skips the welcome and the choice, a stored order skips the
licence form, a trial link skips the choice. The order is asked only when a
download needs it, and a rejected order is marked, never forgotten.

The work runs in threads polled by a `bpy.app.timers` timer: the catalogue
fetch, the order check and the download itself. The overlay is only a view of
it: it can be closed and reopened at any time, and the poll reopens it when
the download finishes. Nothing here touches `bpy` from a thread; what a
thread wants done on the main thread goes through `pending`.

Everything that talks to a server or a disk goes through `Services`, so the
tests and the prototype mode run the same state machine against `FakeServices`.
"""
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple, Union

import bpy

from ...backend.setup import api_client, downloader, migration, online, repository, user_settings
from ...backend.setup.catalogue import (
    Catalogue,
    InstalledPack,
    PackStatus,
    PackVersion,
    has_humans,
    install_mode,
    installed_packs,
    is_trial_install,
    plan,
    required_space,
    version_text,
)

PHASES = ("idle", "downloading", "installing", "paused", "done", "failed", "cancelled")
SCREENS = ("welcome", "choose", "license", "packs", "slides", "done")
MODES = ("", "trial", "licensed")
# Why the licence form shows: "" in a fresh setup, "update" when a download
# needs an order and none is stored, "upgrade" for a trial user who bought,
# "change" to enter another order, "rejected" after the server refused it
LICENSE_REASONS = ("", "update", "upgrade", "change", "rejected")

LICENSE_URL = "https://humgen3d.com/docs/faq/human-generator-asset-license"
PRIVACY_URL = "https://humgen3d.com/privacy"
ORDER_HELP_URL = "https://humgen3d.com/license-key"
EMAIL_HELP_URL = "https://humgen3d.com/license-key#email"
BUY_URL = "https://humgen3d.com/pricing"
UPGRADE_URL = "https://humgen3d.com/upgrade?from=addon"
SUPPORT_EMAIL = "support@humgen3d.com"
SUPPORT_URL = "mailto:" + SUPPORT_EMAIL

GB = 1024**3
MB = 1024**2

# Waits before the automatic retries of a dropped download, in seconds. Each
# retry asks for a fresh link and resumes the partial file.
RETRY_DELAYS: Tuple[float, ...] = (3.0, 10.0, 30.0)

# Texts of the pack statuses, as the packs screen tags them
STATUS_TAGS = {
    "locked": "Full version",
    "needs_newer_addon": "Needs a newer add-on",
    "up_to_date": "Installed",
    "update_available": "Update",
    "update_required": "Needed",
}


@dataclass
class Pack:
    key: str
    name: str
    blurb: str
    size: int
    required: bool = False
    locked: bool = False
    selected: bool = True
    done_bytes: int = 0
    state: str = "pending"  # pending, downloading, installing, done
    status: str = "missing"  # catalogue status, see catalogue.STATUSES
    installed_version: tuple = ()
    target: Optional[PackVersion] = None
    url: Optional[str] = None
    file: str = ""
    free: bool = False  # a trial or public pack, downloadable without an order
    source: Optional[PackStatus] = None

    @property
    def installable(self) -> bool:
        return not self.locked and self.target is not None

    @property
    def tag(self) -> str:
        """The short label on the row, "" for a plain installable pack."""
        return STATUS_TAGS.get(self.status, "")

    @property
    def version(self) -> str:
        return version_text(self.target.version) if self.target else ""


def pack_from_status(s: PackStatus, existing: bool) -> Pack:
    """A row of the pack list. `existing`: the install is up and running
    (update or add-packs mode), so nothing is forced and only updates and the
    standard packs it lacks are ticked."""
    pack = Pack(
        key=s.pack.key,
        name=s.pack.name,
        blurb=s.pack.blurb,
        size=s.download_size,
        required=s.pack.required and s.status == "missing" and not existing,
        locked=s.status in ("locked", "needs_newer_addon"),
        status=s.status,
        installed_version=s.installed.version if s.installed else (),
        target=s.target,
        url=s.target.url if s.target else None,
        file=s.target.file if s.target else "",
        free=s.pack.free,
        source=s,
    )
    if pack.locked or s.status == "up_to_date":
        pack.selected = False
    elif existing:
        # Newer versions, plus packs a standard install has and this one lacks
        pack.selected = s.status in ("update_required", "update_available") or (s.status == "missing" and s.pack.required)
    elif s.status == "update_available":
        pack.selected = s.pack.required
    else:
        pack.selected = s.pack.required or s.pack.preselected
    return pack


def format_bytes(n: float) -> str:
    if n >= GB:
        return f"{n / GB:.1f} GB"
    if n >= MB:
        return f"{n / MB:.0f} MB"
    return f"{n / 1024:.0f} KB"


def clean_guid(text: str) -> str:
    """The order ID or licence key as the server wants it: no surrounding
    spaces, braces or quotes. Licence keys (HG3D-…) pass unchanged."""
    return text.strip().strip("{}\"'").strip()


def looks_like_guid(text: str) -> bool:
    # The server is the judge of the format; only catch an empty or partial entry
    return len(clean_guid(text)) >= 4


def looks_like_order_number(text: str) -> bool:
    """Superhive's short order number (digits only, maybe "#12345"), which
    people paste instead of the order GUID. A GUID always has letters."""
    return clean_guid(text).lstrip("#").replace(" ", "").isdigit()


def looks_like_email(text: str) -> bool:
    text = text.strip()
    return "@" in text and "." in text.rpartition("@")[2] and " " not in text


def default_folder() -> str:
    return migration.default_folder()


def buy_url(rid: str = "", panel: str = "setup") -> str:
    """The pricing page, with the trial request id for attribution."""
    query = f"utm_content={panel}"
    if rid:
        query = f"hg_rid={rid}&" + query
    return f"{BUY_URL}?{query}"


def trial_rid() -> str:
    """The trial request id: from the repository URL, or remembered earlier."""
    return repository.trial_rid() or str(user_settings.get("trial_rid", "") or "")


# Services: the server and the disk, swappable for tests


class Services:
    """What the state asks of the outside world. All calls block and run in
    threads, except the lock calls, which are quick."""

    def fetch_catalogue(self) -> Catalogue:
        raise NotImplementedError

    def activate(self, credential: str, email: str, newsletter: bool, rid: str = "") -> dict:
        raise NotImplementedError

    def content_urls(self, keys: Sequence[str], credential: str, email: str, rid: str) -> dict:
        raise NotImplementedError

    def download(self, pack: Pack, url: str, dest: str, progress, cancel: threading.Event) -> str:
        raise NotImplementedError

    def install(self, zip_path: str, folder: str, cancel: threading.Event) -> InstalledPack:
        raise NotImplementedError

    def acquire_lock(self, folder: str) -> bool:
        return True

    def refresh_lock(self, folder: str) -> None:
        pass

    def release_lock(self, folder: str) -> None:
        pass

    def discard(self, folder: str) -> None:
        """Throw away partial downloads."""

    def finish(self, folder: str) -> None:
        """Main thread: point the add-on at the folder and refresh what reads it."""


class RealServices(Services):
    def fetch_catalogue(self) -> Catalogue:
        return api_client.fetch_catalogue()

    def activate(self, credential: str, email: str, newsletter: bool, rid: str = "") -> dict:
        return api_client.activate(credential, email, newsletter, rid=rid)

    def content_urls(self, keys, credential, email, rid) -> dict:
        return api_client.content_urls(keys, credential=credential, email=email, rid=rid)

    def download(self, pack: Pack, url: str, dest: str, progress, cancel) -> str:
        size = pack.target.size if pack.target else None
        sha = pack.target.sha256 if pack.target else None
        return downloader.download(url, dest, size, sha, progress, cancel)

    def install(self, zip_path: str, folder: str, cancel) -> InstalledPack:
        return downloader.install(zip_path, folder, cancel=cancel)

    def acquire_lock(self, folder: str) -> bool:
        return downloader.acquire_lock(folder)

    def refresh_lock(self, folder: str) -> None:
        downloader.refresh_lock(folder)

    def release_lock(self, folder: str) -> None:
        downloader.release_lock(folder)

    def discard(self, folder: str) -> None:
        downloader.clear_downloads(folder)

    def finish(self, folder: str) -> None:
        migration.after_install(folder)


# A catalogue for the prototype mode and the tests, shaped like the server's
FAKE_CATALOGUE = {
    "schema": 1,
    "addon": {"latest": "4.0.38", "min_blender": "4.0.0", "notices": True, "setup": True},
    "packs": [
        {"key": "Base_Humans", "name": "Base Humans", "blurb": "The base meshes, rig, skin textures and face presets", "access": "licensed", "required": True, "order": 10, "versions": [{"version": [4, 1], "size": int(1.9 * GB), "sha256": None, "min_addon": "4.0.0", "file": "Base_Humans_4_1.hgpack"}]},
        {"key": "Base_Clothes", "name": "Base Clothes", "blurb": "48 outfits and 22 pairs of shoes with patterns", "access": "licensed", "required": True, "order": 20, "versions": [{"version": [4, 1], "size": int(1.4 * GB), "sha256": None, "min_addon": "4.0.0", "file": "Base_Clothes_4_1.hgpack"}]},
        {"key": "Base_Hair", "name": "Base Hair", "blurb": "43 hairstyles, 13 beards and eyebrows", "access": "licensed", "required": True, "order": 30, "versions": [{"version": [4, 1], "size": 620 * MB, "sha256": None, "min_addon": "4.0.0", "file": "Base_Hair_4_1.hgpack"}]},
        {"key": "Base_Poses", "name": "Base Poses", "blurb": "160 poses in categories", "access": "licensed", "required": False, "order": 40, "versions": [{"version": [4, 0], "size": 85 * MB, "sha256": None, "min_addon": "4.0.0", "file": "Base_Poses_4_0.hgpack"}]},
        {"key": "8K_Textures", "name": "8K Textures", "blurb": "8K skin textures for close-ups and large prints. Optional: a 2 GB download, and the 4K textures in Base Humans serve most scenes", "access": "licensed", "required": False, "preselected": False, "order": 80, "versions": [{"version": [4, 0], "size": 2124241021, "sha256": None, "min_addon": "4.0.0", "file": "8K_Textures_OPTIONAL_V4_0.hgpack"}]},
        {"key": "HG_Export", "name": "HG Export", "blurb": "Recipes and skeletons for Unity, Unreal and Godot", "access": "licensed", "required": False, "order": 70, "versions": [{"version": [1, 0], "size": 12 * MB, "sha256": None, "min_addon": "4.0.0", "file": "HG_Export_1_0.hgpack"}]},
        {"key": "Trial_Content", "name": "Trial Content", "blurb": "One human, skin, outfit, hairstyle and four poses", "access": "trial", "required": True, "order": 5, "versions": [{"version": [4, 1], "size": 260 * MB, "sha256": None, "min_addon": "4.0.0", "file": "HG_Trial_Content.hgpack", "url": "fake://HG_Trial_Content.hgpack"}]},
    ],
}

# Seconds the whole fake download takes, whatever is selected
FAKE_DURATION = 30.0
FAKE_INSTALL_SECONDS = 1.2
FAKE_CHECK_SECONDS = 1.8


class FakeServices(Services):
    """Counts bytes instead of downloading and answers the order check by a
    rule: any order passes, except one that starts with "0". Installs nothing.

    Switches for the tests and the dev tools: `fail_times` makes that many
    download attempts fail with a retryable error, `content_error` makes the
    link request fail with that code, `lock_taken` plays another Blender that
    holds the download lock, `catalogue_extra` is merged into the catalogue."""

    def __init__(self) -> None:
        self.fail_times = 0
        self.catalogue_error: Optional[str] = None
        self.content_error: Optional[str] = None
        self.lock_taken = False
        self.license = "commercial"
        self.catalogue_extra: Dict[str, object] = {}
        self.attempts = 0

    def fetch_catalogue(self) -> Catalogue:
        time.sleep(min(FAKE_CHECK_SECONDS, 0.5))
        if self.catalogue_error:
            raise api_client.ApiError("offline", self.catalogue_error)
        data = dict(FAKE_CATALOGUE)
        if self.catalogue_extra:
            data["addon"] = dict(FAKE_CATALOGUE["addon"], **self.catalogue_extra)  # type: ignore[arg-type]
        return Catalogue.from_dict(data)

    def activate(self, credential: str, email: str, newsletter: bool, rid: str = "") -> dict:
        time.sleep(FAKE_CHECK_SECONDS)
        if credential.startswith("0"):
            raise api_client.ApiError("not_found")
        upgrade = UPGRADE_URL if self.license == "personal" else None
        return {"ok": True, "license": self.license, "upgrade_url": upgrade}

    def content_urls(self, keys, credential, email, rid) -> dict:
        if self.content_error:
            raise api_client.ApiError(self.content_error)
        upgrade = UPGRADE_URL if self.license == "personal" else None
        return {"files": {k: {"url": f"fake://{k}"} for k in keys}, "errors": {}, "license": self.license if credential else None, "upgrade_url": upgrade}

    def download(self, pack: Pack, url: str, dest: str, progress, cancel) -> str:
        self.attempts += 1
        total = max(pack.size, 1)
        rate = max(total / FAKE_DURATION, 1.0)
        step = 0.05
        done = pack.done_bytes  # a resume continues where the last attempt stopped
        while done < total:
            if cancel.is_set():
                raise downloader.DownloadError("cancelled")
            if self.fail_times > 0:
                self.fail_times -= 1
                raise downloader.DownloadError("offline", f"Could not reach downloads.humangenerator3d.com while fetching {pack.name}.")
            time.sleep(step)
            done = min(total, done + int(rate * step))
            progress(done, total)
        return dest

    def install(self, zip_path: str, folder: str, cancel) -> InstalledPack:
        time.sleep(FAKE_INSTALL_SECONDS)
        return InstalledPack("", "", (0,), "")

    def acquire_lock(self, folder: str) -> bool:
        return not self.lock_taken


def use_fake_services() -> bool:
    """The prototype mode: set HUMGEN_FAKE_SETUP=1, or the dev tools preference."""
    if os.environ.get("HUMGEN_FAKE_SETUP"):
        return True
    try:
        from ...backend.preferences.preference_func import get_prefs

        return bool(get_prefs().dev_tools and get_prefs().fake_setup)
    except Exception:  # noqa: BLE001
        return False


def default_services() -> Services:
    return FakeServices() if use_fake_services() else RealServices()


def _retryable(error: Exception) -> bool:
    """A dropped connection or a server hiccup, worth an automatic retry."""
    if isinstance(error, downloader.DownloadError):
        return bool(getattr(error, "retryable", False))
    if isinstance(error, api_client.ApiError):
        return error.code in api_client.TRANSIENT_CODES and error.code != "rate_limited"
    return False


@dataclass
class SetupState:
    services: Services = field(default_factory=default_services)
    mode: str = ""  # "", "trial" or "licensed"
    screen: str = "welcome"  # the step both the overlay and the panel show (SCREENS)
    # The step this run of the setup started on: Back ends there
    entry: str = "welcome"
    phase: str = "idle"
    folder: str = field(default_factory=default_folder)
    packs: List[Pack] = field(default_factory=list)
    current: Optional[Pack] = None
    error: str = ""
    # The code of the error that ended the download (api_client / downloader codes)
    failure_code: str = ""
    started: float = 0.0
    finished: float = 0.0
    overlay_open: bool = False
    # The user pressed "Set up": the panel offers its own fallback from now on
    prompted: bool = False
    # The fallback in the panel is unfolded
    fallback_open: bool = False
    # The user closed the overlay during the download: reopen it when done
    reopen_when_done: bool = False
    # Done or failed while no overlay was open and it could not be reopened
    ready_unseen: bool = False
    # Licence check: idle, checking, ok, failed
    license_phase: str = "idle"
    license_error: str = ""
    license_reason: str = ""
    # The form should be filled from the stored order the next time it shows
    prefill_due: bool = False
    # Catalogue: idle, loading, ok, failed
    catalogue: Optional[Catalogue] = None
    catalogue_phase: str = "idle"
    catalogue_error: str = ""
    # Blender's online access is off and an action waits for it: "catalogue", "activate" or "start"
    online_blocked: str = ""
    # Another Blender holds the download lock of this folder
    lock_blocked: bool = False
    # Opened to update installed packs rather than to install
    update_mode: bool = False
    # Opened by an owner to add packs to a working install
    add_packs: bool = False
    # Packs to tick instead of the usual choice, such as HG_Export from the Process tab
    preselect: Tuple[str, ...] = ()
    # The trial request id, when installed from a trial link
    rid: str = ""
    # Content found elsewhere on this computer, offered on the welcome screen
    found_folder: str = ""
    # The user pointed the add-on at existing content instead of downloading
    adopted: bool = False
    # This download replaces the trial with the full library
    upgrading_trial: bool = False
    # The locked packs of the trial list are unfolded
    locked_open: bool = False
    # "Forget" in the preferences waits for its confirmation
    forget_pending: bool = False
    # Automatic retry under way: attempt number, error, monotonic time of the next try
    retry_attempt: int = 0
    retry_error: str = ""
    retry_at: float = 0.0
    # Smoothed download speed in bytes per second
    speed: float = 0.0
    # The install finished and the main thread took it over (folder set, lists refreshed)
    finalized: bool = False
    # Work a thread left for the main thread: "", "start" or "catalogue"
    pending: str = ""
    worker: Optional[threading.Thread] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    _pausing: bool = False
    _speed_mark: Optional[Tuple[float, int]] = None
    _installed: Optional[Dict[str, InstalledPack]] = None
    _installed_key: Tuple[str, float] = ("", 0.0)
    _free: Optional[int] = None
    _free_key: Tuple[str, float] = ("", 0.0)

    def __post_init__(self) -> None:
        saved = user_settings.content_folder()
        if saved:
            self.folder = saved

    # Derived

    @property
    def selected(self) -> List[Pack]:
        return [p for p in self.packs if p.selected and p.installable]

    @property
    def total_bytes(self) -> int:
        return sum(p.size for p in self.selected)

    @property
    def done_bytes(self) -> int:
        return sum(p.done_bytes for p in self.selected)

    @property
    def fraction(self) -> float:
        total = self.total_bytes
        return self.done_bytes / total if total else 0.0

    @property
    def active(self) -> bool:
        return self.phase in ("downloading", "installing")

    @property
    def paused(self) -> bool:
        return self.phase == "paused"

    @property
    def in_progress(self) -> bool:
        """A download runs or waits to be resumed."""
        return self.active or self.paused

    @property
    def checking(self) -> bool:
        return self.license_phase == "checking"

    @property
    def loading(self) -> bool:
        return self.catalogue_phase == "loading"

    @property
    def packs_done(self) -> int:
        return sum(1 for p in self.selected if p.state == "done")

    @property
    def busy(self) -> bool:
        return self.active or self.checking or self.loading

    @property
    def credential(self) -> Optional[user_settings.Credential]:
        return user_settings.credential()

    @property
    def credentials(self) -> Dict[str, str]:
        """The stored order (or licence key) and email, "" when none."""
        cred = self.credential
        return {"order_guid": cred.value if cred else "", "email": cred.email if cred else ""}

    @property
    def activated(self) -> bool:
        """A stored order the server accepted last time."""
        cred = self.credential
        return cred is not None and cred.status == "ok"

    @property
    def credential_failed(self) -> bool:
        """The download ended because the server refused the order."""
        return self.phase == "failed" and self.failure_code in api_client.CREDENTIAL_CODES

    @property
    def can_go_back(self) -> bool:
        return self.screen != self.entry

    @property
    def downloads_paused(self) -> bool:
        """The server switched downloads off, or speaks a catalogue this add-on can't read."""
        cat = self.catalogue
        return cat is not None and (not cat.setup_enabled or not cat.supported)

    @property
    def server_message(self) -> str:
        return self.catalogue.message if self.catalogue is not None else ""

    @property
    def trial_installed_here(self) -> bool:
        """The trial list with nothing left to install: the trial is in."""
        if self.mode != "trial" or not self.packs:
            return False
        free = [p for p in self.packs if not p.locked]
        return bool(free) and all(p.status == "up_to_date" for p in free)

    @property
    def addon_too_old(self) -> bool:
        return any(p.status == "needs_newer_addon" for p in self.packs)

    def installed(self, refresh: bool = False) -> Dict[str, InstalledPack]:
        """The packs in the folder, read at most once a second."""
        now = time.monotonic()
        folder, at = self._installed_key
        if refresh or self._installed is None or folder != self.folder or now - at > 1.0:
            self._installed = installed_packs(self.folder)
            self._installed_key = (self.folder, now)
        return self._installed

    @property
    def has_content(self) -> bool:
        return has_humans(self.installed())

    @property
    def has_licensed_content(self) -> bool:
        installed = self.installed()
        return has_humans(installed) and not is_trial_install(installed)

    def space(self) -> Tuple[int, Optional[int]]:
        """Bytes the selected packs need on disk while installing, and the
        free bytes (None when the disk can't tell)."""
        now = time.monotonic()
        folder, at = self._free_key
        if folder != self.folder or now - at > 2.0:
            self._free = downloader.free_space(self.folder)
            self._free_key = (self.folder, now)
        sources = [p.source for p in self.selected if p.source is not None and p.state != "done"]
        return (required_space(sources) if sources else 0), self._free

    @property
    def space_ok(self) -> bool:
        needed, free = self.space()
        return free is None or free >= needed

    @property
    def drive_missing(self) -> bool:
        """The folder is on a drive or share that is not connected: nothing is
        created or downloaded there."""
        return migration.drive_missing(self.folder)

    @property
    def can_install(self) -> bool:
        return bool(self.selected) and not self.loading and self.space_ok and not self.downloads_paused and not self.drive_missing

    # Ways in

    def _fresh(self, folder: str = "") -> None:
        """Forget the previous run's routing and outcome, keep the catalogue."""
        if folder:
            self.folder = folder
        if self.phase in ("done", "failed", "cancelled"):
            self.phase = "idle"
        self.current = None
        self.error = ""
        self.failure_code = ""
        self.finalized = False
        self.ready_unseen = False
        if not self.checking:
            self.license_phase = "idle"
        self.license_error = ""
        self.license_reason = ""
        self.update_mode = False
        self.add_packs = False
        self.preselect = ()
        self.adopted = False
        self.upgrading_trial = False
        self.lock_blocked = False
        self.locked_open = False
        self.found_folder = ""
        self.prompted = True
        self.rid = trial_rid()
        self.installed(refresh=True)

    def _enter(self, screen: str) -> None:
        self.screen = self.entry = screen
        if screen == "packs":
            self.ensure_catalogue()
        elif screen == "license":
            self._license_entered()

    def begin_setup(self, folder: str = "") -> None:
        """Fresh setup from "Set up Human Generator". Skips the steps whose
        answer is known: installed content opens the pack list to add packs,
        a stored order opens the full pack list, a trial install shows its
        pack list, a trial link leaves out the choice between trial and licence."""
        if self.in_progress:
            self.prompted = True
            return
        self._fresh(folder)
        installed = self.installed()
        if has_humans(installed) and not is_trial_install(installed):
            self.begin_add_packs()
            return
        if self.activated:
            self.set_mode("licensed", force=True)
            self.upgrading_trial = is_trial_install(installed)
            self._enter("packs")
        elif is_trial_install(installed):
            self.set_mode("trial", force=True)
            self._enter("packs")
        else:
            self.set_mode("", force=True)
            try:
                self.found_folder = migration.find_existing_content() or ""
            except Exception:  # noqa: BLE001  never let probing block the setup
                self.found_folder = ""
            self._enter("welcome")

    def begin_update(self, folder: str = "", keys: Sequence[str] = ()) -> None:
        """Entered from the update notice: the pack list in update mode. The
        order is asked only when Install is pressed and none is stored.
        `keys`: tick only these packs (installable ones), for a button that
        installs one pack, such as "Install HG Export"."""
        if self.in_progress:
            self.prompted = True
            return
        self._fresh(folder)
        self.preselect = tuple(k for k in keys if k)
        self.update_mode = True
        self.set_mode(install_mode(self.installed()), force=True)
        self._enter("packs")

    def begin_add_packs(self, folder: str = "") -> None:
        """An owner adding packs: the pack list, without welcome, choice or trial."""
        if self.in_progress:
            self.prompted = True
            return
        self._fresh(folder)
        self.add_packs = True
        self.set_mode("licensed", force=True)
        self._enter("packs")

    def begin_upgrade(self) -> None:
        """A trial user who bought: the licence form, or the full pack list when
        an order is stored. Resets a finished earlier run."""
        if self.in_progress:
            self.prompted = True
            return
        self._fresh()
        self.upgrading_trial = is_trial_install(self.installed())
        self.set_mode("licensed", force=True)
        if self.activated:
            self._enter("packs")
        else:
            self.license_reason = "upgrade"
            self._enter("license")
            if self.upgrading_trial:
                self.entry = "packs"  # Back returns to the trial's pack list

    def begin_change_credential(self) -> None:
        """The licence form filled with the stored order, to enter another one.
        The pack list follows in update mode."""
        if self.in_progress:
            self.prompted = True
            return
        self._fresh()
        self.update_mode = True
        self.set_mode("licensed", force=True)
        self.license_reason = "change"
        self._enter("license")

    def _license_entered(self) -> None:
        self.prefill_due = True
        cred = self.credential
        if cred is not None and cred.status == "rejected" and not self.license_error:
            self.license_error = cred.error_message or api_client.MESSAGES.get(cred.error_code, "")

    # Steps

    def choose(self, mode: str) -> None:
        """Choice screen: the trial goes straight to the packs, a licence is checked first."""
        if mode == "trial" and (self.activated or self.has_licensed_content):
            mode = "licensed"  # a licensed install never gets the trial
        self.set_mode(mode)
        if mode == "trial" or self.activated:
            self.go("packs")
        else:
            self.go("license")

    def set_mode(self, mode: str, force: bool = False) -> None:
        if mode != self.mode or force:
            self.mode = mode
            self.build_packs()

    def go(self, screen: str) -> None:
        self.screen = screen
        if screen == "packs":
            self.ensure_catalogue()
        elif screen == "license":
            self._license_entered()

    def back(self) -> None:
        if not self.can_go_back:
            return
        if self.screen == "choose":
            self.screen = "welcome"
        elif self.screen == "license":
            if self.license_reason == "update":
                # "Not now": the notices stop asking for these versions, so
                # someone without a license (a bundle copy) isn't asked daily
                from ...backend.setup import update_check

                update_check.status.skip([p.source for p in self.selected if p.source is not None])
            if self.license_reason in ("update", "change", "rejected"):
                self.go("packs")
            elif self.license_reason == "upgrade":
                if is_trial_install(self.installed()):
                    self.set_mode("trial")
                self.go("packs")
            else:
                # A trial link has no choice screen: its welcome offers both
                self.screen = "welcome" if self.rid else "choose"
            self.license_error = ""
        elif self.screen == "packs":
            if self.mode == "licensed" and not self.activated:
                self.go("license")
            else:
                self.screen = "welcome" if self.rid else "choose"
        if self.entry != "welcome" and self.screen in ("welcome", "choose"):
            self.screen = self.entry
    # Catalogue

    def ensure_catalogue(self) -> None:
        if self.catalogue is not None or self.loading:
            return
        self.load_catalogue()

    def load_catalogue(self) -> None:
        if self.loading:
            return
        if not online.allowed():
            self.online_blocked = "catalogue"
            return
        self.online_blocked = ""
        self.catalogue_phase = "loading"
        self.catalogue_error = ""
        self.worker = CatalogueLoad(self)
        self.worker.start()
        _start_poll()

    def build_packs(self) -> None:
        if self.catalogue is None:
            self.packs = []
            return
        statuses = plan(self.catalogue, self.installed(refresh=True), _addon_version(), self.mode or "licensed")
        existing = self.update_mode or self.add_packs
        self.packs = [pack_from_status(s, existing) for s in statuses]
        if self.preselect:
            for pack in self.packs:
                pack.selected = pack.key in self.preselect and pack.installable and pack.status != "up_to_date"

    # Online access

    def allow_online(self) -> None:
        """The "Allow online access" button: turn it on and retry what waited for it."""
        if not online.allow():
            return
        action = self.online_blocked
        self.online_blocked = ""
        if action == "catalogue":
            self.load_catalogue()
        elif action == "start":
            self.start()

    # Licence

    def prefill_form(self, form) -> None:
        """Fill the licence form from the stored order. Overwrites what is typed
        only right after a step asked for it (`prefill_due`). Main thread, never
        from a Panel.draw."""
        force = self.prefill_due
        self.prefill_due = False
        cred = self.credential
        if cred is not None:
            if force or not form.order_guid:
                form.order_guid = cred.value
            if force or not form.email:
                form.email = cred.email
        if user_settings.get("terms_accepted_at") and not form.accept_terms:
            form.accept_terms = True

    def activate(self, order_guid: str, email: str, accepted: bool, newsletter: bool = False) -> bool:
        """Start the order check. False (with `license_error` set) if the form is incomplete."""
        if self.checking:
            return True
        if not looks_like_guid(order_guid):
            self.license_error = "Enter your license key. Bought on Superhive? Use the order GUID from your order email."
            return False
        if looks_like_order_number(order_guid):
            self.license_error = "This is the order number. Enter the order GUID instead: the long code of letters and numbers in your order email."
            return False
        if not looks_like_email(email):
            self.license_error = "Enter the email you bought with."
            return False
        if not accepted:
            self.license_error = "Accept the license and the privacy policy to continue."
            return False
        if not online.allowed():
            self.online_blocked = "activate"
            self.license_error = ""
            return True
        self.online_blocked = ""
        self.license_error = ""
        self.license_phase = "checking"
        self.worker = LicenseCheck(self, clean_guid(order_guid), email.strip(), newsletter)
        self.worker.start()
        _start_poll()
        return True

    def forget_credential(self) -> bool:
        self.forget_pending = False
        return user_settings.forget_credential()

    # Download

    def start(self) -> None:
        """Install, or resume after a pause or failure: packs already done stay done."""
        if self.active or self.downloads_paused or self.drive_missing:
            return
        if any(not p.free for p in self.selected) and not self.activated:
            # The order is asked at the moment it is needed, once
            if not self.license_reason:
                cred = self.credential
                if cred is not None and cred.status == "rejected":
                    self.license_reason = "rejected"
                elif self.update_mode or self.add_packs or self.screen in ("packs", "done", "slides"):
                    self.license_reason = "update"
            self.go("license")
            return
        if not online.allowed():
            self.online_blocked = "start"
            return
        self.online_blocked = ""
        if not self.services.acquire_lock(self.folder):
            self.lock_blocked = True
            return
        self.lock_blocked = False
        keep_done = self.phase in ("failed", "paused", "cancelled")
        for pack in self.packs:
            if keep_done and pack.state == "done":
                continue
            pack.state = "pending"
            if not keep_done:
                pack.done_bytes = 0
        self.error = ""
        self.failure_code = ""
        self.ready_unseen = False
        self.finalized = False
        self._clear_retry()
        self.speed = 0.0
        self._speed_mark = None
        self.rid = trial_rid()
        if self.rid:
            user_settings.update(trial_rid=self.rid)
        if self.mode == "licensed" and is_trial_install(self.installed()):
            self.upgrading_trial = True
        self.cancel_event = threading.Event()
        self._pausing = False
        self.started = time.monotonic()
        self.phase = "downloading"
        self.screen = "slides"
        self.worker = InstallWorker(self)
        self.worker.start()
        _start_poll()

    def pause(self) -> None:
        """Stop the download and keep what it fetched, to resume later. Not
        while a pack is being extracted."""
        if self.phase == "downloading":
            self._pausing = True
            self.cancel_event.set()

    def cancel(self) -> None:
        if self.active:
            self.cancel_event.set()

    def abort(self) -> None:
        """Stop the download, throw away what it fetched and go back to the pack choice."""
        worker = self.worker if self.active else None
        self._pausing = False
        self.cancel_event.set()
        if worker is not None:
            worker.join(timeout=5.0)
        for pack in self.packs:
            if pack.state != "done":
                pack.done_bytes = 0
                pack.state = "pending"
        self.phase = "idle"
        self.current = None
        self.error = ""
        self.failure_code = ""
        self._clear_retry()
        self.reopen_when_done = False
        self.ready_unseen = False
        self.screen = "packs"
        self.services.discard(self.folder)

    def shutdown(self, timeout: float = 1.0) -> None:
        """The add-on is switched off: stop every thread quickly, keep partial files."""
        self._pausing = self.phase == "downloading"
        self.cancel_event.set()
        worker = self.worker
        if worker is not None and worker.is_alive():
            worker.join(timeout=timeout)
        self.services.release_lock(self.folder)

    def fail(self) -> None:
        """Dev switch: make the running fake download fail, retries included."""
        if isinstance(self.services, FakeServices):
            self.services.fail_times = len(RETRY_DELAYS) + 1

    def _clear_retry(self) -> None:
        self.retry_attempt = 0
        self.retry_error = ""
        self.retry_at = 0.0

    def track_speed(self, now: Optional[float] = None) -> None:
        """Sample the progress for the speed shown, smoothed over a few seconds."""
        now = time.monotonic() if now is None else now
        done = self.done_bytes
        mark = self._speed_mark
        if mark is None or done < mark[1]:
            self._speed_mark = (now, done)
            return
        elapsed = now - mark[0]
        if elapsed < 0.5:
            return
        rate = (done - mark[1]) / elapsed
        self.speed = rate if self.speed <= 0 else self.speed * 0.8 + rate * 0.2
        self._speed_mark = (now, done)

    @property
    def seconds_left(self) -> Optional[float]:
        if self.phase != "downloading" or self.speed <= 0:
            return None
        return max(0.0, self.total_bytes - self.done_bytes) / self.speed

    def finish_on_main_thread(self) -> None:
        """Called by the poll once the worker is done: hand the folder to the add-on."""
        if self.finalized or self.phase != "done":
            return
        self.finalized = True
        try:
            self.services.finish(self.folder)
        except Exception as e:  # noqa: BLE001
            print("HumGen: finishing the install failed:", repr(e))
        _refresh_update_status()

    def adopt_folder(self, folder: str) -> bool:
        """Use content already on this computer: no order, no download. Main thread."""
        if not migration.folder_has_content(folder):
            return False
        self._fresh(folder)
        self.adopted = True
        self.phase = "done"
        self.finalized = True
        try:
            self.services.finish(folder)
        except Exception as e:  # noqa: BLE001
            print("HumGen: using the content folder failed:", repr(e))
        _refresh_update_status()
        self.screen = "done"
        return True

    def dismiss(self) -> None:
        """The user is done with the finished setup: the sidebar card goes away."""
        if self.phase == "done":
            self.phase = "idle"
        self.prompted = False
        self.fallback_open = False
        self.ready_unseen = False
        self.screen = self.entry = "welcome"

    def run_pending(self) -> None:
        """Main thread: what a thread asked for."""
        action, self.pending = self.pending, ""
        if action == "start":
            self.start()
        elif action == "catalogue":
            self.ensure_catalogue()

    def reset(self) -> None:
        self.cancel()
        self.phase = "idle"
        self.screen = self.entry = "welcome"
        self.mode = ""
        self.packs = []
        self.current = None
        self.error = ""
        self.failure_code = ""
        self.prompted = False
        self.fallback_open = False
        self.ready_unseen = False
        self.reopen_when_done = False
        self.license_phase = "idle"
        self.license_error = ""
        self.license_reason = ""
        self.catalogue = None
        self.catalogue_phase = "idle"
        self.catalogue_error = ""
        self.online_blocked = ""
        self.lock_blocked = False
        self.update_mode = False
        self.add_packs = False
        self.adopted = False
        self.upgrading_trial = False
        self.found_folder = ""
        self.finalized = False
        self.pending = ""
        self._clear_retry()


def _addon_version() -> tuple:
    try:
        from ...package import addon_version

        return addon_version()
    except Exception:  # noqa: BLE001
        return (0, 0, 0)


def _refresh_update_status() -> None:
    try:
        from ...backend.setup import update_check

        update_check.apply()
    except Exception:  # noqa: BLE001
        pass


class CatalogueLoad(threading.Thread):
    def __init__(self, state: "SetupState") -> None:
        super().__init__(name="hg-catalogue", daemon=True)
        self.state = state

    def run(self) -> None:
        state = self.state
        try:
            catalogue = state.services.fetch_catalogue()
        except api_client.ApiError as e:
            state.catalogue_error = e.message
            state.catalogue_phase = "failed"
            return
        except Exception as e:  # noqa: BLE001
            state.catalogue_error = api_client.MESSAGES["bad_response"] + f" ({e!r})"
            state.catalogue_phase = "failed"
            return
        state.catalogue = catalogue
        state.build_packs()
        state.catalogue_phase = "ok"


class LicenseCheck(threading.Thread):
    def __init__(self, state: "SetupState", credential: str, email: str, newsletter: bool) -> None:
        super().__init__(name="hg-license-check", daemon=True)
        self.state = state
        self.credential = credential
        self.email = email
        self.newsletter = newsletter

    def run(self) -> None:
        state = self.state
        try:
            answer = state.services.activate(self.credential, self.email, self.newsletter, state.rid)
        except api_client.ApiError as e:
            stored = user_settings.credential()
            if e.code in api_client.CREDENTIAL_CODES and stored is not None and stored.value == self.credential:
                # A definitive answer about the stored order: mark it, never forget it
                user_settings.mark_credential_rejected(e.code, e.message)
            state.license_error = e.message
            state.license_phase = "failed"
            return
        except Exception as e:  # noqa: BLE001
            state.license_error = api_client.MESSAGES["bad_response"] + f" ({e!r})"
            state.license_phase = "failed"
            return
        user_settings.save_credential(self.credential, self.email, license=answer.get("license"), upgrade_url=answer.get("upgrade_url"))
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        user_settings.update(newsletter=self.newsletter, terms_accepted_at=now)
        state.license_phase = "ok"
        reason = state.license_reason
        state.license_reason = ""
        if reason in ("update", "rejected") and state.selected:
            # Asked at Install: go on with the download the user chose
            state.pending = "start"
            return
        state.set_mode("licensed")
        state.screen = "packs"
        state.pending = "catalogue"


class InstallWorker(threading.Thread):
    """Downloads and installs the selected packs, one after the other. Packs
    already done (an earlier attempt) are skipped; a dropped connection is
    retried a few times with a fresh link, resuming the partial file."""

    def __init__(self, state: "SetupState") -> None:
        super().__init__(name="hg-install", daemon=True)
        self.state = state

    def run(self) -> None:
        state = self.state
        cancel = state.cancel_event
        try:
            self._run(state, cancel)
        except downloader.DownloadError as e:
            if e.code == "cancelled":
                if state._pausing:
                    state._pausing = False
                    state.phase = "paused"
                    if state.current is not None and state.current.state == "downloading":
                        state.current.state = "pending"
                return  # otherwise abort() sets the state
            state.error = e.message
            state.failure_code = e.code
            state.phase = "failed"
        except api_client.ApiError as e:
            if e.code in api_client.CREDENTIAL_CODES:
                # The stored order no longer passes: mark it, keep it, ask again
                user_settings.mark_credential_rejected(e.code, e.message)
            state.error = e.message
            state.failure_code = e.code
            state.phase = "failed"
            if e.code in api_client.CREDENTIAL_CODES:
                state.screen = "done"  # where the ways out are
        except Exception as e:  # noqa: BLE001
            state.error = api_client.MESSAGES["bad_response"] + f" ({e!r})"
            state.failure_code = "bad_response"
            state.phase = "failed"
        finally:
            state._clear_retry()
            state.finished = time.monotonic()
            try:
                state.services.release_lock(state.folder)
            except Exception:  # noqa: BLE001
                pass

    def _run(self, state: "SetupState", cancel: threading.Event) -> None:
        folder = downloader.download_folder(state.folder)
        for pack in state.selected:
            if pack.state == "done":
                continue
            if cancel.is_set():
                raise downloader.DownloadError("cancelled")
            dest = os.path.join(folder, pack.file or (pack.key + ".hgpack"))
            self._download(state, pack, dest, cancel)
            pack.done_bytes = pack.size
            pack.state = "installing"
            state.phase = "installing"
            state.services.install(dest, state.folder, cancel)
            if isinstance(state.services, RealServices):
                downloader._remove(dest)
            pack.state = "done"
        state.phase = "done"

    def _download(self, state: "SetupState", pack: Pack, dest: str, cancel: threading.Event) -> None:
        attempt = 0
        last_refresh = [0.0]

        def progress(done: int, total: Optional[int], pack: Pack = pack) -> None:
            if total and total != pack.size:
                pack.size = total
            pack.done_bytes = min(done, pack.size) if pack.size else done
            now = time.monotonic()
            state.track_speed(now)
            if now - last_refresh[0] > 30.0:
                last_refresh[0] = now
                state.services.refresh_lock(state.folder)

        while True:
            if cancel.is_set():
                raise downloader.DownloadError("cancelled")
            state.current = pack
            pack.state = "downloading"
            state.phase = "downloading"
            state._speed_mark = None
            try:
                # Ask for this pack's link right before its download: signed
                # links expire after an hour, and a retry or a resumed
                # download can come days later
                self._fetch_url(state, pack)
                state.services.download(pack, pack.url or "", dest, progress, cancel)
                state._clear_retry()
                return
            except (downloader.DownloadError, api_client.ApiError) as e:
                if not _retryable(e) or attempt >= len(RETRY_DELAYS):
                    raise
                delay = RETRY_DELAYS[attempt]
                attempt += 1
                state.retry_attempt = attempt
                state.retry_error = e.message
                state.retry_at = time.monotonic() + delay
                if cancel.wait(delay):
                    raise downloader.DownloadError("cancelled") from None
                pack.url = None  # a fresh link for the next attempt

    @staticmethod
    def _fetch_url(state: "SetupState", pack: Pack) -> None:
        creds = state.credentials if not pack.free else {"order_guid": "", "email": ""}
        answer = state.services.content_urls([pack.key], creds["order_guid"], creds["email"], state.rid)
        # The server says the customer's best licence every time: an upgrade
        # to Commercial shows without entering anything again
        if creds["order_guid"]:
            user_settings.update_license(answer.get("license"), answer.get("upgrade_url"))
        info = (answer.get("files") or {}).get(pack.key)
        if info and info.get("url"):
            pack.url = info["url"]
            if pack.target is not None:
                if info.get("size"):
                    pack.target.size = int(info["size"])
                    pack.size = pack.target.size
                if info.get("sha256"):
                    pack.target.sha256 = info["sha256"]
            return
        if pack.target is not None and pack.target.url:
            pack.url = pack.target.url
            return
        code = str((answer.get("errors") or {}).get(pack.key) or "no_download")
        if code in api_client.CREDENTIAL_CODES:
            raise api_client.ApiError(code)
        if code in api_client.TRANSIENT_CODES:
            raise api_client.ApiError(code)
        raise downloader.DownloadError("pack", PackErrorText(pack.name, api_client.pack_error_message(code)))


class PackErrorText(str):
    """A per-pack error: the sentence plus the pack it is about, drawn as
    "{pack}: {reason}" through the translation."""

    def __new__(cls, pack: str, reason: str) -> "PackErrorText":
        obj = super().__new__(cls, f"{pack}: {reason}")
        obj.pack = pack
        obj.reason = reason
        return obj


def error_text(error: Union[str, PackErrorText], tr) -> str:
    """An error for the interface, translated."""
    if isinstance(error, PackErrorText):
        return tr("{pack}: {reason}").format(pack=tr(error.pack), reason=tr(error.reason))
    return tr(error) if error else ""


state = SetupState()


# Poll: redraws the viewports while something runs and reopens the overlay
# when the download ends. Runs on the main thread, so it may touch bpy.

_poll_registered = False


def _start_poll() -> None:
    global _poll_registered
    if _poll_registered and bpy.app.timers.is_registered(_poll):
        return
    bpy.app.timers.register(_poll, first_interval=0.1, persistent=True)
    _poll_registered = True


def _poll() -> Optional[float]:
    global _poll_registered
    redraw_viewports()
    if state.pending:
        state.run_pending()
    if state.busy or state.pending:
        return 0.1
    _poll_registered = False
    if state.phase == "done":
        state.finish_on_main_thread()
    if state.phase in ("done", "failed") and not state.overlay_open:
        if state.reopen_when_done:
            state.reopen_when_done = False
            if not reopen_overlay():
                state.ready_unseen = True
        else:
            state.ready_unseen = True
    return None


def stop_poll() -> None:
    global _poll_registered
    if bpy.app.timers.is_registered(_poll):
        bpy.app.timers.unregister(_poll)
    _poll_registered = False


def redraw_viewports() -> None:
    for window in bpy.data.window_managers[0].windows:
        for area in window.screen.areas:
            if area.type in ("VIEW_3D", "PREFERENCES"):
                for region in area.regions:
                    region.tag_redraw()


def reopen_overlay() -> bool:
    """Open the overlay in the first 3D viewport found. False if there is none."""
    for window in bpy.data.window_managers[0].windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if region is None:
                continue
            try:
                with bpy.context.temp_override(window=window, area=area, region=region):
                    result = bpy.ops.hg3d.setup_overlay("INVOKE_DEFAULT")
            except Exception as e:  # noqa: BLE001  another modal operator, no GPU, ...
                print("HumGen setup overlay could not reopen:", repr(e))
                return False
            return "RUNNING_MODAL" in result
    return False


def reopen_overlay_soon(delay: float = 0.05) -> None:
    """Reopen from a timer, for callers inside another operator."""

    def _open() -> None:
        if not reopen_overlay():
            state.ready_unseen = True
        return None

    bpy.app.timers.register(_open, first_interval=delay)
