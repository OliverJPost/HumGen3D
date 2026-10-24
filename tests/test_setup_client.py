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


def test_credential_kind():
    assert user_settings.credential_kind("HG3D-ABCDE-FGHIJ") == "key"
    assert user_settings.credential_kind(" hg3d abcde ") == "key"
    assert user_settings.credential_kind("3f2a9c1e-0000-4bcd-9e1f-1234567890ab") == "superhive"
    assert user_settings.credential_kind("") == "superhive"


def test_credential_helpers(settings_file):
    assert user_settings.credential() is None
    user_settings.update(content_folder="/x", newsletter=True, trial_rid="r1")
    assert user_settings.save_credential(" 3f2a-1a2b ", "jane@example.com", "personal", "https://humgen3d.com/upgrade?x=1")
    cred = user_settings.credential()
    assert cred.value == "3f2a-1a2b" and cred.email == "jane@example.com" and cred.kind == "superhive"
    assert cred.status == "ok" and cred.license == "personal" and cred.is_personal
    assert cred.upgrade_url.startswith("https://") and cred.error_code == ""
    assert cred.masked == "\u2022\u2022\u2022\u20221a2b"
    assert cred.masked_email == "j\u2022\u2022\u2022@example.com"
    assert user_settings.get("activated_at")
    # A rejection keeps the credential, so the form can show it again
    assert user_settings.mark_credential_rejected("refunded", "This order was refunded.")
    cred = user_settings.credential()
    assert cred.value == "3f2a-1a2b" and cred.email == "jane@example.com"
    assert cred.status == "rejected" and cred.rejected and cred.error_code == "refunded" and cred.error_message
    # An answer without a tier changes nothing; one with a tier replaces it
    assert user_settings.update_license(None, None)
    assert user_settings.credential().license == "personal"
    user_settings.update_license("commercial", None)
    cred = user_settings.credential()
    assert cred.license == "commercial" and not cred.is_personal and cred.upgrade_url == ""
    # Saving again clears the rejection
    user_settings.save_credential("HG3D-AAAA-BBBB", "jane@example.com")
    cred = user_settings.credential()
    assert cred.kind == "key" and cred.status == "ok" and cred.error_code == "" and cred.license is None
    # Forgetting removes only the credential keys
    assert user_settings.forget_credential()
    assert user_settings.credential() is None
    assert user_settings.load() == {"content_folder": "/x", "newsletter": True, "trial_rid": "r1"}


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


def test_activate_sends_versions_and_returns_answer(api):
    FakeApi.routes["/api/addon/activate"] = (200, lambda body: {"ok": True, "license": "commercial", "echo": body})
    answer = api_client.activate("ABC-123", "a@b.co", True)
    assert answer["license"] == "commercial" and answer["upgrade_url"] is None
    body = answer["echo"]
    assert body["order_guid"] == "ABC-123" and body["licence"] == "ABC-123"
    assert body["email"] == "a@b.co" and body["newsletter"] is True and "rid" not in body
    assert set(body) >= {"addon", "blender", "platform"}
    assert body["platform"].split("-")[0] in ("macos", "windows", "linux")


def test_activate_with_key_rid_and_tier(api):
    FakeApi.routes["/api/addon/activate"] = (200, lambda body: {"ok": True, "license": "personal", "upgrade_url": "https://humgen3d.com/upgrade?o=1", "echo": body})
    answer = api_client.activate(" HG3D-AAAA-BBBB ", "a@b.co", rid="0123456789abcdef")
    assert answer["license"] == "personal" and answer["upgrade_url"] == "https://humgen3d.com/upgrade?o=1"
    body = answer["echo"]
    assert body["order_guid"] == body["licence"] == "HG3D-AAAA-BBBB" and body["rid"] == "0123456789abcdef"
    # The old keyword still works
    answer = api_client.activate(order_guid="OLD", email="a@b.co")
    assert answer["echo"]["order_guid"] == "OLD"
    # Unknown tiers and odd upgrade links are dropped
    FakeApi.routes["/api/addon/activate"] = (200, {"ok": True, "license": "gold", "upgrade_url": "javascript:x"})
    answer = api_client.activate("x", "a@b.co")
    assert answer["license"] is None and answer["upgrade_url"] is None


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
    assert e.value.code == "unavailable"
    FakeApi.routes["/api/addon/activate"] = (200, {"ok": True, "unexpected": [1]})
    assert api_client.activate("x", "a@b.co")["license"] is None


