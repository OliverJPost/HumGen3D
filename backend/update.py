# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Contains the check_update function for online checking for cpack and code updates."""

import json
from typing import TYPE_CHECKING

import bpy
import requests  # type:ignore

if TYPE_CHECKING:
    from .content_packs.content_packs import HG_CONTENT_PACK  # type: ignore

from . import get_prefs, hg_log  # type: ignore


def check_update() -> None:
    """Checks if there are any code or cpack updates available."""
    from HumGen3D import bl_info

    pref = get_prefs()
    if pref.skip_url_request:
        return

    url = "https://raw.githubusercontent.com/HG3D/Public/main/versions.json"
    resp = requests.get(url, timeout=2)

    if not resp:
        hg_log("Human Generator update check timed out after 2 seconds.", level="INFO")

    pref.cpack_update_required = False
    pref.cpack_update_available = False

    update_data = json.loads(resp.text)

    # only get 2 first version numbers for required cpacks, last number can
    # be updated without needing a new required cpack item
    current_main_version = str([bl_info["version"][0], bl_info["version"][1]])

    pref.latest_version = tuple(update_data["latest_addon"])

    update_col = bpy.context.scene.hg_update_col  # type:ignore[attr-defined]
    update_col.clear()
    for version, update_types in update_data["addon_updates"].items():
        if tuple([int(i) for i in version.split(",")]) <= bl_info["version"]:
            continue
        for update_type, lines in update_types.items():
            for line in lines:
                item = update_col.add()
                item.version = tuple([int(i) for i in version.split(",")])
                item.categ = update_type
                item.line = line

    cpack_col = bpy.context.scene.contentpacks_col  # type:ignore[attr-defined]
    req_cpacks = update_data["required_cpacks"][
        current_main_version
    ]  # TODO this is bound to break
    latest_cpacks = update_data["latest_cpacks"]

    for cp in cpack_col:
        _check_cpack_update(cp, req_cpacks, latest_cpacks)


class UPDATE_INFO_ITEM(bpy.types.PropertyGroup):
    """Line item to show what features are included in new update."""

    categ: bpy.props.StringProperty()
    version: bpy.props.IntVectorProperty(default=(0, 0, 0))
    line: bpy.props.StringProperty()


Version = tuple[int, int, int]


def _check_cpack_update(
    cp: "HG_CONTENT_PACK",
    req_cpacks: dict[str, Version],
    latest_cpacks: dict[str, Version],
) -> None:
    """Checks for updates of the passed cpack.

    Args:
        cp (HG_CONTENT_PACK): HumGen content pack item
        req_cpacks (dict):
            keys: (str) cpack names,
            values: (tuple) required version
        latest_cpacks (dict):
            keys: (str) cpack names,
            values: (tuple) latest version
    """
    pref = get_prefs()
    if cp.name == "header":  # skip fake hader
        return
    current_version = tuple(cp.pack_version)
    if not current_version:
        hg_log(
            "Skipping cpack during update check, missing version number",
            cp.pack_name,
        )
        return

    if cp.pack_name in req_cpacks:
        cp.required_version = tuple(req_cpacks[cp.pack_name])
        if tuple(req_cpacks[cp.pack_name]) > current_version:
            pref.cpack_update_required = True
    if cp.pack_name in latest_cpacks:
        cp.latest_version = tuple(latest_cpacks[cp.pack_name])
        if tuple(latest_cpacks[cp.pack_name]) > current_version:
            pref.cpack_update_available = True
