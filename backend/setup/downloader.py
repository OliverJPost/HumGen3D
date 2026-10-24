# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Downloading a pack and putting it in the content folder.

A pack is a zip (`.hgpack`) whose root holds the content folder's layout:
`content_packs/<Key>.json` plus the files the pack brings. Installing is
unzipping over the content folder and writing the list of files into that
JSON, so the pack can be removed or updated file by file later without
touching anything else in the folder, such as the user's own content.

`download()` resumes a partial file, verifies the checksum when one is known
and can be cancelled between chunks. `install()` replaces an older version of
the same pack: files the old version had and the new one has not are removed.

Two rules hold for every deletion here. A file is deleted only when no other
installed pack lists it (packs share files: the trial pack and the base packs
have 155 in common, `models/HG_HUMAN.blend` among them). And only the folders
a deletion just emptied are pruned, never other empty folders in the content
folder, which may be the user's own. On case-insensitive file systems (the
default on macOS and Windows) paths are compared case-folded, so a file whose
name only changed case between versions is not deleted as stale.

Nothing here touches `bpy`.
"""
import hashlib
import json
import os
import platform
import socket
import ssl
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile
from typing import Callable, Dict, Iterable, List, Optional, Set

from . import api_client
from .catalogue import InstalledPack, installed_packs, parse_version

CHUNK = 256 * 1024
TIMEOUT = 30.0
USER_AGENT = "HumGen3D-addon"
PART_SUFFIX = ".part"
DOWNLOAD_DIR = "downloads"  # inside <folder>/content_packs/
LOCK_NAME = ".lock"  # inside the download folder
LOCK_STALE = 10 * 60.0  # seconds without a refresh before a lock is ignored

MESSAGES = {
    "offline": "Can't reach the download server. Check your internet connection and try again.",
    "timeout": "The download server stopped answering. Try again in a minute.",
    "tls": "A secure connection to the download server couldn't be made. A proxy or security software may be intercepting it.",
    "proxy": "Your network's proxy asks for a login. Sign in to it, or ask your IT department to allow the download.",
    "http": "The download server refused the file.",
    "bad_response": "The download server sent a web page instead of the file. If your network needs a sign-in page, sign in and try again.",
    "checksum": "The downloaded file is damaged. Try again.",
    "disk": "Can't write to the content folder. Check the free space and the folder's permissions.",
    "not_a_pack": "This file is not a Human Generator content pack.",
    "cancelled": "Cancelled.",
}

Progress = Callable[[int, Optional[int]], None]  # bytes so far, total when known


class DownloadError(Exception):
    def __init__(self, code: str, message: str = "", status: int = 0) -> None:
        self.code = code
        self.message = message or MESSAGES.get(code, MESSAGES["http"])
        self.status = status  # the HTTP status for "http"
        super().__init__(f"{code}: {self.message}")

    @property
    def retryable(self) -> bool:
        """Worth an automatic retry with a fresh link (which also resumes the
        .part). Not for answers a retry cannot change: a damaged file, a full
        disk, a certificate problem, a cancel."""
        if self.code in ("offline", "timeout", "bad_response"):
            return True
        if self.code == "http":
            # 5xx, a timeout or rate limit, and 403, which is what an expired
            # signed link gets
            return self.status >= 500 or self.status in (403, 408, 429)
        return False


def _open(url: str, offset: int):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)
    if offset > 0:
        req.add_header("Range", f"bytes={offset}-")
    context = api_client.ssl_context() if url.startswith("https") else None
    return urllib.request.urlopen(req, timeout=TIMEOUT, context=context)


def _hash_file(path: str) -> "hashlib._Hash":
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest


def download(url: str, dest: str, expected_size: Optional[int] = None, sha256: Optional[str] = None, progress: Optional[Progress] = None, cancel: Optional[threading.Event] = None) -> str:
    """Fetch `url` into `dest`, resuming `dest.part` when it exists. Returns `dest`.

    A finished `dest` with the right checksum (or size, without checksum) is
    kept as is. Raises DownloadError; a cancel leaves the partial file for a
    later resume.
    """
    part = dest + PART_SUFFIX
    if os.path.isfile(dest) and _complete(dest, expected_size, sha256):
        if progress:
            progress(os.path.getsize(dest), expected_size)
        return dest
    try:
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    except OSError:
        raise DownloadError("disk") from None
    offset = os.path.getsize(part) if os.path.isfile(part) else 0
    if expected_size and offset > expected_size:
        offset = 0
    digest = hashlib.sha256() if sha256 else None
    if offset and digest is not None:
        digest = _hash_file(part)
    try:
        resp = _open(url, offset)
    except urllib.error.HTTPError as e:
        if e.code == 416:  # the part is already the whole file
            resp = None
        elif e.code == 407:
            raise DownloadError("proxy", status=e.code) from None
        else:
            raise DownloadError("http", f"The download server answered {e.code} for {os.path.basename(dest)}.", e.code) from None
    except socket.timeout:
        raise DownloadError("timeout") from None
    except (urllib.error.URLError, OSError) as e:
        if "timed out" in str(e):
            raise DownloadError("timeout") from None
        if api_client.is_tls_error(e):
            raise DownloadError("tls") from None
        if api_client.is_proxy_error(e):
            raise DownloadError("proxy") from None
        raise DownloadError("offline") from None
    total: Optional[int] = expected_size
    if resp is not None:
        with resp:
            if offset and resp.status != 206 and _is_html(resp):
                # A sign-in portal or proxy page instead of the file: keep the
                # part for when the real server is back
                raise DownloadError("bad_response")
            if offset and resp.status != 206:
                # The server ignored the range: start over
                offset = 0
                digest = hashlib.sha256() if sha256 else None
            length = resp.headers.get("Content-Length")
            if length and length.isdigit():
                total = offset + int(length)
            mode = "ab" if offset else "wb"
            try:
                with open(part, mode) as f:
                    done = offset
                    if progress:
                        progress(done, total)
                    while True:
                        if cancel is not None and cancel.is_set():
                            raise DownloadError("cancelled")
                        try:
                            block = resp.read(CHUNK)
                        except socket.timeout:
                            raise DownloadError("timeout") from None
                        except (OSError, ssl.SSLError):
                            raise DownloadError("offline") from None
                        if not block:
                            break
                        f.write(block)
                        if digest is not None:
                            digest.update(block)
                        done += len(block)
                        if progress:
                            progress(done, total)
            except OSError:
                raise DownloadError("disk") from None
    if sha256 and digest is not None and digest.hexdigest().lower() != sha256.lower():
        _remove(part)
        raise DownloadError("checksum")
    if expected_size and os.path.getsize(part) != expected_size:
        _remove(part)
        raise DownloadError("checksum", "The downloaded file is incomplete. Try again.")
    try:
        os.replace(part, dest)
    except OSError:
        raise DownloadError("disk") from None
    return dest


def _is_html(resp) -> bool:
    kind = (resp.headers.get("Content-Type") or "").lower()
    return kind.startswith("text/html") or kind.startswith("application/xhtml")


def _complete(path: str, expected_size: Optional[int], sha256: Optional[str]) -> bool:
    if sha256:
        return _hash_file(path).hexdigest().lower() == sha256.lower()
    if expected_size:
        return os.path.getsize(path) == expected_size
    return False


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


# Installing


def pack_json_entry(zf: zipfile.ZipFile) -> Optional[str]:
    """The `content_packs/<Key>.json` member of a pack zip, or None."""
    for name in zf.namelist():
        parts = name.replace("\\", "/").split("/")
        if len(parts) == 2 and parts[0] == "content_packs" and parts[1].endswith(".json"):
            return name
    return None


def inspect(zip_path: str) -> InstalledPack:
    """Key, name and version of a pack zip, without installing it."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            entry = pack_json_entry(zf)
            if entry is None:
                raise DownloadError("not_a_pack")
            data = json.loads(zf.read(entry).decode("utf-8"))
    except (zipfile.BadZipFile, ValueError, OSError):
        raise DownloadError("not_a_pack") from None
    config = data.get("config", {})
    key = os.path.basename(entry)[:-5]
    return InstalledPack(key=key, name=str(config.get("pack_name", key)), version=parse_version(config.get("pack_version", [0, 0])), json_path=entry, files=[], creator=str(config.get("creator", "")))


