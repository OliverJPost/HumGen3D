# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The content catalogue: what packs exist, what is installed, what to do.

The server publishes a catalogue (`GET /api/addon/catalogue`) listing every
pack with its versions, sizes, checksums and the lowest add-on version each
needs. The add-on keeps its own idea of which pack versions it requires, in
`REQUIRED` below, next to the code that needs the data. `plan()` combines the
catalogue, the packs found in the content folder and the running add-on
version into one status per pack, which the overlay, the sidebar notice and
the preferences all show.

Nothing here touches `bpy`, so it runs in threads and in plain tests.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

Version = Tuple[int, ...]

CATALOGUE_SCHEMA = 1

# The pack versions this add-on needs. A pack below its entry is "update
# required"; one that is only behind the catalogue is "update available".
# `HG_Export` takes its number from `human/process/export_pack.py`, which
# owns that data.
REQUIRED: Dict[str, Version] = {
    "Base_Humans": (4, 1),
    "Base_Clothes": (4, 0),
    "Base_Hair": (4, 0),
    "HG_Export": (1, 0),
}

# Packs a standard install includes (the catalogue says the same with
# `required`; this is the fallback when it is unreachable)
STANDARD_KEYS = ("Base_Humans", "Base_Clothes", "Base_Hair", "Base_Poses", "HG_Export")

TRIAL_KEY = "Trial_Content"
BASE_KEY = "Base_Humans"

STATUSES = ("missing", "update_required", "update_available", "up_to_date", "needs_newer_addon", "locked")


def parse_version(value) -> Version:
    """"4.1.0", [4, 1] or (4, 1, 0) as a tuple of ints. Unknown input is (0,)."""
    if isinstance(value, (list, tuple)):
        try:
            return tuple(int(v) for v in value)
        except (TypeError, ValueError):
            return (0,)
    if isinstance(value, str):
        parts = value.strip().split(".")
        try:
            return tuple(int(p) for p in parts if p != "")
        except ValueError:
            return (0,)
    return (0,)


def version_text(version: Sequence[int]) -> str:
    return ".".join(str(n) for n in version)


def pad(version: Sequence[int], length: int = 3) -> Version:
    """Compare versions of different lengths: (4, 1) == (4, 1, 0)."""
    return tuple(version) + (0,) * (length - len(version))


@dataclass
class PackVersion:
    version: Version
    size: Optional[int]
    sha256: Optional[str]
    min_addon: Version
    file: str
    url: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "PackVersion":
        size = data.get("size")
        return cls(
            version=parse_version(data.get("version", [0])),
            size=int(size) if isinstance(size, (int, float)) and size > 0 else None,
            sha256=(data.get("sha256") or None),
            min_addon=parse_version(data.get("min_addon", "0.0.0")),
            file=str(data.get("file", "")),
            url=data.get("url") or None,
        )


@dataclass
class CataloguePack:
    key: str
    name: str
    blurb: str = ""
    access: str = "licensed"  # licensed, trial, public
    required: bool = False
    # Ticked by default in a first install. False for packs that are large
    # and only useful to some, such as the 8K textures.
    preselected: bool = True
    order: int = 100
    versions: List[PackVersion] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "CataloguePack":
        versions = [PackVersion.from_dict(v) for v in data.get("versions", []) if isinstance(v, dict)]
        versions.sort(key=lambda v: pad(v.version), reverse=True)
        return cls(
            key=str(data["key"]),
            name=str(data.get("name", data["key"])),
            blurb=str(data.get("blurb", "")),
            access=str(data.get("access", "licensed")),
            required=bool(data.get("required", False)),
            preselected=bool(data.get("preselected", True)),
            order=int(data.get("order", 100)),
            versions=versions,
        )

    @property
    def free(self) -> bool:
        return self.access in ("trial", "public")

    def latest(self) -> Optional[PackVersion]:
        return self.versions[0] if self.versions else None

    def best_for(self, addon_version: Sequence[int]) -> Optional[PackVersion]:
        """The newest version this add-on may install, or None when every
        version needs a newer add-on."""
        addon = pad(addon_version)
        for version in self.versions:
            if pad(version.min_addon) <= addon:
                return version
        return None


