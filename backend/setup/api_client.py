# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The requests the add-on makes to humgen3d.com.

Three calls: the public catalogue (the update check), the download URLs of
the free packs, which is the trial content, and the events of an install that
came from a trial link (`trial_events`). The packs of the full version are
not downloaded by the add-on: they are installed from the `.hgpack` files of
the purchase. Every call is plain `urllib`, blocking, and meant to run in a
thread; nothing here touches `bpy` except to read the version numbers it
sends along. Errors become `ApiError` with the server's code and message, or
a local code with a sentence for the user: `offline`, `timeout`, `tls` (a
certificate problem, often a proxy or security software in between), `proxy`
(the proxy wants a login), `unavailable` (any 5xx, whatever its body) and
`bad_response`. `TRANSIENT_CODES` are worth retrying.
"""
import json
import os
import platform
import socket
import ssl
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Sequence

from .catalogue import Catalogue, version_text
from .links import SUPPORT_EMAIL

DEFAULT_BASE_URL = "https://humgen3d.com"
ENV_BASE_URL = "HUMGEN_API_URL"
USER_AGENT = "HumGen3D-addon"
TIMEOUT = 20.0

MESSAGES = {
    "offline": "Can't reach humgen3d.com. Check your internet connection and try again. Your installed content works as usual.",
    "timeout": "humgen3d.com took too long to answer. Try again in a minute.",
    "tls": "A secure connection to humgen3d.com couldn't be made. A proxy or security software may be intercepting it.",
    "proxy": "Your network's proxy asks for a login. Sign in to it, or ask your IT department to allow humgen3d.com.",
    "unavailable": "humgen3d.com is having a problem right now. Try again in a few minutes.",
    "bad_response": f"humgen3d.com gave an unexpected answer. Try again later, or contact {SUPPORT_EMAIL}.",
    "rate_limited": "Too many downloads from this network. Try again in an hour.",
}

# Worth trying again
TRANSIENT_CODES = ("offline", "timeout", "unavailable", "tls", "proxy", "rate_limited", "bad_response")

# Per-pack codes in the `errors` of /api/addon/content
PACK_MESSAGES = {
    "license_required": "This pack comes with the full version. Install it from the files of your purchase.",
    "not_found": "This pack isn't offered for download any more.",
    "needs_newer_addon": "A newer Human Generator is needed for this content.",
    "unavailable": "This pack can't be downloaded right now. Try again in a few minutes.",
}
PACK_MESSAGE_DEFAULT = f"This pack can't be downloaded right now. Try again later, or contact {SUPPORT_EMAIL}."


class ApiError(Exception):
    def __init__(self, code: str, message: str = "", status: int = 0) -> None:
        self.code = code
        self.message = message or MESSAGES.get(code, MESSAGES["bad_response"])
        self.status = status
        super().__init__(f"{code}: {self.message}")

    @property
    def transient(self) -> bool:
        return self.code in TRANSIENT_CODES


def pack_error_message(code: str) -> str:
    """A sentence for a per-pack error code from /api/addon/content."""
    code = str(code or "")
    if code in PACK_MESSAGES:
        return PACK_MESSAGES[code]
    if code == "rate_limited":
        return MESSAGES[code]
    return PACK_MESSAGE_DEFAULT


def base_url() -> str:
    return os.environ.get(ENV_BASE_URL, DEFAULT_BASE_URL).rstrip("/")


def platform_tag() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
    names = {"darwin": "macos", "windows": "windows", "linux": "linux"}
    return f"{names.get(system, system)}-{arch}"


def client_info() -> Dict[str, str]:
    """The version fields every request carries."""
    try:
        from ...package import addon_version

        addon = version_text(addon_version())
    except Exception:  # noqa: BLE001  outside the add-on (tests)
        addon = "0.0.0"
    try:
        import bpy

        blender = version_text(bpy.app.version)
    except Exception:  # noqa: BLE001
        blender = "0.0.0"
    return {"addon": addon, "blender": blender, "platform": platform_tag()}


def user_agent() -> str:
    """The User-Agent of the API requests. The catalogue GET has no body, so
    this is how the server counts which versions run its daily check."""
    info = client_info()
    return f"{USER_AGENT}/{info['addon']} (Blender {info['blender']}; {info['platform']})"


def ssl_context() -> ssl.SSLContext:
    """The context for every https request, downloads included."""
    context = ssl.create_default_context()
    # Blender's Python on some Linux builds has no CA bundle; certifi, when
    # present, fills the gap
    if not context.get_ca_certs():
        try:
            import certifi

            context.load_verify_locations(certifi.where())
        except Exception:  # noqa: BLE001
            pass
    return context


_ssl_context = ssl_context  # the old name


def is_tls_error(error: BaseException) -> bool:
    """A certificate or handshake failure, also when urllib wrapped it."""
    reason = getattr(error, "reason", None)
    return isinstance(error, (ssl.SSLError, ssl.CertificateError)) or isinstance(reason, (ssl.SSLError, ssl.CertificateError))


def is_proxy_error(error: BaseException) -> bool:
    """An https proxy that refused the tunnel (407 and friends arrive as an OSError)."""
    text = str(getattr(error, "reason", None) or error)
    return "Tunnel connection failed" in text or "407" in text


def request_json(method: str, path: str, body: Optional[dict] = None, timeout: float = TIMEOUT) -> Dict[str, Any]:
    """One JSON request. Raises ApiError for transport and server errors."""
    url = path if path.startswith("http") else base_url() + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", user_agent())
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    context = ssl_context() if url.startswith("https") else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            text = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            text = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            text = ""
    except socket.timeout:
        raise ApiError("timeout") from None
    except (urllib.error.URLError, OSError) as e:
        if isinstance(getattr(e, "reason", None), socket.timeout) or "timed out" in str(e):
            raise ApiError("timeout") from None
        if is_tls_error(e):
            raise ApiError("tls") from None
        if is_proxy_error(e):
            raise ApiError("proxy") from None
        raise ApiError("offline") from None
    if status == 407:
        raise ApiError("proxy", status=status)
    if status >= 500:
        # Before parsing: a 5xx is often an HTML page from a proxy or the host
        raise ApiError("unavailable", _message_of(text), status)
    if status == 429:
        raise ApiError("rate_limited", _message_of(text), status)
    try:
        payload = json.loads(text) if text else {}
    except ValueError:
        raise ApiError("bad_response", status=status) from None
    if not isinstance(payload, dict):
        raise ApiError("bad_response", status=status)
    if status >= 400:
        raise ApiError(str(payload.get("error") or "bad_response"), str(payload.get("message") or ""), status)
    return payload


def _message_of(text: str) -> str:
    """The `message` of a JSON error body, or ""."""
    try:
        payload = json.loads(text)
    except ValueError:
        return ""
    return str(payload.get("message") or "") if isinstance(payload, dict) else ""


CATALOGUE_PATH = "/api/addon/catalogue"
TRIAL_PATH = "/api/trial"


def fetch_catalogue() -> Catalogue:
    payload = request_json("GET", CATALOGUE_PATH)
    try:
        return Catalogue.from_dict(payload)
    except (ValueError, KeyError, TypeError):
        raise ApiError("bad_response") from None


def send_event(event: str, rid: str) -> None:
    """One event of an install that came from a trial link: `setup_opened`,
    `trial_installed` or `full_installed`, with its trial request id and the
    versions every request names. `trial_events` decides when; nothing else
    calls this."""
    request_json("POST", TRIAL_PATH, dict(client_info(), event=event, trial=rid))


def content_urls(keys: Sequence[str], rid: str = "", retry: str = "") -> Dict[str, Any]:
    """Download URLs for free packs: {"files": {key: {...}}, "errors": {key:
    code}}. `rid` is the trial request id of an install that came from a trial
    link. `retry` is the error code of the attempt this request follows, so
    the server can count failed downloads."""
    body: Dict[str, Any] = dict(client_info(), packs=list(keys))
    if rid:
        body["rid"] = rid
    if retry:
        body["retry"] = retry[:32]
    payload = request_json("POST", "/api/addon/content", body)
    files = payload.get("files")
    errors = payload.get("errors") or {}
    if not isinstance(files, dict) or not isinstance(errors, dict):
        raise ApiError("bad_response")
    return dict(files=files, errors=errors)


def python_tag() -> str:
    return "%d.%d" % sys.version_info[:2]