def _safe_member(name: str) -> bool:
    """Inside the folder, and not the resource-fork junk macOS adds to zips."""
    norm = name.replace("\\", "/")
    if norm.startswith("/") or ".." in norm.split("/") or (len(norm) > 1 and norm[1] == ":"):
        return False
    parts = norm.split("/")
    return parts[0] != "__MACOSX" and parts[-1] != ".DS_Store"


def install(zip_path: str, folder: str, progress: Optional[Callable[[int, int], None]] = None, cancel: Optional[threading.Event] = None) -> InstalledPack:
    """Unzip a pack into the content folder and record its files.

    An installed older version of the same pack is replaced: its files that
    the new version does not have are removed, unless another installed pack
    lists them. The user's own files are never touched, because only files
    listed in the old pack's JSON are removed.

    The pack JSON is written last. Before extracting, the old JSON is told
    about the new files too (old version, old and new file list); only once
    every file is in place does the new JSON replace it. A cancel, crash or
    full disk in between therefore leaves the old version recorded with every
    file that may be on disk, and the next install cleans up after it.
    """
    info = inspect(zip_path)
    packs = installed_packs(folder)
    previous = packs.get(info.key)
    json_path = os.path.join(folder, "content_packs", info.key + ".json")
    try:
        with zipfile.ZipFile(zip_path) as zf:
            entry = pack_json_entry(zf)
            members = [m for m in zf.infolist() if not m.is_dir() and _safe_member(m.filename) and m.filename != entry]
            files = _unique([m.filename.replace("\\", "/") for m in members])
            data = json.loads(zf.read(entry).decode("utf-8")) if entry else {}
            if not isinstance(data, dict):
                raise DownloadError("not_a_pack")
            if previous is not None:
                _record_files(previous.json_path, _unique(previous.files + files))
            total = len(members) + 1  # the JSON is the last step
            for index, member in enumerate(members):
                if cancel is not None and cancel.is_set():
                    raise DownloadError("cancelled")
                zf.extract(member, folder)
                if progress:
                    progress(index + 1, total)
    except zipfile.BadZipFile:
        raise DownloadError("not_a_pack") from None
    except (OSError, ValueError):
        raise DownloadError("disk") from None
    data["files"] = files
    try:
        _write_json(json_path, data)
    except OSError:
        raise DownloadError("disk") from None
    if progress:
        progress(total, total)
    if previous is not None:
        others = _listed_by_others(packs, info.key)
        stale = _stale(folder, previous.files, files, others)
        _remove_files(folder, stale)
    return InstalledPack(info.key, info.name, info.version, json_path, files, info.creator)