def test_5xx_html_is_unavailable(api):
    """A proxy's or the host's error page is "unavailable", not "unexpected answer"."""
    for status in (500, 502, 503, 504):
        FakeApi.routes["/api/addon/activate"] = (status, b"<html><body>Bad gateway</body></html>")
        with pytest.raises(api_client.ApiError) as e:
            api_client.activate("x", "a@b.co")
        assert e.value.code == "unavailable" and e.value.status == status and e.value.transient
        assert e.value.message == api_client.MESSAGES["unavailable"]
    FakeApi.routes["/api/addon/activate"] = (503, {"error": "unavailable", "message": "Down for maintenance."})
    with pytest.raises(api_client.ApiError) as e:
        api_client.activate("x", "a@b.co")
    assert e.value.code == "unavailable" and e.value.message == "Down for maintenance."


def test_proxy_and_rate_limit(api):
    FakeApi.routes["/api/addon/activate"] = (407, b"<html>Proxy Authentication Required</html>")
    with pytest.raises(api_client.ApiError) as e:
        api_client.activate("x", "a@b.co")
    assert e.value.code == "proxy" and e.value.transient
    FakeApi.routes["/api/addon/activate"] = (429, b"<html>slow down</html>")
    with pytest.raises(api_client.ApiError) as e:
        api_client.activate("x", "a@b.co")
    assert e.value.code == "rate_limited" and e.value.message == api_client.MESSAGES["rate_limited"]


def test_tls_error(api, monkeypatch):
    """https against a plain http server fails the handshake: a tls error, not "offline"."""
    monkeypatch.setenv(api_client.ENV_BASE_URL, api.replace("http://", "https://"))
    with pytest.raises(api_client.ApiError) as e:
        api_client.fetch_catalogue()
    assert e.value.code == "tls" and "secure connection" in e.value.message


def test_error_code_groups():
    assert set(api_client.CREDENTIAL_CODES) == {"not_found", "email_mismatch", "refunded", "revoked"}
    assert not set(api_client.CREDENTIAL_CODES) & set(api_client.TRANSIENT_CODES)
    assert api_client.ApiError("refunded").about_credential and not api_client.ApiError("refunded").transient
    for code in api_client.CREDENTIAL_CODES + api_client.TRANSIENT_CODES + ("pending", "invalid"):
        assert api_client.MESSAGES[code] and "!" not in api_client.MESSAGES[code]
    assert "support@humgen3d.com" in api_client.MESSAGES["not_found"] and "license key" in api_client.MESSAGES["not_found"] and "order GUID" in api_client.MESSAGES["not_found"]
    assert api_client.ssl_context() is not None


def test_pack_error_message():
    assert "license key" in api_client.pack_error_message("license_required")
    assert api_client.pack_error_message("not_found") != api_client.MESSAGES["not_found"]
    assert api_client.pack_error_message("refunded") == api_client.MESSAGES["refunded"]
    assert api_client.pack_error_message("something_new") == api_client.PACK_MESSAGE_DEFAULT
    assert api_client.pack_error_message("") == api_client.PACK_MESSAGE_DEFAULT


def test_content_urls(api):
    FakeApi.routes["/api/addon/content"] = (200, {"ok": True, "files": {"A": {"url": "http://x/A", "size": 5}}, "errors": {"B": "not_found"}})
    answer = api_client.content_urls(["A", "B"], "guid", "a@b.co", "0123456789abcdef")
    assert answer["files"]["A"]["url"] == "http://x/A" and answer["errors"] == {"B": "not_found"}
    assert answer["license"] is None and answer["upgrade_url"] is None
    body = FakeApi.requests[-1][2]
    assert body["packs"] == ["A", "B"] and body["rid"] == "0123456789abcdef"
    assert body["order_guid"] == body["licence"] == "guid" and body["email"] == "a@b.co"
    api_client.content_urls(["A"])
    assert "order_guid" not in FakeApi.requests[-1][2] and "licence" not in FakeApi.requests[-1][2] and "rid" not in FakeApi.requests[-1][2]
    # The tier comes along on every call, so an upgrade shows without a new activation
    FakeApi.routes["/api/addon/content"] = (200, {"ok": True, "files": {}, "errors": {}, "license": "commercial"})
    answer = api_client.content_urls(["A"], credential="guid", email="a@b.co")
    assert answer["license"] == "commercial" and answer["upgrade_url"] is None
    api_client.content_urls(["A"], order_guid="old-name", email="a@b.co")
    assert FakeApi.requests[-1][2]["order_guid"] == "old-name"
    FakeApi.routes["/api/addon/content"] = (200, {"ok": True, "files": [], "errors": {}})
    with pytest.raises(api_client.ApiError) as e:
        api_client.content_urls(["A"])
    assert e.value.code == "bad_response"


def test_offline(monkeypatch):
    monkeypatch.setenv(api_client.ENV_BASE_URL, "http://127.0.0.1:9")
    with pytest.raises(api_client.ApiError) as e:
        api_client.fetch_catalogue()
    assert e.value.code == "offline"
