# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The three events an install from the trial page sends humgen3d.com.

Someone who installed the add-on from the trial page has a trial request
id: the site put it in the zip they downloaded, in a file named `trial.json`
(`repository.trial_rid`). Such an install says three things, each once, at
the moment it happens:

- `setup_opened`: the setup opened for the first time.
- `trial_installed`: the trial content is installed.
- `full_installed`: the full version is installed. Its packs come from files
  and ask no server anything, so this event is the only sign that a trial
  became a full version.

Each is one small request of its own: `POST /api/trial` with
`{"event": "trial_installed", "trial": "<id>"}` plus the versions every
request names. The setup opens by itself the first time Blender runs the
add-on, so `setup_opened` is the add-on installed: with `trial_installed` it
is what the request form calls "when it's installed". The rules, which the
privacy policy on humgen3d.com states too:
- An install whose zip did not come from the trial page has no id and
  sends nothing.
- The events are named for what they are and sent readable. Don't shorten,
  encode or fold them into another request: what the add-on sends has to
  match what the privacy policy says it sends.
- Once each per install: what was sent is kept in the settings file.
- In a thread, never while Blender's online access is off, and a failure
  shows nowhere. An event that could not be sent stays due and goes out at
  the next of these moments or the next start of Blender.
- What happened is read from what is true (the setup was shown, the content
  folder holds the trial or the full version), not from calls at the right
  places, so content that got there another way (an existing folder taken
  over) counts. It is noted in the settings file when seen, so an event
  whose send failed is still sent after the install moved on (the trial
  became the full version before the server could be reached again).
"""
import re
import threading
from typing import Callable, Dict, List, Optional

from . import api_client, online, user_settings
from .catalogue import has_humans, installed_packs, is_trial_install

EVENTS = ("setup_opened", "trial_installed", "full_installed")
# Settings key: {"trial": id, "seen": [...], "sent": [...]}, the events that
# happened and those the server has
STORE_KEY = "trial_events"
_RID_RE = re.compile(r"^[a-f0-9]{16}$")

# Sends one event for a trial id; raises when it did not arrive
Sender = Callable[[str, str], object]

_lock = threading.Lock()
_busy = False
_again: Optional[str] = None
# Around every read-and-write of STORE_KEY: the main thread notes, the thread marks
_store_lock = threading.Lock()


def content(folder: str) -> str:
    """"none", "trial" or "full": what is installed in the content folder."""
    installed = installed_packs(folder)
    if not has_humans(installed):
        return "none"
    return "trial" if is_trial_install(installed) else "full"


def trial_rid() -> Optional[str]:
    """The trial request id of this install, or None. Reads the add-on's
    `trial.json` and remembers the id in the settings file, since an update
    of the add-on removes that file."""
    try:
        from . import repository

        rid = repository.trial_rid()
    except Exception:  # noqa: BLE001  outside Blender (tests)
        rid = None
    stored = user_settings.get("trial_rid")
    if rid and rid != stored:
        user_settings.update(trial_rid=rid)
    return rid or (stored if isinstance(stored, str) and stored else None)


def trial_notice() -> str:
    """"strict" or "none": which wording this install shows about what it
    tells humgen3d.com (`repository.trial_notice`). The site wrote it into
    the zip to match the request form the lead saw. Remembered like the id,
    and "strict" when nothing says: then the setup says it."""
    try:
        from . import repository

        notice = repository.trial_notice()
    except Exception:  # noqa: BLE001  outside Blender (tests)
        notice = None
    stored = user_settings.get("trial_notice")
    if notice and notice != stored:
        user_settings.update(trial_notice=notice)
    if notice:
        return notice
    return stored if stored in ("strict", "none") else "strict"


def _stored(rid: str) -> Dict[str, List[str]]:
    stored = user_settings.get(STORE_KEY)
    if not isinstance(stored, dict) or stored.get("trial") != rid:
        stored = {}
    lists = {}
    for name in ("seen", "sent"):
        events = stored.get(name)
        lists[name] = [e for e in events if e in EVENTS] if isinstance(events, list) else []
    return lists


def _store(rid: str, name: str, events: List[str]) -> List[str]:
    """Add `events` to the "seen" or "sent" list of this trial id; the list after it."""
    with _store_lock:
        lists = _stored(rid)
        new = [e for e in events if e not in lists[name]]
        if new:
            lists[name] = [e for e in EVENTS if e in lists[name] or e in new]
            user_settings.update(**{STORE_KEY: dict(lists, trial=rid)})
        return lists[name]


def sent_events(rid: str) -> List[str]:
    """The events the server already has for this trial id."""
    return _stored(rid)["sent"]


def true_now(folder: str) -> List[str]:
    """The events that describe this install as it is."""
    state = content(folder)
    is_true = {
        "setup_opened": user_settings.setup_shown(),
        "trial_installed": state == "trial",
        "full_installed": state == "full",
    }
    return [event for event in EVENTS if is_true[event]]


def due(folder: str, rid: Optional[str]) -> List[str]:
    """The events that happened and were not sent yet, in their order. Notes
    what is true now as happened. None, and nothing noted, without a trial id."""
    if not rid or not _RID_RE.match(rid):
        return []
    sent = sent_events(rid)
    if len(sent) == len(EVENTS):
        return []
    seen = _store(rid, "seen", true_now(folder))
    return [event for event in seen if event not in sent]


def _prototype_mode() -> bool:
    """The setup's prototype mode (fake downloads) talks to no server."""
    try:
        from ...user_interface.setup_overlay.state import use_fake_services

        return bool(use_fake_services())
    except Exception:  # noqa: BLE001
        return False


def report(folder: str, send: Optional[Sender] = None) -> bool:
    """Send what is due, in a thread. Call it at the moments something may
    have become true: the setup opened, an install finished, a content folder
    was taken over, Blender started. Call it from the main thread. True
    when something is being sent."""
    global _busy, _again
    rid = trial_rid()
    # Before anything can stop it: what is true now is noted as happened
    if not rid or not due(folder, rid):
        return False
    if not online.allowed():
        return False
    if send is None:
        if _prototype_mode():
            return False
        send = api_client.send_event
    with _lock:
        if _busy:
            _again = folder  # the running thread looks once more when it is done
            return True
        _busy = True
    threading.Thread(target=_work, args=(folder, rid, send), name="hg-trial-events", daemon=True).start()
    return True


def idle() -> bool:
    """Nothing is being sent."""
    return not _busy


def _work(folder: str, rid: str, send: Sender) -> None:
    global _busy, _again
    while True:
        try:
            for event in due(folder, rid):
                send(event, rid)
                _store(rid, "sent", [event])
        except Exception:  # noqa: BLE001  offline or a server problem: it stays due
            pass
        with _lock:
            if _again is None:
                _busy = False
                return
            folder, _again = _again, None
