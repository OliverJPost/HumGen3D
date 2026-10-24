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
# The newest catalogue schema this add-on understands. A catalogue with a
# higher number is still read for its pack list, but the add-on shows no
# notices from it (`Catalogue.supported`).
SUPPORTED_SCHEMA = 1

# The pack versions this add-on needs. A pack below its entry is "update
# required"; one that is only behind the catalogue is "update available".
# `HG_Export` takes its number from `human/process/export_pack.py`, which
# owns that data.
REQUIRED: Dict[str, Version] = {
    "Base_Humans": (4, 1),
    "Base_Clothes": (4, 0),
    "Base_Hair": (4, 0),
    "HG_Export": (1, 0),
    "Trial_Content": (4, 1),
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
    # Bytes on disk once unzipped, when the catalogue says
    unpacked_size: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict) -> "PackVersion":
        return cls(
            version=parse_version(data.get("version", [0])),
            size=_positive(data.get("size")),
            sha256=(data.get("sha256") or None),
            min_addon=parse_version(data.get("min_addon", "0.0.0")),
            file=str(data.get("file", "")),
            url=data.get("url") or None,
            unpacked_size=_positive(data.get("unpacked_size")),
        )


def _positive(value) -> Optional[int]:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else None


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
    schema: int = CATALOGUE_SCHEMA
    # Switches the server can flip without a release: `notices` off silences
    # every content notice, `setup_enabled` off stops new downloads
    notices: bool = True
    setup_enabled: bool = True
    # A sentence the server wants shown (an outage, a known problem), with
    # an optional link
    message: str = ""
    message_url: str = ""
    # Where a Personal owner upgrades, when the credential did not say
    upgrade_url: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Catalogue":
        if not isinstance(data, dict) or not isinstance(data.get("packs"), list):
            raise ValueError("Not a catalogue")
        addon = data.get("addon")
        if not isinstance(addon, dict):
            addon = {}
        packs = [CataloguePack.from_dict(p) for p in data["packs"] if isinstance(p, dict) and "key" in p]
        packs.sort(key=lambda p: (p.order, p.name))
        schema = data.get("schema", CATALOGUE_SCHEMA)
        return cls(
            packs=packs,
            latest_addon=parse_version(addon.get("latest", "0")),
            min_blender=parse_version(addon.get("min_blender", "0")),
            generated_at=str(data.get("generated_at", "")),
            schema=schema if isinstance(schema, int) and not isinstance(schema, bool) else 0,
            notices=addon.get("notices", True) is not False,
            setup_enabled=addon.get("setup", True) is not False,
            message=str(addon.get("message") or ""),
            message_url=str(addon.get("message_url") or ""),
            upgrade_url=str(addon.get("upgrade_url") or ""),
        )

    @property
    def supported(self) -> bool:
        """False for a catalogue written for a newer add-on (or a malformed
        schema field): its pack list is still read, its notices are not shown."""
        return 1 <= self.schema <= SUPPORTED_SCHEMA

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
    """The packs in `<folder>/content_packs/*.json`, keyed by file stem.

    A JSON that cannot be read or has an unexpected shape is skipped, so one
    broken file never hides the other packs.
    """
    result: Dict[str, InstalledPack] = {}
    if not folder:
        return result
    packs_dir = os.path.join(folder, "content_packs")
    try:
        names = sorted(os.listdir(packs_dir))
    except OSError:
        return result
    for fn in names:
        if not fn.endswith(".json") or fn.startswith("."):
            continue
        path = os.path.join(packs_dir, fn)
        key = fn[:-5]
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            config = data.get("config") or {}
            files = data.get("files") or []
            if not isinstance(config, dict) or not isinstance(files, list):
                continue
            result[key] = InstalledPack(
                key=key,
                name=str(config.get("pack_name") or key),
                version=parse_version(config.get("pack_version", [0, 0])),
                json_path=path,
                files=[p for p in files if isinstance(p, str) and p],
                creator=str(config.get("creator") or ""),
            )
        except (OSError, ValueError, AttributeError, TypeError):
            continue
    return result


def is_trial_install(installed: Dict[str, InstalledPack]) -> bool:
    """A trial install is one with the trial pack and without the base pack."""
    return TRIAL_KEY in installed and BASE_KEY not in installed


def install_mode(installed: Dict[str, InstalledPack]) -> str:
    """"trial" for a trial install (see `is_trial_install`), else "licensed"."""
    return "trial" if is_trial_install(installed) else "licensed"


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
            if not pack.free:
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


def required_space(selected: Sequence[PackStatus]) -> int:
    """Disk space an install of `selected` needs at its peak: every pack
    unpacked (twice its download when the catalogue has no unpacked size),
    plus the largest download, which sits next to its unpacked files until it
    is deleted. Takes anything with a `target` PackVersion."""
    targets = [s.target for s in selected if getattr(s, "target", None) is not None]
    if not targets:
        return 0
    unpacked = sum(t.unpacked_size or 2 * (t.size or 0) for t in targets)
    return unpacked + max(t.size or 0 for t in targets)
