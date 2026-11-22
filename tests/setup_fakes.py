"""A pack zip in memory, an installed pack on disk, a catalogue like the live
one and a small HTTP server with range support, for the setup tests."""
import http.server
import io
import json
import os
import zipfile


def make_pack(key, version, files, name=None):
    """A pack zip in memory: content_packs/<key>.json plus files {relpath: bytes}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"content_packs/{key}.json", json.dumps({"config": {"pack_name": name or key.replace("_", " "), "pack_version": list(version), "creator": "HumGen"}}))
        for rel, data in files.items():
            zf.writestr(rel, data)
    return buf.getvalue()


def write_pack(folder, key, version, files=(), name=None, on_disk=True):
    """An installed pack: content_packs/<key>.json listing `files`, and (with
    `on_disk`) each file written with the pack key as its content."""
    packs = os.path.join(str(folder), "content_packs")
    os.makedirs(packs, exist_ok=True)
    with open(os.path.join(packs, key + ".json"), "w") as f:
        json.dump({"config": {"pack_name": name or key.replace("_", " "), "pack_version": list(version), "creator": "HumGen"}, "files": list(files)}, f)
    if on_disk:
        for rel in files:
            write_file(folder, rel, key.encode())


def write_file(folder, rel, data=b"x"):
    path = os.path.join(str(folder), *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path


def exists(folder, rel):
    return os.path.exists(os.path.join(str(folder), *rel.split("/")))


def _version(key, version, size, min_addon="4.0.0", **extra):
    return dict({"version": list(version), "size": size, "sha256": None, "min_addon": min_addon, "file": f"{key}_V{version[0]}_{version[1]}.hgpack", "url": None}, **extra)


# The live catalogue of 19 October 2026 (sizes rounded)
LIVE_CATALOGUE = {
    "schema": 1,
    "generated_at": "2026-10-19T00:00:00Z",
    "addon": {"latest": "4.0.38", "min_blender": "4.0.0"},
    "packs": [
        {"key": "Base_Humans", "name": "Base Humans", "access": "licensed", "required": True, "order": 10, "versions": [_version("Base_Humans", (4, 1), 704709967)]},
        {"key": "Base_Clothes", "name": "Base Clothes", "access": "licensed", "required": True, "order": 20, "versions": [_version("Base_Clothes", (4, 1), 1111648913)]},
        {"key": "Base_Hair", "name": "Base Hair", "access": "licensed", "required": True, "order": 30, "versions": [_version("Base_Hair", (4, 1), 117632495)]},
        {"key": "Base_Poses", "name": "Base Poses", "access": "licensed", "required": False, "order": 40, "versions": [_version("Base_Poses", (4, 0), 6355004)]},
        {"key": "8K_Textures", "name": "8K Textures", "access": "licensed", "required": False, "preselected": False, "order": 80, "versions": [_version("8K_Textures", (4, 0), 2124241021)]},
        {"key": "HG_Export", "name": "HG Export", "access": "licensed", "required": False, "order": 70, "versions": [_version("HG_Export", (1, 0), 101000)]},
        {"key": "Trial_Content", "name": "Trial Content", "access": "trial", "required": True, "order": 5, "versions": [_version("Trial_Content", (4, 1), 300000000, url="https://downloads.example/HG_Trial_Content.hgpack")]},
    ],
}


class Handler(http.server.BaseHTTPRequestHandler):
    files = {}
    ranges = True
    hits = []
    # Path -> (status, content type, body) answered instead of the file,
    # whatever the Range header says: a proxy or sign-in page
    overrides = {}

    def log_message(self, *args):
        pass

    def do_GET(self):
        Handler.hits.append(self.path)
        if self.path in Handler.overrides:
            status, kind, body = Handler.overrides[self.path]
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        data = self.files.get(self.path)
        if data is None:
            self.send_error(404)
            return
        start = 0
        rng = self.headers.get("Range")
        if rng and Handler.ranges:
            start = int(rng.split("=")[1].rstrip("-"))
            if start >= len(data):
                self.send_error(416)
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
        else:
            self.send_response(200)
        body = data[start:]
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the client cancelled


