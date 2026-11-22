# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""What the panels need to know about the content folder, cached.

The panels ask on every redraw, and reading the pack JSONs (Base_Clothes lists
hundreds of files) is slow on network and cloud folders. The answer is kept
until the `content_packs` folder changes (installing or removing a pack writes
or deletes a JSON in it) and for at most `MAX_AGE` seconds, so an unplugged or
reconnected drive shows within moments. `clear()` forgets it at once, for
"Try again" and after a change of folder.

The two questions:
- `state(folder)`: "unset", "unreachable", "empty" or "installed", see
  `migration.content_state`.
- `is_trial(folder)`: the trial pack without the full one, see
  `catalogue.is_trial_install`, the one definition of a trial install.
"""
import os
import time
from typing import Dict, Tuple

from ..setup import migration
from ..setup.catalogue import installed_packs, is_trial_install

MAX_AGE = 3.0

# folder -> (checked at, mtime of content_packs, state, is trial)
_cache: Dict[str, Tuple[float, float, str, bool]] = {}


def _changed(folder: str) -> float:
    try:
        return os.stat(os.path.join(folder, "content_packs")).st_mtime
    except OSError:
        return -1.0


def _lookup(folder: str) -> Tuple[str, bool]:
    if not folder:
        return "unset", False
    now = time.monotonic()
    changed = _changed(folder)
    known = _cache.get(folder)
    if known is not None and known[1] == changed and now - known[0] < MAX_AGE:
        return known[2], known[3]
    folder_state = migration.content_state(folder)
    trial = folder_state == "installed" and is_trial_install(installed_packs(folder))
    _cache[folder] = (now, changed, folder_state, trial)
    return folder_state, trial


def state(folder: str) -> str:
    """"unset", "unreachable", "empty" or "installed"."""
    return _lookup(folder)[0]


def is_trial(folder: str) -> bool:
    """Whether the folder holds the trial pack and not the full one."""
    return _lookup(folder)[1]


def clear() -> None:
    _cache.clear()
