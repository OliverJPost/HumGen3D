# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The add-on's own extension repository on humgen3d.com, and the trial
request id of an install that came from the trial page.

Blender 4.2 and later update extensions from the repository they were
installed from. The website serves one at `REPO_URL`. A zip installed from
disk belongs to the local "User Default" repository and gets no updates from
Blender: it is updated by installing the newer zip over it (drag it into
Blender), which keeps the settings, and the preferences link to that
download. Don't offer to add the repository to such an install: installing
from it gives a second copy next to the first, both switched on, and two
copies of the add-on break each other.

A trial lead installs from a zip: they download it from the trial page and
drag the file into Blender, which installs it with one small dialog. (A
dragged link does not: for a repository Blender does not know yet it only
offers to add that repository, shows its address, and asks to drag again.)
The site adds one file to a lead's zip, `trial.json` with
`{"trial": "<request id>"}`, and `trial_rid()` reads it. That id is what the
trial download and the three trial events name (`trial_events`).
"""
import json
import os
import re
from typing import Optional

import bpy

from ...package import addon_package, addon_root, is_extension

SITE = "https://humgen3d.com"
REPO_URL = SITE + "/ext/index.json"
# The file the site adds to the zip of a trial lead, next to the manifest
TRIAL_FILE = "trial.json"
_RID_RE = re.compile(r"^[a-f0-9]{16}$")
_OWN_RE = re.compile(r"^https://humgen3d\.com/ext/(t/[a-f0-9]{16}/)?index\.json/?$")


def repos():
    try:
        return bpy.context.preferences.extensions.repos
    except AttributeError:  # Blender 4.0 and 4.1
        return []


def own_repo():
    """The repository this extension was installed from, or None."""
    if not is_extension():
        return None
    module = addon_package().split(".")[1] if addon_package().count(".") >= 2 else ""
    for repo in repos():
        if repo.module == module:
            return repo
    return None


def trial_rid() -> Optional[str]:
    """The trial request id of this install, when its zip came from the trial
    page: the `trial` of the `trial.json` the site put in that zip. None for
    every other install. An update replaces the add-on's folder and with it
    the file, which is why `trial_events.trial_rid` remembers the id."""
    try:
        with open(os.path.join(addon_root(), TRIAL_FILE), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    rid = data.get("trial") if isinstance(data, dict) else None
    return rid if isinstance(rid, str) and _RID_RE.match(rid) else None


def installed_from_site() -> bool:
    repo = own_repo()
    return bool(repo is not None and getattr(repo, "use_remote_url", False) and _OWN_RE.match(repo.remote_url or ""))