def _unique(paths: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(paths))


def _write_json(path: str, data: dict) -> None:
    """Write a JSON file in one step: a temporary file, then a rename."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".hg-", suffix=".json.tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp, path)
    except OSError:
        _remove(tmp)
        raise


def _record_files(json_path: str, files: List[str]) -> None:
    """Replace the file list of an installed pack JSON, keeping the rest."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        data = {}
    data["files"] = files
    _write_json(json_path, data)


def remove(folder: str, key: str, only: Optional[Callable[[str], bool]] = None) -> bool:
    """Delete a pack's files and its JSON. False when it is not installed.

    Files another installed pack lists stay. `only`, when given, narrows the
    deletion further to the paths it returns True for (the JSON goes anyway).
    """
    packs = installed_packs(folder)
    pack = packs.get(key)
    if pack is None:
        return False
    protected = _keys(folder, _listed_by_others(packs, key))
    fold = _folder_fold(folder)
    doomed = [rel for rel in pack.files if fold(rel) not in protected and (only is None or only(rel))]
    _remove_files(folder, doomed)
    _remove(pack.json_path)
    remove_empty_dirs(folder, [pack.json_path])
    return True


def _listed_by_others(packs: Dict[str, InstalledPack], key: str) -> List[str]:
    return [rel for other, pack in packs.items() if other != key for rel in pack.files]


def _stale(folder: str, old: Iterable[str], new: Iterable[str], others: Iterable[str]) -> List[str]:
    """Files of the old version to remove: not in the new one, not listed by
    another pack, and not the same file as a new one under another case."""
    fold = _folder_fold(folder)
    new_by_key = {fold(rel): rel for rel in new}
    protected = set(new_by_key) | {fold(rel) for rel in others}
    result = []
    new_names = {rel.lower(): rel for rel in new}
    for rel in _unique(old):
        if fold(rel) in protected:
            continue
        twin = new_names.get(rel.lower())
        if twin is not None and _same_file(_path(folder, rel), _path(folder, twin)):
            continue  # a case-only rename the fold did not catch
        result.append(rel)
    return result


def _remove_files(folder: str, rels: Iterable[str]) -> List[str]:
    """Delete these content-relative files and prune the folders that emptied."""
    removed = []
    for rel in rels:
        path = _path(folder, rel)
        if os.path.isfile(path) or os.path.islink(path):
            try:
                os.remove(path)
            except OSError:
                continue
            removed.append(path)
    remove_empty_dirs(folder, removed)
    return removed


def _path(folder: str, rel: str) -> str:
    return os.path.join(folder, *rel.replace("\\", "/").split("/"))