@dataclass
class Catalogue:
    packs: List[CataloguePack]
    latest_addon: Version = (0,)
    min_blender: Version = (0,)
    generated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Catalogue":
        if not isinstance(data, dict) or "packs" not in data:
            raise ValueError("Not a catalogue")
        addon = data.get("addon") or {}
        packs = [CataloguePack.from_dict(p) for p in data["packs"] if isinstance(p, dict) and "key" in p]
        packs.sort(key=lambda p: (p.order, p.name))
        return cls(
            packs=packs,
            latest_addon=parse_version(addon.get("latest", "0")),
            min_blender=parse_version(addon.get("min_blender", "0")),
            generated_at=str(data.get("generated_at", "")),
        )

    @classmethod
    def from_json(cls, text: str) -> "Catalogue":
        return cls.from_dict(json.loads(text))

    def get(self, key: str) -> Optional[CataloguePack]:
        return next((p for p in self.packs if p.key == key), None)


@dataclass
class InstalledPack:
    key: str
    name: str
    version: Version
    json_path: str
    files: List[str] = field(default_factory=list)
    creator: str = ""


def installed_packs(folder: str) -> Dict[str, InstalledPack]:
    """The packs in `<folder>/content_packs/*.json`, keyed by file stem."""
    result: Dict[str, InstalledPack] = {}
    if not folder:
        return result
    packs_dir = os.path.join(folder, "content_packs")
    try:
        names = sorted(os.listdir(packs_dir))
    except OSError:
        return result
    for fn in names:
        if not fn.endswith(".json"):
            continue
        path = os.path.join(packs_dir, fn)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            config = data.get("config", {})
        except (OSError, ValueError, AttributeError):
            continue
        key = fn[:-5]
        result[key] = InstalledPack(
            key=key,
            name=str(config.get("pack_name", key)),
            version=parse_version(config.get("pack_version", [0, 0])),
            json_path=path,
            files=[str(p) for p in data.get("files", [])],
            creator=str(config.get("creator", "")),
        )
    return result


def is_trial_install(installed: Dict[str, InstalledPack]) -> bool:
    """A trial install is one with the trial pack and without the base pack."""
    return TRIAL_KEY in installed and BASE_KEY not in installed


def has_humans(installed: Dict[str, InstalledPack]) -> bool:
    return BASE_KEY in installed or TRIAL_KEY in installed


@dataclass
class PackStatus:
    pack: CataloguePack
    status: str
    target: Optional[PackVersion] = None
    installed: Optional[InstalledPack] = None

    @property
    def key(self) -> str:
        return self.pack.key

    @property
    def needs_install(self) -> bool:
        return self.status in ("missing", "update_required", "update_available")

    @property
    def download_size(self) -> int:
        return self.target.size or 0 if self.target else 0


def status_of(pack: CataloguePack, installed: Optional[InstalledPack], addon_version: Sequence[int]) -> PackStatus:
    target = pack.best_for(addon_version)
    required = REQUIRED.get(pack.key)
    if installed is None:
        if target is None:
            return PackStatus(pack, "needs_newer_addon", None, None)
        return PackStatus(pack, "missing", target, None)
    have = pad(installed.version)
    if required is not None and have < pad(required):
        # Behind what the add-on needs: an update is required if the
        # catalogue offers one this add-on can take
        if target is not None and pad(target.version) > have:
            return PackStatus(pack, "update_required", target, installed)
        return PackStatus(pack, "needs_newer_addon", None, installed)
    if target is not None and pad(target.version) > have:
        return PackStatus(pack, "update_available", target, installed)
    return PackStatus(pack, "up_to_date", target, installed)


def plan(catalogue: Catalogue, installed: Dict[str, InstalledPack], addon_version: Sequence[int], mode: str = "licensed") -> List[PackStatus]:
    """One status per catalogue pack, for the given mode.

    Trial mode shows the trial packs as installable and the licensed ones as
    locked. Licensed mode leaves the trial packs out.
    """
    result = []
    for pack in catalogue.packs:
        if mode == "trial":
            if pack.access == "licensed":
                result.append(PackStatus(pack, "locked", None, installed.get(pack.key)))
                continue
        elif pack.access == "trial":
            continue
        result.append(status_of(pack, installed.get(pack.key), addon_version))
    return result


def updates(statuses: Sequence[PackStatus]) -> List[PackStatus]:
    """What an existing install should fetch: packs with a newer version and
    standard packs it lacks (an add-on update can bring a new one), required first."""
    return sorted(
        (s for s in statuses if (s.installed is not None and s.status in ("update_required", "update_available")) or (s.status == "missing" and s.pack.required)),
        key=lambda s: (s.status == "update_available", s.pack.order),
    )


def addon_update_available(catalogue: Catalogue, addon_version: Sequence[int]) -> bool:
    return pad(catalogue.latest_addon) > pad(addon_version)


def version_blocks_packs(statuses: Sequence[PackStatus]) -> bool:
    """True when some pack this add-on requires only exists for a newer add-on."""
    return any(s.status == "needs_newer_addon" and s.pack.key in REQUIRED for s in statuses)
