# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""State of the setup, shared by the overlay and the sidebar panel.

The setup is a sequence of steps (`SetupState.screen`): welcome, choose,
licence, packs, slides (the download) and done. The overlay and the fallback
in the sidebar panel are two views of the same step, so the user can go on in
either.

The work runs in threads polled by a `bpy.app.timers` timer: the catalogue
fetch, the order check and the download itself. The overlay is only a view of
it: it can be closed and reopened at any time, and the poll reopens it when
the download finishes. Nothing here touches `bpy` from a thread.

Everything that talks to a server or a disk goes through `Services`, so the
tests and the prototype mode run the same state machine against `FakeServices`.
"""
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import bpy

from ...backend.setup import api_client, downloader, migration, online, repository, user_settings
from ...backend.setup.catalogue import (
    Catalogue,
    CataloguePack,
    InstalledPack,
    PackStatus,
    PackVersion,
    installed_packs,
    plan,
    version_text,
)

PHASES = ("idle", "downloading", "installing", "done", "failed", "cancelled")
SCREENS = ("welcome", "choose", "license", "packs", "slides", "done")
MODES = ("", "trial", "licensed")

LICENSE_URL = "https://humgen3d.com/docs/faq/human-generator-asset-license"
PRIVACY_URL = "https://humgen3d.com/privacy"
ORDER_HELP_URL = "https://humgen3d.com/docs/guide/installation#order-guid"
EMAIL_HELP_URL = "https://humgen3d.com/docs/guide/installation#email"

GB = 1024**3
MB = 1024**2

# Texts of the pack statuses, as the packs screen tags them
STATUS_TAGS = {
    "locked": "Full version",
    "needs_newer_addon": "Needs a newer add-on",
    "up_to_date": "Installed",
    "update_available": "Update",
    "update_required": "Update needed",
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


def pack_from_status(s: PackStatus, update_mode: bool) -> Pack:
    pack = Pack(
        key=s.pack.key,
        name=s.pack.name,
        blurb=s.pack.blurb,
        size=s.download_size,
        required=s.pack.required and s.status == "missing" and not update_mode,
        locked=s.status in ("locked", "needs_newer_addon"),
        status=s.status,
        installed_version=s.installed.version if s.installed else (),
        target=s.target,
        url=s.target.url if s.target else None,
        file=s.target.file if s.target else "",
    )
    if pack.locked or s.status == "up_to_date":
        pack.selected = False
    elif update_mode:
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
    """The GUID as the server wants it: no surrounding spaces, braces or quotes."""
    return text.strip().strip("{}\"'").strip()


def looks_like_guid(text: str) -> bool:
    # The server is the judge of the format; only catch an empty or partial entry
    return len(clean_guid(text)) >= 4


def looks_like_email(text: str) -> bool:
    text = text.strip()
    return "@" in text and "." in text.rpartition("@")[2] and " " not in text


def default_folder() -> str:
    return migration.default_folder()


free_space = downloader.free_space


# Services: the server and the disk, swappable for tests


class Services:
    """What the state asks of the outside world. All calls block and run in threads."""

    def fetch_catalogue(self) -> Catalogue:
        raise NotImplementedError

    def activate(self, order_guid: str, email: str, newsletter: bool) -> dict:
        raise NotImplementedError

    def content_urls(self, keys: Sequence[str], order_guid: str, email: str, rid: str) -> dict:
        raise NotImplementedError

    def download(self, pack: Pack, url: str, dest: str, progress, cancel: threading.Event) -> str:
        raise NotImplementedError

    def install(self, zip_path: str, folder: str, cancel: threading.Event) -> InstalledPack:
        raise NotImplementedError


class RealServices(Services):
    def fetch_catalogue(self) -> Catalogue:
        return api_client.fetch_catalogue()

    def activate(self, order_guid: str, email: str, newsletter: bool) -> dict:
        return api_client.activate(order_guid, email, newsletter)

    def content_urls(self, keys, order_guid, email, rid) -> dict:
        return api_client.content_urls(keys, order_guid, email, rid)

    def download(self, pack: Pack, url: str, dest: str, progress, cancel) -> str:
        size = pack.target.size if pack.target else None
        sha = pack.target.sha256 if pack.target else None
        return downloader.download(url, dest, size, sha, progress, cancel)

    def install(self, zip_path: str, folder: str, cancel) -> InstalledPack:
        return downloader.install(zip_path, folder, cancel=cancel)


# A catalogue for the prototype mode and the tests, shaped like the server's
FAKE_CATALOGUE = {
    "schema": 1,
    "addon": {"latest": "4.0.38", "min_blender": "4.0.0"},
    "packs": [
        {"key": "Base_Humans", "name": "Base Humans", "blurb": "The base meshes, rig, skin textures and face presets", "access": "licensed", "required": True, "order": 10, "versions": [{"version": [4, 1], "size": int(1.9 * GB), "sha256": None, "min_addon": "4.0.0", "file": "Base_Humans_4_1.hgpack"}]},
        {"key": "Base_Clothes", "name": "Base Clothes", "blurb": "48 outfits and 22 pairs of shoes with patterns", "access": "licensed", "required": True, "order": 20, "versions": [{"version": [4, 1], "size": int(1.4 * GB), "sha256": None, "min_addon": "4.0.0", "file": "Base_Clothes_4_1.hgpack"}]},
        {"key": "Base_Hair", "name": "Base Hair", "blurb": "43 hairstyles, 13 beards and eyebrows", "access": "licensed", "required": True, "order": 30, "versions": [{"version": [4, 1], "size": 620 * MB, "sha256": None, "min_addon": "4.0.0", "file": "Base_Hair_4_1.hgpack"}]},
        {"key": "Base_Poses", "name": "Base Poses", "blurb": "160 poses in categories", "access": "licensed", "required": False, "order": 40, "versions": [{"version": [4, 0], "size": 85 * MB, "sha256": None, "min_addon": "4.0.0", "file": "Base_Poses_4_0.hgpack"}]},
        {"key": "Extra_Presets", "name": "Extra Presets", "blurb": "20 more starting humans", "access": "licensed", "required": False, "order": 50, "versions": [{"version": [1, 0], "size": 310 * MB, "sha256": None, "min_addon": "4.0.0", "file": "Extra_Presets_1_0.hgpack"}]},
        {"key": "Base_Animations", "name": "Base Animations", "blurb": "Walk cycles and idles for the game export", "access": "licensed", "required": False, "order": 60, "versions": [{"version": [4, 0], "size": 450 * MB, "sha256": None, "min_addon": "4.0.0", "file": "Base_Animations_4_0.hgpack"}]},
        {"key": "8K_Textures", "name": "8K Textures", "blurb": "8K skin textures for close-ups. Optional: 2 GB, the 4K textures in Base Humans serve most scenes", "access": "licensed", "required": False, "preselected": False, "order": 80, "versions": [{"version": [4, 0], "size": 2124241021, "sha256": None, "min_addon": "4.0.0", "file": "8K_Textures_OPTIONAL_V4_0.hgpack"}]},
        {"key": "HG_Export", "name": "HG Export", "blurb": "Recipes and skeletons for Unity, Unreal and Godot", "access": "licensed", "required": True, "order": 70, "versions": [{"version": [1, 0], "size": 12 * MB, "sha256": None, "min_addon": "4.0.0", "file": "HG_Export_1_0.hgpack"}]},
        {"key": "Trial_Content", "name": "Trial Content", "blurb": "One human, skin, outfit, hairstyle and four poses", "access": "trial", "required": True, "order": 5, "versions": [{"version": [1, 0], "size": 340 * MB, "sha256": None, "min_addon": "4.0.0", "file": "HG_Trial_Content.hgpack", "url": "fake://HG_Trial_Content.hgpack"}]},
    ],
}

# Seconds the whole fake download takes, whatever is selected
FAKE_DURATION = 30.0
FAKE_INSTALL_SECONDS = 1.2
FAKE_CHECK_SECONDS = 1.8


class FakeServices(Services):
    """Counts bytes instead of downloading and answers the order check by a
    rule: any GUID passes, except one that starts with "0". Installs nothing."""

    def __init__(self) -> None:
        self.fail_requested = False
        self.catalogue_error: Optional[str] = None

    def fetch_catalogue(self) -> Catalogue:
        time.sleep(min(FAKE_CHECK_SECONDS, 0.5))
        if self.catalogue_error:
            raise api_client.ApiError("offline", self.catalogue_error)
        return Catalogue.from_dict(FAKE_CATALOGUE)

    def activate(self, order_guid: str, email: str, newsletter: bool) -> dict:
        time.sleep(FAKE_CHECK_SECONDS)
        if order_guid.startswith("0"):
            raise api_client.ApiError("not_found")
        return {"ok": True, "license": "commercial"}

    def content_urls(self, keys, order_guid, email, rid) -> dict:
        return {"files": {k: {"url": f"fake://{k}"} for k in keys}, "errors": {}}

    def download(self, pack: Pack, url: str, dest: str, progress, cancel) -> str:
        total = max(pack.size, 1)
        rate = max(total / FAKE_DURATION, 1.0)
        step = 0.05
        done = 0
        while done < total:
            if cancel.is_set():
                raise downloader.DownloadError("cancelled")
            if self.fail_requested:
                self.fail_requested = False
                raise downloader.DownloadError("offline", f"Could not reach downloads.humgen3d.com while fetching {pack.name}")
            time.sleep(step)
            done = min(total, done + int(rate * step))
            progress(done, total)
        return dest

    def install(self, zip_path: str, folder: str, cancel) -> InstalledPack:
        time.sleep(FAKE_INSTALL_SECONDS)
        return InstalledPack("", "", (0,), "")


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


@dataclass
class SetupState:
    services: Services = field(default_factory=default_services)
    mode: str = ""  # "", "trial" or "licensed"
    screen: str = "welcome"  # the step both the overlay and the panel show (SCREENS)
    phase: str = "idle"
    folder: str = field(default_factory=default_folder)
    packs: List[Pack] = field(default_factory=list)
    current: Optional[Pack] = None
    error: str = ""
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
    # Catalogue: idle, loading, ok, failed
    catalogue: Optional[Catalogue] = None
    catalogue_phase: str = "idle"
    catalogue_error: str = ""
    # Blender's online access is off and an action waits for it: "catalogue", "activate" or "start"
    online_blocked: str = ""
    # Opened to update installed packs rather than to install
    update_mode: bool = False
    # The trial request id, when installed from a trial link
    rid: str = ""
    # The install finished and the main thread took it over (folder set, lists refreshed)
    finalized: bool = False
    worker: Optional[threading.Thread] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)

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
    def credentials(self) -> Dict[str, str]:
        """The order the user activated with, from the settings file."""
        data = user_settings.load()
        return {"order_guid": str(data.get("order_guid", "")), "email": str(data.get("email", ""))}

    @property
    def activated(self) -> bool:
        return bool(self.credentials["order_guid"])

    # Steps

    def choose(self, mode: str) -> None:
        """Choice screen: the trial goes straight to the packs, a licence is checked first."""
        self.set_mode(mode)
        if mode == "trial" or self.activated:
            self.screen = "packs"
            self.ensure_catalogue()
        else:
            self.screen = "license"

    def set_mode(self, mode: str) -> None:
        if mode != self.mode:
            self.mode = mode
            self.build_packs()

    def go(self, screen: str) -> None:
        self.screen = screen
        if screen == "packs":
            self.ensure_catalogue()

    def back(self) -> None:
        if self.screen == "choose":
            self.screen = "welcome"
        elif self.screen == "license":
            self.screen = "choose"
        elif self.screen == "packs":
            if self.update_mode:
                self.screen = "welcome"
            else:
                self.screen = "license" if self.mode == "licensed" and not self.activated else "choose"

    def begin_update(self) -> None:
        """Entered from the update notice: the installed packs that have a newer version."""
        self.prompted = True
        self.update_mode = True
        self.mode = "licensed"
        self.build_packs()
        self.screen = "packs" if self.activated else "license"
        if self.screen == "packs":
            self.ensure_catalogue()

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
        statuses = plan(self.catalogue, installed_packs(self.folder), _addon_version(), self.mode or "licensed")
        self.packs = [pack_from_status(s, self.update_mode) for s in statuses]

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
        creds = self.credentials
        if not form.order_guid and creds["order_guid"]:
            form.order_guid = creds["order_guid"]
        if not form.email and creds["email"]:
            form.email = creds["email"]

    def activate(self, order_guid: str, email: str, accepted: bool, newsletter: bool = False) -> bool:
        """Start the order check. False (with `license_error` set) if the form is incomplete."""
        if self.checking:
            return True
        if not looks_like_guid(order_guid):
            self.license_error = "Enter the order GUID from your Superhive order."
            return False
        if not looks_like_email(email):
            self.license_error = "Enter the email address of your Superhive account."
            return False
        if not accepted:
            self.license_error = "Accept the licence and the privacy policy to continue."
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

    # Download

    def start(self) -> None:
        if self.active:
            return
        if not online.allowed():
            self.online_blocked = "start"
            return
        self.online_blocked = ""
        for pack in self.packs:
            pack.done_bytes = 0
            pack.state = "pending"
        self.error = ""
        self.ready_unseen = False
        self.finalized = False
        self.rid = repository.trial_rid() or user_settings.get("trial_rid", "") or ""
        if self.rid:
            user_settings.update(trial_rid=self.rid)
        self.cancel_event = threading.Event()
        self.started = time.monotonic()
        self.phase = "downloading"
        self.screen = "slides"
        self.worker = InstallWorker(self)
        self.worker.start()
        _start_poll()

    def cancel(self) -> None:
        if self.active:
            self.cancel_event.set()

    def abort(self) -> None:
        """Stop the download, throw away what it fetched and go back to the pack choice."""
        worker = self.worker if self.active else None
        self.cancel_event.set()
        if worker is not None:
            worker.join(timeout=5.0)
        for pack in self.packs:
            pack.done_bytes = 0
            pack.state = "pending"
        self.phase = "idle"
        self.current = None
        self.error = ""
        self.reopen_when_done = False
        self.ready_unseen = False
        self.screen = "packs"
        if isinstance(self.services, RealServices):
            downloader.clear_downloads(self.folder)

    def fail(self) -> None:
        """Dev switch: make the running fake download fail."""
        if isinstance(self.services, FakeServices):
            self.services.fail_requested = True

    def finish_on_main_thread(self) -> None:
        """Called by the poll once the worker is done: hand the folder to the add-on."""
        if self.finalized or self.phase != "done":
            return
        self.finalized = True
        if isinstance(self.services, RealServices):
            try:
                migration.after_install(self.folder)
            except Exception as e:  # noqa: BLE001
                print("HumGen: finishing the install failed:", repr(e))
        try:
            from ...backend.setup import update_check

            update_check.apply()
        except Exception:  # noqa: BLE001
            pass

    def reset(self) -> None:
        self.cancel()
        self.phase = "idle"
        self.screen = "welcome"
        self.mode = ""
        self.packs = []
        self.current = None
        self.error = ""
        self.prompted = False
        self.fallback_open = False
        self.ready_unseen = False
        self.reopen_when_done = False
        self.license_phase = "idle"
        self.license_error = ""
        self.catalogue = None
        self.catalogue_phase = "idle"
        self.catalogue_error = ""
        self.online_blocked = ""
        self.update_mode = False
        self.finalized = False


def _addon_version() -> tuple:
    try:
        from ...package import addon_version

        return addon_version()
    except Exception:  # noqa: BLE001
        return (0, 0, 0)


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
    def __init__(self, state: "SetupState", order_guid: str, email: str, newsletter: bool) -> None:
        super().__init__(name="hg-license-check", daemon=True)
        self.state = state
        self.order_guid = order_guid
        self.email = email
        self.newsletter = newsletter

    def run(self) -> None:
        state = self.state
        try:
            answer = state.services.activate(self.order_guid, self.email, self.newsletter)
        except api_client.ApiError as e:
            state.license_error = e.message
            state.license_phase = "failed"
            return
        except Exception as e:  # noqa: BLE001
            state.license_error = api_client.MESSAGES["bad_response"] + f" ({e!r})"
            state.license_phase = "failed"
            return
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        user_settings.update(
            order_guid=self.order_guid,
            email=self.email,
            newsletter=self.newsletter,
            license=answer.get("license"),
            activated_at=now,
            terms_accepted_at=now,
        )
        state.license_phase = "ok"
        state.set_mode("licensed")
        state.screen = "packs"
        state.ensure_catalogue()


class InstallWorker(threading.Thread):
    """Downloads and installs the selected packs, one after the other."""

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
                return  # abort() sets the state
            state.error = e.message
            state.phase = "failed"
        except api_client.ApiError as e:
            state.error = e.message
            state.phase = "failed"
            if e.code in ("not_found", "email_mismatch", "refunded", "invalid"):
                # The saved order no longer passes: ask again next time
                user_settings.update(order_guid=None, email=None)
        except Exception as e:  # noqa: BLE001
            state.error = api_client.MESSAGES["bad_response"] + f" ({e!r})"
            state.phase = "failed"
        finally:
            state.finished = time.monotonic()

    def _run(self, state: "SetupState", cancel: threading.Event) -> None:
        packs = state.selected
        if not packs:
            state.phase = "done"
            return
        creds = state.credentials
        answer = state.services.content_urls([p.key for p in packs], creds["order_guid"], creds["email"], state.rid)
        files = answer.get("files", {})
        errors = answer.get("errors", {})
        for pack in packs:
            info = files.get(pack.key)
            if info and info.get("url"):
                pack.url = info["url"]
                if pack.target is not None:
                    if info.get("size"):
                        pack.target.size = int(info["size"])
                        pack.size = pack.target.size
                    if info.get("sha256"):
                        pack.target.sha256 = info["sha256"]
            elif not pack.url:
                raise downloader.DownloadError("http", f"{pack.name} is not available: {errors.get(pack.key, 'no download')}.")
        folder = downloader.download_folder(state.folder)
        for pack in packs:
            if cancel.is_set():
                raise downloader.DownloadError("cancelled")
            state.current = pack
            pack.state = "downloading"
            state.phase = "downloading"
            dest = os.path.join(folder, pack.file or (pack.key + ".hgpack"))

            def progress(done: int, total: Optional[int], pack: Pack = pack) -> None:
                if total and total != pack.size:
                    pack.size = total
                pack.done_bytes = min(done, pack.size) if pack.size else done

            state.services.download(pack, pack.url or "", dest, progress, cancel)
            pack.done_bytes = pack.size
            pack.state = "installing"
            state.phase = "installing"
            state.services.install(dest, state.folder, cancel)
            if isinstance(state.services, RealServices):
                downloader._remove(dest)
            pack.state = "done"
        state.phase = "done"


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
    if state.busy:
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
