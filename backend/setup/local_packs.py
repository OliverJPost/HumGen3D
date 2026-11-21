# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Content packs as files on this computer.

The packs of the full version come as `.hgpack` files with the purchase. The
setup installs them from wherever the user saved them: nothing is downloaded
and no server is asked. This module reads what a file is (`read`) and says
what installing it would do in a content folder (`status_of`). The trial pack
and packs made by other creators are files like any other.

Nothing here touches `bpy`.
"""
import os
import zipfile
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from . import downloader
from .catalogue import BASE_KEY, REQUIRED, TRIAL_KEY, InstalledPack, Version, pad

EXTENSIONS = (".hgpack", ".zip")

# What installing a file would do: "missing" (a pack the folder doesn't have)
# and "update_available" (newer than the installed one) install; the others
# are left out, and the list says why
INSTALLS = ("missing", "update_available")
STATUSES = INSTALLS + ("up_to_date", "older", "not_needed", "not_a_pack")


@dataclass
class LocalPack:
    path: str
    key: str = ""
    name: str = ""
    version: Version = (0,)
    creator: str = ""
    size: int = 0
    """Bytes of the file."""
    unpacked_size: int = 0
    """Bytes its files take once installed."""
    problem: str = ""
    """"" for a pack, "not_a_pack" for any other file."""

    @property
    def file(self) -> str:
        return os.path.basename(self.path)


def is_pack_name(path: str) -> bool:
    return path.lower().endswith(EXTENSIONS)


def read(path: str) -> LocalPack:
    """What the file at `path` is. Never raises: a file that is not a pack
    comes back with `problem` set."""
    local = LocalPack(path=path, name=os.path.basename(path))
    try:
        local.size = os.path.getsize(path)
        info = downloader.inspect(path)
        with zipfile.ZipFile(path) as zf:
            local.unpacked_size = sum(m.file_size for m in zf.infolist() if not m.is_dir())
    except (downloader.DownloadError, zipfile.BadZipFile, OSError, ValueError):
        local.problem = "not_a_pack"
        return local
    local.key = info.key
    local.name = info.name
    local.version = info.version
    local.creator = info.creator
    return local


def newest(packs: Iterable[LocalPack]) -> List[LocalPack]:
    """One file per pack, the newest version of each, in the order given.
    Files that are not packs all stay, so the list can say so."""
    best: Dict[str, LocalPack] = {}
    for local in packs:
        key = local.key if not local.problem else "\0" + local.path
        known = best.get(key)
        if known is None or pad(local.version) > pad(known.version):
            best[key] = local
    return list(best.values())


def status_of(local: LocalPack, installed: Dict[str, InstalledPack], picked: Iterable[str] = ()) -> str:
    """What installing `local` into a folder with `installed` would do, one of
    STATUSES. `picked`: the keys of the other files chosen with it, so the
    trial pack is left out when the base pack is among them."""
    if local.problem:
        return "not_a_pack"
    if local.key == TRIAL_KEY and (BASE_KEY in installed or BASE_KEY in picked):
        return "not_needed"
    have = installed.get(local.key)
    if have is None:
        return "missing"
    if pad(local.version) > pad(have.version):
        return "update_available"
    if pad(local.version) == pad(have.version):
        return "up_to_date"
    return "older"


def needs_newer(local: LocalPack) -> Optional[Version]:
    """The version this add-on needs of the pack, when the file is older than
    that; None when the file will do."""
    required = REQUIRED.get(local.key)
    if local.problem or required is None or pad(local.version) >= pad(required):
        return None
    return required
