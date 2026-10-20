# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""The HG_Export content pack, which holds the data the process system runs on.

The built-in recipes, the bone names of the game skeletons and the edge lists
of the mesh reduction are not part of the add-on. They come as the content
pack HG Export (`HG_Export.hgpack`), which the setup downloads with the other
content packs of a licence. It unpacks to:

    <content folder>/content_packs/HG_Export.json
    <content folder>/process/recipes/*.json, with order.json
    <content folder>/process/game_rig_presets.json
    <content folder>/process/lod/edges.json, collar_edges.json, lod2.json

Without it the Process tab is greyed out and the process API raises
`ExportPackMissing`. `scripts/build_export_pack.py` builds the pack from the
content folder. Raise `REQUIRED_VERSION` when the add-on needs data that older
packs don't have, so users are told to update it.
"""

import functools
import json
import os
from typing import Any, Callable, Dict, Literal, Optional, Tuple, TypeVar

from ...backend.preferences.preference_func import get_prefs
from ...common.exceptions import HumGenException

PACK_NAME = "HG_Export"
PACK_FILE = PACK_NAME + ".hgpack"
# Version of the pack this add-on needs at least, (major, minor)
REQUIRED_VERSION = (1, 0)
# Folder in the content folder the pack unpacks its data to
DATA_FOLDER = "process"

Status = Literal["installed", "missing", "outdated"]
F = TypeVar("F", bound=Callable[..., Any])

# Status per manifest path, with the time the manifest was changed, as the
# interface asks on every redraw
_status_cache: Dict[str, Tuple[float, Status]] = {}


class ExportPackMissing(HumGenException):
    """The HG_Export content pack the process system needs is not installed.

    Install it with the "Install HG Export" button of the Process tab, which
    downloads it like the other content packs.
    """


def content_folder() -> str:
    """The content folder from the preferences."""
    return str(get_prefs().filepath)


def manifest_path() -> str:
    """Path of the content pack file of the pack, made when it is installed."""
    return os.path.join(content_folder(), "content_packs", PACK_NAME + ".json")


def data_folder() -> str:
    """Folder in the content folder with the data of the pack."""
    return os.path.join(content_folder(), DATA_FOLDER)


def status() -> Status:
    """Whether the pack is installed, missing, or older than this add-on needs."""
    manifest = manifest_path()
    try:
        changed = os.path.getmtime(manifest)
    except OSError:
        return "missing"
    known = _status_cache.get(manifest)
    if known and known[0] == changed:
        return known[1]

    result: Status
    if not os.path.isfile(os.path.join(data_folder(), "recipes", "order.json")):
        result = "missing"
    elif installed_version() < REQUIRED_VERSION:
        result = "outdated"
    else:
        result = "installed"
    _status_cache[manifest] = (changed, result)
    return result


def installed_version() -> Tuple[int, ...]:
    """Version of the installed pack, (0, 0) when it can't be read."""
    try:
        with open(manifest_path(), "r") as f:
            return tuple(json.load(f)["config"]["pack_version"])
    except (OSError, ValueError, KeyError, TypeError):
        return (0, 0)


def is_installed() -> bool:
    """Whether the pack is installed and recent enough for this add-on."""
    return status() == "installed"


def message(pack_status: Optional[Status] = None) -> str:
    """What is wrong with the pack and what to do, for errors and the interface."""
    pack_status = pack_status or status()
    if pack_status == "outdated":
        required = ".".join(str(n) for n in REQUIRED_VERSION)
        return (
            f"Export data needs an update: this version of Human Generator needs"
            f" HG Export {required} or newer. Update it with the button in the Process tab"
        )
    return "Export data not installed. Install HG Export with the button in the Process tab"


def require() -> None:
    """Raises `ExportPackMissing` when the pack is missing or outdated."""
    pack_status = status()
    if pack_status != "installed":
        raise ExportPackMissing(message(pack_status))


def data_path(*parts: str) -> str:
    """Path of a file of the pack, raises `ExportPackMissing` without the pack."""
    require()
    return os.path.join(data_folder(), *parts)


def needs_export_pack(func: F) -> F:
    """Decorator for the API functions that need the pack, see `require`."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        require()
        return func(*args, **kwargs)

    return wrapper  # type:ignore[return-value]