def _same_file(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _keys(folder: str, rels: Iterable[str]) -> Set[str]:
    fold = _folder_fold(folder)
    return {fold(rel) for rel in rels}


def _folder_fold(folder: str) -> Callable[[str], str]:
    """How to compare paths in `folder`: case-folded (and Unicode-normalised)
    on a case-insensitive file system, as they are elsewhere."""
    if is_case_insensitive(folder):
        return lambda rel: unicodedata.normalize("NFC", rel.replace("\\", "/")).casefold()
    return lambda rel: rel.replace("\\", "/")


def is_case_insensitive(folder: str) -> bool:
    """Whether the file system `folder` lives on ignores case. Looks for an
    entry inside it under swapped case, which reads nothing but names; falls
    back to the platform's default when there is nothing to look at."""
    try:
        names = os.listdir(folder)
    except OSError:
        names = []
    for name in names:
        swapped = name.swapcase()
        if swapped != name:
            return os.path.exists(os.path.join(folder, swapped)) and _same_file(os.path.join(folder, name), os.path.join(folder, swapped))
    return platform.system() in ("Darwin", "Windows")


def remove_empty_dirs(folder: str, removed_paths: Iterable[str] = ()) -> None:
    """Prune the folders that removing `removed_paths` emptied: each removed
    file's parent, then its parent, up to but not including `folder`. Other
    empty folders, which may be the user's own, stay. A folder holding only
    a Finder `.DS_Store` counts as empty."""
    root = os.path.normcase(os.path.abspath(folder))
    for path in removed_paths:
        current = os.path.dirname(os.path.abspath(path))
        while True:
            norm = os.path.normcase(current)
            if norm == root or not norm.startswith(os.path.join(root, "")):
                break
            try:
                names = os.listdir(current)
                if names == [".DS_Store"]:
                    os.remove(os.path.join(current, ".DS_Store"))
                    names = []
                if names:
                    break
                os.rmdir(current)
            except OSError:
                break
            current = os.path.dirname(current)


def download_folder(content_folder: str) -> str:
    return os.path.join(content_folder, "content_packs", DOWNLOAD_DIR)


def clear_downloads(content_folder: str) -> None:
    """Throw away finished and partial downloads (the lock stays while held)."""
    folder = download_folder(content_folder)
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        if name != LOCK_NAME:
            _remove(os.path.join(folder, name))
    try:
        os.rmdir(folder)
    except OSError:
        pass


def free_space(folder: str) -> Optional[int]:
    """Free bytes on the disk `folder` is (or would be) on. None when that
    cannot be told, such as on some network mounts: a warning, not a block."""
    import shutil

    if not folder:
        return None
    path = folder
    while path and not os.path.isdir(path):
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    if not path or not os.path.isdir(path):
        return None
    try:
        return shutil.disk_usage(path).free
    except (OSError, ValueError):
        return None


# The download lock: one setup at a time per content folder, also across
# Blender instances. A JSON with pid, host and the time of the last refresh;
# a lock not refreshed for LOCK_STALE seconds, or whose process is gone, is
# taken over.


def lock_path(content_folder: str) -> str:
    return os.path.join(download_folder(content_folder), LOCK_NAME)


def _lock_owner() -> Dict[str, object]:
    return {"pid": os.getpid(), "host": socket.gethostname(), "time": time.time()}


def _read_lock(path: str) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _ours(data: Optional[dict]) -> bool:
    return bool(data) and data.get("pid") == os.getpid() and data.get("host") == socket.gethostname()


def _lock_alive(data: Optional[dict]) -> bool:
    if not data:
        return False
    try:
        age = time.time() - float(data.get("time", 0))
    except (TypeError, ValueError):
        return False
    if age > LOCK_STALE or age < -LOCK_STALE:
        return False
    if data.get("host") == socket.gethostname() and platform.system() != "Windows":
        # Same machine: a crashed Blender leaves its lock behind. (On Windows
        # os.kill(pid, 0) is not a harmless probe, so only the age counts.)
        try:
            os.kill(int(data.get("pid")), 0)
        except ProcessLookupError:
            return False
        except (OSError, TypeError, ValueError):
            return True
    return True


def lock_holder(content_folder: str) -> Optional[dict]:
    """The live lock of another process ({"pid", "host", "time"}), or None."""
    data = _read_lock(lock_path(content_folder))
    return data if _lock_alive(data) and not _ours(data) else None


def acquire_lock(content_folder: str) -> bool:
    """Take the download lock. False only when another live process holds it;
    a folder the lock cannot be written to counts as free, since the install
    then fails with its own disk error."""
    path = lock_path(content_folder)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError:
        return True
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        data = _read_lock(path)
        if not _ours(data) and _lock_alive(data):
            return False
        # Ours already, or left behind: take it over
        try:
            _write_json(path, _lock_owner())
        except OSError:
            return True
        return _ours(_read_lock(path))
    except OSError:
        return True
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(_lock_owner(), f)
    return True


def refresh_lock(content_folder: str) -> None:
    """Keep a held lock fresh; call it at least every few minutes."""
    path = lock_path(content_folder)
    if _ours(_read_lock(path)):
        try:
            _write_json(path, _lock_owner())
        except OSError:
            pass


def release_lock(content_folder: str) -> None:
    path = lock_path(content_folder)
    if _ours(_read_lock(path)):
        _remove(path)
        try:
            os.rmdir(os.path.dirname(path))
        except OSError:
            pass


def manifest_versions(folder: str) -> Dict[str, tuple]:
    return {key: pack.version for key, pack in installed_packs(folder).items()}
