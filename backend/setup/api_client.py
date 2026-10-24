# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The requests the add-on makes to humgen3d.com.

Three calls: the public catalogue, the activation of a credential (a
Superhive order GUID or a license key), and the download URLs of packs. Every
call is plain `urllib`, blocking, and meant to run in a thread; nothing here
touches `bpy` except to read the version numbers it sends along. Errors become
`ApiError` with the server's code and message, or a local code with a
sentence for the user: `offline`, `timeout`, `tls` (a certificate problem,
often a proxy or security software in between), `proxy` (the proxy wants a
login), `unavailable` (any 5xx, whatever its body) and `bad_response`.

`CREDENTIAL_CODES` are definitive answers about the credential: the caller
marks it rejected (and keeps it). `TRANSIENT_CODES` say nothing about it and
are worth retrying.
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

DEFAULT_BASE_URL = "https://humgen3d.com"
ENV_BASE_URL = "HUMGEN_API_URL"
USER_AGENT = "HumGen3D-addon"
TIMEOUT = 20.0
SUPPORT_EMAIL = "support@humgen3d.com"

MESSAGES = {
    "offline": "Can't reach humgen3d.com. Check your internet connection and try again. Your installed content works as usual.",
    "timeout": "humgen3d.com took too long to answer. Try again in a minute.",
    "tls": "A secure connection to humgen3d.com couldn't be made. A proxy or security software may be intercepting it.",
    "proxy": "Your network's proxy asks for a login. Sign in to it, or ask your IT department to allow humgen3d.com.",
    "unavailable": "humgen3d.com is having a problem right now. Try again in a few minutes.",
    "bad_response": "humgen3d.com gave an unexpected answer. Try again later, or contact support@humgen3d.com.",
    "not_found": "We couldn't find this license key. Bought on Superhive? Copy the order ID from your order email again, or contact support@humgen3d.com.",
    "email_mismatch": "This license is linked to a different email. Use the email you bought with.",
    "refunded": "This purchase was refunded, so it can't download content. Content you already installed is not affected.",
    "revoked": "This license is no longer active. Contact support@humgen3d.com if you think this is a mistake.",
    "pending": "This purchase is still being processed. Try again in a few minutes.",
    "rate_limited": "Too many attempts from this network. Try again in an hour.",
    "invalid": "Enter your license key and the email you bought with.",
}

# Definitive answers about the credential: mark it rejected, keep it stored
CREDENTIAL_CODES = ("not_found", "email_mismatch", "refunded", "revoked")
# Say nothing about the credential; worth trying again
TRANSIENT_CODES = ("offline", "timeout", "unavailable", "tls", "proxy", "rate_limited", "bad_response")

# Per-pack codes in the `errors` of /api/addon/content
PACK_MESSAGES = {
    "license_required": "This pack needs a license. Enter your license key to download it.",
    "not_found": "This pack isn't offered for download any more.",
    "needs_newer_addon": "A newer Human Generator is needed for this content.",
    "unavailable": "This pack can't be downloaded right now. Try again in a few minutes.",
}
PACK_MESSAGE_DEFAULT = "This pack can't be downloaded right now. Try again later, or contact support@humgen3d.com."


class ApiError(Exception):
    def __init__(self, code: str, message: str = "", status: int = 0) -> None:
        self.code = code
        self.message = message or MESSAGES.get(code, MESSAGES["bad_response"])
        self.status = status
        super().__init__(f"{code}: {self.message}")

    @property
    def about_credential(self) -> bool:
        """A definitive answer about the credential (see CREDENTIAL_CODES)."""
        return self.code in CREDENTIAL_CODES

    @property
    def transient(self) -> bool:
        return self.code in TRANSIENT_CODES


def pack_error_message(code: str) -> str:
    """A sentence for a per-pack error code from /api/addon/content."""
    code = str(code or "")
    if code in PACK_MESSAGES:
        return PACK_MESSAGES[code]
    if code in CREDENTIAL_CODES or code in ("pending", "rate_limited"):
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
    req.add_header("User-Agent", USER_AGENT)
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


def fetch_catalogue() -> Catalogue:
    payload = request_json("GET", "/api/addon/catalogue")
    try:
        return Catalogue.from_dict(payload)
    except (ValueError, KeyError, TypeError):
        raise ApiError("bad_response") from None


def _credential_fields(credential: str) -> Dict[str, str]:
    # `order_guid` is the field name for good; `licence` is its alias for
    # servers that tell keys and orders apart
    value = credential.strip()
    return {"order_guid": value, "licence": value}


def _tier(payload: Dict[str, Any]) -> Dict[str, Optional[str]]:
    license = payload.get("license")
    upgrade_url = payload.get("upgrade_url")
    return {
        "license": license if license in ("personal", "commercial") else None,
        "upgrade_url": upgrade_url if isinstance(upgrade_url, str) and upgrade_url.startswith("http") else None,
    }


def activate(credential: str = "", email: str = "", newsletter: bool = False, rid: str = "", order_guid: str = "") -> Dict[str, Any]:
    """Check a credential (order GUID or licence key). Returns the server's
    answer: {"ok": True, "license": "personal"|"commercial"|None,
    "upgrade_url": ...}. `order_guid=` is the old name of `credential`."""
    body: Dict[str, Any] = dict(client_info(), email=email.strip(), newsletter=bool(newsletter))
    body.update(_credential_fields(credential or order_guid))
    if rid:
        body["rid"] = rid
    payload = request_json("POST", "/api/addon/activate", body)
    payload.update(_tier(payload))
    return payload


def content_urls(keys: Sequence[str], credential: str = "", email: str = "", rid: str = "", order_guid: str = "") -> Dict[str, Any]:
    """Download URLs for packs: {"files": {key: {...}}, "errors": {key: code},
    "license": tier or None, "upgrade_url": url or None}. `order_guid=` is
    the old name of `credential`."""
    body: Dict[str, Any] = dict(client_info(), packs=list(keys))
    credential = credential or order_guid
    if credential:
        body.update(_credential_fields(credential))
        body["email"] = email.strip()
    if rid:
        body["rid"] = rid
    payload = request_json("POST", "/api/addon/content", body)
    files = payload.get("files")
    errors = payload.get("errors") or {}
    if not isinstance(files, dict) or not isinstance(errors, dict):
        raise ApiError("bad_response")
    return dict(files=files, errors=errors, **_tier(payload))


def python_tag() -> str:
    return "%d.%d" % sys.version_info[:2]
