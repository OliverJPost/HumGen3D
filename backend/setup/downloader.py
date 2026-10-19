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
Nothing here touches `bpy`.
"""
import hashlib
import json
import os
import socket
import ssl
import threading
import urllib.error
import urllib.request
import zipfile
from typing import Callable, Dict, List, Optional

from .catalogue import InstalledPack, installed_packs, parse_version

CHUNK = 256 * 1024
TIMEOUT = 30.0
USER_AGENT = "HumGen3D-addon"
PART_SUFFIX = ".part"
DOWNLOAD_DIR = "downloads"  # inside <folder>/content_packs/

MESSAGES = {
    "offline": "Could not reach the download server. Check your internet connection and try again.",
    "timeout": "The download server stopped answering. Try again in a minute.",
    "http": "The download server refused the file.",
    "checksum": "The downloaded file is damaged. Try again.",
    "disk": "Could not write to the content folder. Check the free space and the folder's permissions.",
    "not_a_pack": "This file is not a Human Generator content pack.",
    "cancelled": "Cancelled.",
}

Progress = Callable[[int, Optional[int]], None]  # bytes so far, total when known


class DownloadError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        self.message = message or MESSAGES.get(code, MESSAGES["http"])
        super().__init__(f"{code}: {self.message}")


def _open(url: str, offset: int):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)
    if offset > 0:
        req.add_header("Range", f"bytes={offset}-")
    context = ssl.create_default_context() if url.startswith("https") else None
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
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
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
        else:
            raise DownloadError("http", f"The download server answered {e.code} for {os.path.basename(dest)}.") from None
    except socket.timeout:
        raise DownloadError("timeout") from None
    except (urllib.error.URLError, OSError) as e:
        if "timed out" in str(e):
            raise DownloadError("timeout") from None
        raise DownloadError("offline") from None
    total: Optional[int] = expected_size
    if resp is not None:
        with resp:
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
    the new version does not have are removed. The user's own files are never
    touched, because only files listed in the old pack's JSON are removed.
    """
    info = inspect(zip_path)
    previous = installed_packs(folder).get(info.key)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            members = [m for m in zf.infolist() if not m.is_dir() and _safe_member(m.filename)]
            files: List[str] = []
            for index, member in enumerate(members):
                if cancel is not None and cancel.is_set():
                    raise DownloadError("cancelled")
                zf.extract(member, folder)
                files.append(member.filename.replace("\\", "/"))
                if progress:
                    progress(index + 1, len(members))
    except zipfile.BadZipFile:
        raise DownloadError("not_a_pack") from None
    except OSError:
        raise DownloadError("disk") from None
    json_path = os.path.join(folder, "content_packs", info.key + ".json")
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        data["files"] = [p for p in files if p != info.json_path.replace("\\", "/")]
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except (OSError, ValueError):
        raise DownloadError("disk") from None
    if previous is not None:
        stale = set(previous.files) - set(files)
        for rel in stale:
            _remove(os.path.join(folder, *rel.split("/")))
        remove_empty_dirs(folder)
    return InstalledPack(info.key, info.name, info.version, json_path, data["files"], info.creator)


def remove(folder: str, key: str) -> bool:
    """Delete a pack's files and its JSON. False when it is not installed."""
    pack = installed_packs(folder).get(key)
    if pack is None:
        return False
    for rel in pack.files:
        _remove(os.path.join(folder, *rel.split("/")))
    _remove(pack.json_path)
    remove_empty_dirs(folder)
    return True


def remove_empty_dirs(folder: str) -> None:
    """Drop empty folders below `folder`, deepest first; `folder` itself stays."""
    for root, dirs, files in os.walk(folder, topdown=False):
        if root == folder:
            continue
        try:
            if not os.listdir(root):
                os.rmdir(root)
        except OSError:
            pass


def download_folder(content_folder: str) -> str:
    return os.path.join(content_folder, "content_packs", DOWNLOAD_DIR)


def clear_downloads(content_folder: str) -> None:
    """Throw away finished and partial downloads."""
    folder = download_folder(content_folder)
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        _remove(os.path.join(folder, name))
    try:
        os.rmdir(folder)
    except OSError:
        pass


def free_space(folder: str) -> int:
    import shutil

    path = folder
    while path and not os.path.isdir(path):
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    try:
        return shutil.disk_usage(path or os.path.expanduser("~")).free
    except OSError:
        return 0


def manifest_versions(folder: str) -> Dict[str, tuple]:
    return {key: pack.version for key, pack in installed_packs(folder).items()}
