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
    assert user_settings.update(content_folder="/x", trial_rid="abc")
    assert user_settings.get("trial_rid") == "abc"
    assert user_settings.content_folder() == "/x"
    user_settings.update(trial_rid=None)
    assert user_settings.load() == {"content_folder": "/x"}
    settings_file.write_text("not json")
    assert user_settings.load() == {}


def test_nothing_about_a_license_is_kept():
    """The settings file holds the folder, the trial id and the update
    check's bookkeeping. No key, order or email: this build has no such thing."""
    assert not any(hasattr(user_settings, name) for name in ("credential", "save_credential", "forget_credential", "update_license"))


def test_setup_shown(settings_file):
    assert not user_settings.setup_shown()
    user_settings.mark_setup_shown()
    assert user_settings.setup_shown()


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
        self.send_header("Content-Type", "text/html" if isinstance(payload, bytes) and payload.startswith(b"<") else "application/json")
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


def test_content_request_sends_versions(api):
    FakeApi.routes["/api/addon/content"] = (200, lambda body: {"ok": True, "files": {}, "errors": {}})
    api_client.content_urls(["Trial_Content"])
    body = FakeApi.requests[-1][2]
    assert set(body) == {"addon", "blender", "platform", "packs"}
    assert body["platform"].split("-")[0] in ("macos", "windows", "linux")


def test_server_errors_become_api_errors(api):
    FakeApi.routes["/api/addon/content"] = (404, {"error": "not_found", "message": "No such pack."})
    with pytest.raises(api_client.ApiError) as e:
        api_client.content_urls(["A"])
    assert e.value.code == "not_found" and e.value.message == "No such pack." and e.value.status == 404
    # A code this add-on has no sentence for still gets one
    FakeApi.routes["/api/addon/content"] = (403, {"error": "something_new"})
    with pytest.raises(api_client.ApiError) as e:
        api_client.content_urls(["A"])
    assert e.value.code == "something_new" and e.value.message == api_client.MESSAGES["bad_response"]
    FakeApi.routes["/api/addon/content"] = (500, b"boom")
    with pytest.raises(api_client.ApiError) as e:
        api_client.content_urls(["A"])
    assert e.value.code == "unavailable"


def test_5xx_html_is_unavailable(api):
    """A proxy's or the host's error page is "unavailable", not "unexpected answer"."""
    for status in (500, 502, 503, 504):
        FakeApi.routes["/api/addon/content"] = (status, b"<html><body>Bad gateway</body></html>")
        with pytest.raises(api_client.ApiError) as e:
            api_client.content_urls(["A"])
        assert e.value.code == "unavailable" and e.value.status == status and e.value.transient
        assert e.value.message == api_client.MESSAGES["unavailable"]
    FakeApi.routes["/api/addon/content"] = (503, {"error": "unavailable", "message": "Down for maintenance."})
    with pytest.raises(api_client.ApiError) as e:
        api_client.content_urls(["A"])
    assert e.value.code == "unavailable" and e.value.message == "Down for maintenance."


def test_proxy_and_rate_limit(api):
    FakeApi.routes["/api/addon/content"] = (407, b"<html>Proxy Authentication Required</html>")
    with pytest.raises(api_client.ApiError) as e:
        api_client.content_urls(["A"])
    assert e.value.code == "proxy" and e.value.transient
    FakeApi.routes["/api/addon/content"] = (429, b"<html>slow down</html>")
    with pytest.raises(api_client.ApiError) as e:
        api_client.content_urls(["A"])
    assert e.value.code == "rate_limited" and e.value.message == api_client.MESSAGES["rate_limited"]


def test_tls_error(api, monkeypatch):
    """https against a plain http server fails the handshake: a tls error, not "offline"."""
    monkeypatch.setenv(api_client.ENV_BASE_URL, api.replace("http://", "https://"))
    with pytest.raises(api_client.ApiError) as e:
        api_client.fetch_catalogue()
    assert e.value.code == "tls" and "secure connection" in e.value.message


def test_messages():
    for code in api_client.TRANSIENT_CODES:
        assert api_client.MESSAGES[code] and "!" not in api_client.MESSAGES[code]
    # Nothing in this client is about a license, a key or an order
    words = " ".join(list(api_client.MESSAGES.values()) + list(api_client.PACK_MESSAGES.values())).lower()
    assert not any(word in words for word in ("license key", "licence", "order guid", "activate", "superhive"))
    assert not hasattr(api_client, "activate") and not hasattr(api_client, "CREDENTIAL_CODES")
    assert api_client.ssl_context() is not None


def test_pack_error_message():
    assert "full version" in api_client.pack_error_message("license_required")
    assert api_client.pack_error_message("not_found") == api_client.PACK_MESSAGES["not_found"]
    assert api_client.pack_error_message("rate_limited") == api_client.MESSAGES["rate_limited"]
    assert api_client.pack_error_message("something_new") == api_client.PACK_MESSAGE_DEFAULT
    assert api_client.pack_error_message("") == api_client.PACK_MESSAGE_DEFAULT


def test_content_urls(api):
    FakeApi.routes["/api/addon/content"] = (200, {"ok": True, "files": {"A": {"url": "http://x/A", "size": 5}}, "errors": {"B": "not_found"}})
    answer = api_client.content_urls(["A", "B"], "0123456789abcdef")
    assert answer == {"files": {"A": {"url": "http://x/A", "size": 5}}, "errors": {"B": "not_found"}}
    body = FakeApi.requests[-1][2]
    assert body["packs"] == ["A", "B"] and body["rid"] == "0123456789abcdef"
    # Never a key, an order or an email: there is none to send
    assert not {"order_guid", "licence", "email", "newsletter"} & set(body)
    api_client.content_urls(["A"])
    assert "rid" not in FakeApi.requests[-1][2] and "retry" not in FakeApi.requests[-1][2]
    # After a failed attempt the request says why, for the server's count of failed downloads
    api_client.content_urls(["A"], retry="checksum")
    assert FakeApi.requests[-1][2]["retry"] == "checksum"
    FakeApi.routes["/api/addon/content"] = (200, {"ok": True, "files": [], "errors": {}})
    with pytest.raises(api_client.ApiError) as e:
        api_client.content_urls(["A"])
    assert e.value.code == "bad_response"


def test_user_agent_names_the_versions():
    """The catalogue GET has no body: the User-Agent is how the server counts versions."""
    info = api_client.client_info()
    assert api_client.user_agent() == f"HumGen3D-addon/{info['addon']} (Blender {info['blender']}; {info['platform']})"


def test_offline(monkeypatch):
    monkeypatch.setenv(api_client.ENV_BASE_URL, "http://127.0.0.1:9")
    with pytest.raises(api_client.ApiError) as e:
        api_client.fetch_catalogue()
    assert e.value.code == "offline"
