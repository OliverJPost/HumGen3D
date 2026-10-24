# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The add-on's own extension repository on humgen3d.com.

Blender 4.2 and later update extensions from the repository they were
installed from. The website serves one at `REPO_URL`; a trial lead gets a
personal copy under `/ext/t/<rid>/index.json`, which is how the add-on learns
the trial request id without any per-user build. A zip installed from disk
belongs to the local "User Default" repository and gets no updates, so the
preferences offer to add the repository.
"""
import re
from typing import Optional

import bpy

from ...package import addon_package, is_extension

SITE = "https://humgen3d.com"
REPO_URL = SITE + "/ext/index.json"
REPO_NAME = "Human Generator"
REPO_MODULE = "humgen3d_com"
_RID_RE = re.compile(r"/ext/t/([a-f0-9]{16})/index\.json/?$")
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
    """The trial request id in the repository URL, when installed from a trial link."""
    repo = own_repo()
    if repo is None or not getattr(repo, "use_remote_url", False):
        return None
    match = _RID_RE.search(repo.remote_url or "")
    return match.group(1) if match else None


def installed_from_site() -> bool:
    repo = own_repo()
    return bool(repo is not None and getattr(repo, "use_remote_url", False) and _OWN_RE.match(repo.remote_url or ""))


def site_repo():
    for repo in repos():
        if getattr(repo, "use_remote_url", False) and _OWN_RE.match(repo.remote_url or ""):
            return repo
    return None


def can_offer_repo() -> bool:
    """Blender knows repositories, and this install does not update from ours."""
    return bool(hasattr(bpy.app, "online_access")) and site_repo() is None


def add_repo():
    """Add the repository to Blender's list. Returns it, or None when not possible."""
    existing = site_repo()
    if existing is not None:
        return existing
    try:
        repo = bpy.context.preferences.extensions.repos.new(name=REPO_NAME, module=REPO_MODULE, remote_url=REPO_URL)
    except (AttributeError, TypeError, RuntimeError):
        return None
    repo.use_remote_url = True
    repo.enabled = True
    return repo
