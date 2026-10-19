"""The settings file and the humgen3d.com client, against a local fake server."""
import http.server
import json
import threading

import pytest

from HumGen3D.backend.setup import api_client, user_settings


# Settings file


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setenv(user_settings.ENV_OVERRIDE, str(path))
    return path


def test_settings_roundtrip(settings_file):
    assert user_settings.load() == {}
    assert user_settings.update(content_folder="/x", order_guid="abc")
    assert user_settings.get("order_guid") == "abc"
    assert user_settings.content_folder() == "/x"
    user_settings.update(order_guid=None)
    assert user_settings.load() == {"content_folder": "/x"}
    settings_file.write_text("not json")
    assert user_settings.load() == {}


def test_settings_default_location(monkeypatch):
    monkeypatch.delenv(user_settings.ENV_OVERRIDE, raising=False)
    path = user_settings.settings_path()
    assert path.endswith(user_settings.FILE_NAME) and user_settings.APP_FOLDER in path


# Client


class FakeApi(http.server.BaseHTTPRequestHandler):
    routes = {}
    requests = []

    def log_message(self, *args):
        pass

    def _answer(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else None
        FakeApi.requests.append((self.command, self.path, body))
        status, payload = self.routes.get(self.path, (404, {"error": "not_found", "message": "no route"}))
        if callable(payload):
            payload = payload(body)
        data = json.dumps(payload).encode() if not isinstance(payload, bytes) else payload
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = _answer
    do_POST = _answer


@pytest.fixture(scope="module")
def api():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeApi)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


@pytest.fixture(autouse=True)
def point_client_at(api, monkeypatch):
    monkeypatch.setenv(api_client.ENV_BASE_URL, api)
    FakeApi.routes = {}
    FakeApi.requests = []


def test_catalogue_fetch(api):
    FakeApi.routes["/api/addon/catalogue"] = (200, {"schema": 1, "addon": {"latest": "4.1.0"}, "packs": [{"key": "A", "name": "A", "versions": [{"version": [1, 0], "file": "A.hgpack", "min_addon": "4.0.0"}]}]})
    catalogue = api_client.fetch_catalogue()
    assert catalogue.get("A").latest().version == (1, 0)
    assert FakeApi.requests[0][0] == "GET"


def test_catalogue_bad_payload(api):
    FakeApi.routes["/api/addon/catalogue"] = (200, b"<html>")
    with pytest.raises(api_client.ApiError) as e:
        api_client.fetch_catalogue()
    assert e.value.code == "bad_response"


def test_activate_sends_versions_and_returns_answer(api):
    FakeApi.routes["/api/addon/activate"] = (200, lambda body: {"ok": True, "license": "commercial", "echo": body})
    answer = api_client.activate("ABC-123", "a@b.co", True)
    assert answer["license"] == "commercial"
    body = answer["echo"]
    assert body["order_guid"] == "ABC-123" and body["email"] == "a@b.co" and body["newsletter"] is True
    assert set(body) >= {"addon", "blender", "platform"}
    assert body["platform"].split("-")[0] in ("macos", "windows", "linux")


def test_server_errors_become_api_errors(api):
    FakeApi.routes["/api/addon/activate"] = (404, {"error": "not_found", "message": "No such order."})
    with pytest.raises(api_client.ApiError) as e:
        api_client.activate("x", "a@b.co")
    assert e.value.code == "not_found" and e.value.message == "No such order." and e.value.status == 404
    FakeApi.routes["/api/addon/activate"] = (403, {"error": "email_mismatch"})
    with pytest.raises(api_client.ApiError) as e:
        api_client.activate("x", "a@b.co")
    assert e.value.message == api_client.MESSAGES["email_mismatch"]
    FakeApi.routes["/api/addon/activate"] = (500, b"boom")
    with pytest.raises(api_client.ApiError) as e:
        api_client.activate("x", "a@b.co")
    assert e.value.code == "bad_response"


def test_content_urls(api):
    FakeApi.routes["/api/addon/content"] = (200, {"ok": True, "files": {"A": {"url": "http://x/A", "size": 5}}, "errors": {"B": "not_found"}})
    answer = api_client.content_urls(["A", "B"], "guid", "a@b.co", "0123456789abcdef")
    assert answer["files"]["A"]["url"] == "http://x/A" and answer["errors"] == {"B": "not_found"}
    body = FakeApi.requests[-1][2]
    assert body["packs"] == ["A", "B"] and body["rid"] == "0123456789abcdef" and body["order_guid"] == "guid"
    api_client.content_urls(["A"])
    assert "order_guid" not in FakeApi.requests[-1][2] and "rid" not in FakeApi.requests[-1][2]


def test_offline(monkeypatch):
    monkeypatch.setenv(api_client.ENV_BASE_URL, "http://127.0.0.1:9")
    with pytest.raises(api_client.ApiError) as e:
        api_client.fetch_catalogue()
    assert e.value.code == "offline"
