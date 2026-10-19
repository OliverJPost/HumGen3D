# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The requests the add-on makes to humgen3d.com.

Three calls: the public catalogue, the activation of an order, and the
download URLs of packs. Every call is plain `urllib`, blocking, and meant to
run in a thread; nothing here touches `bpy` except to read the version
numbers it sends along. Errors become `ApiError` with the server's code and
message, or a local code (`offline`, `timeout`, `bad_response`) with a
sentence for the user.
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

MESSAGES = {
    "offline": "Could not reach humgen3d.com. Check your internet connection and try again.",
    "timeout": "humgen3d.com took too long to answer. Try again in a minute.",
    "bad_response": "humgen3d.com gave an unexpected answer. Try again later, or contact support@humgen3d.com.",
    "unavailable": "The activation service is unavailable right now. Try again in a minute.",
    "not_found": "We could not find an order with this GUID. Check the order email from Superhive, or contact support@humgen3d.com.",
    "email_mismatch": "This email does not match the order.",
    "refunded": "This order was refunded.",
    "rate_limited": "Too many attempts. Wait a while before trying again.",
    "invalid": "The order GUID or email is not valid.",
}


class ApiError(Exception):
    def __init__(self, code: str, message: str = "", status: int = 0) -> None:
        self.code = code
        self.message = message or MESSAGES.get(code, MESSAGES["bad_response"])
        self.status = status
        super().__init__(f"{code}: {self.message}")


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


def _ssl_context() -> ssl.SSLContext:
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


def request_json(method: str, path: str, body: Optional[dict] = None, timeout: float = TIMEOUT) -> Dict[str, Any]:
    """One JSON request. Raises ApiError for transport and server errors."""
    url = path if path.startswith("http") else base_url() + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    context = _ssl_context() if url.startswith("https") else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            text = resp.read().decode("utf-8")
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            text = e.read().decode("utf-8")
        except Exception:  # noqa: BLE001
            text = ""
    except socket.timeout:
        raise ApiError("timeout") from None
    except (urllib.error.URLError, OSError) as e:
        if isinstance(getattr(e, "reason", None), socket.timeout) or "timed out" in str(e):
            raise ApiError("timeout") from None
        raise ApiError("offline") from None
    try:
        payload = json.loads(text) if text else {}
    except ValueError:
        raise ApiError("bad_response", status=status) from None
    if not isinstance(payload, dict):
        raise ApiError("bad_response", status=status)
    if status >= 400:
        code = str(payload.get("error") or ("unavailable" if status >= 500 else "bad_response"))
        raise ApiError(code, str(payload.get("message") or ""), status)
    return payload


def fetch_catalogue() -> Catalogue:
    payload = request_json("GET", "/api/addon/catalogue")
    try:
        return Catalogue.from_dict(payload)
    except (ValueError, KeyError, TypeError):
        raise ApiError("bad_response") from None


def activate(order_guid: str, email: str, newsletter: bool = False) -> Dict[str, Any]:
    """Check an order. Returns the server's answer ({"ok": True, "license": ...})."""
    body = dict(client_info(), order_guid=order_guid, email=email, newsletter=bool(newsletter))
    return request_json("POST", "/api/addon/activate", body)


def content_urls(keys: Sequence[str], order_guid: str = "", email: str = "", rid: str = "") -> Dict[str, Any]:
    """Download URLs for packs: {"files": {key: {...}}, "errors": {key: code}}."""
    body: Dict[str, Any] = dict(client_info(), packs=list(keys))
    if order_guid:
        body["order_guid"] = order_guid
        body["email"] = email
    if rid:
        body["rid"] = rid
    payload = request_json("POST", "/api/addon/content", body)
    files = payload.get("files")
    if not isinstance(files, dict):
        raise ApiError("bad_response")
    return {"files": files, "errors": payload.get("errors") or {}}


def python_tag() -> str:
    return "%d.%d" % sys.version_info[:2]
