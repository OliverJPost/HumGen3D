"""A pack zip in memory and a small HTTP server with range support, for the setup tests."""
import http.server
import io
import json
import zipfile


def make_pack(key, version, files, name=None):
    """A pack zip in memory: content_packs/<key>.json plus files {relpath: bytes}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"content_packs/{key}.json", json.dumps({"config": {"pack_name": name or key.replace("_", " "), "pack_version": list(version), "creator": "HumGen"}}))
        for rel, data in files.items():
            zf.writestr(rel, data)
    return buf.getvalue()


class Handler(http.server.BaseHTTPRequestHandler):
    files = {}
    ranges = True
    hits = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        Handler.hits.append(self.path)
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


