# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""A small settings file outside Blender.

Blender keeps add-on preferences per package name and per Blender version, so
the content folder was lost whenever someone moved from the legacy add-on to
the extension, or from Blender 4.2 to 4.3. The things that must survive that
live here instead: the content folder, the order used for activation and the
trial request id. The file is plain JSON in the user's application support
folder, one per user, shared by every Blender version.

Keys in use:
    content_folder   the folder the packs are installed in
    order_guid       the credential the user activated with: a Superhive
                     order GUID or a licence key starting with HG3D- (the
                     key name stays for the files older versions wrote)
    email            the address they entered with it
    license          "personal" or "commercial", as the server last answered
    upgrade_url      where a Personal owner upgrades, as the server answered
    activated_at     ISO time of the last successful activation
    credential_status        "ok", or "rejected" when the server turned the
                     stored credential down (it is kept, to prefill the form)
    credential_error_code    the server's code for that rejection
    credential_error_message its sentence for it
    newsletter       whether they ticked "updates and offers"
    terms_accepted_at ISO time the licence and privacy policy were accepted
    trial_rid        the trial request id found in the extension repository URL
    setup_shown_at   ISO time the setup opened by itself (it does so once)
    catalogue_checked_at  epoch seconds of the last successful catalogue fetch
    catalogue_failed_at   epoch seconds of the last failed one (backoff)
"""
import json
import os
import platform
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

APP_FOLDER = "HumGen3D"
FILE_NAME = "settings.json"
ENV_OVERRIDE = "HUMGEN_SETTINGS_FILE"

_lock = threading.Lock()


def settings_folder() -> str:
    """The per-user, per-OS folder the settings and caches live in."""
    system = platform.system()
    if system == "Darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif system == "Windows":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP_FOLDER)


def settings_path() -> str:
    override = os.environ.get(ENV_OVERRIDE)
    if override:
        return override
    return os.path.join(settings_folder(), FILE_NAME)


def load() -> Dict[str, Any]:
    """The settings, or an empty dict when there is no file or it is unreadable."""
    path = settings_path()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(data: Dict[str, Any]) -> bool:
    """Write the whole settings dict. False when the folder is not writable."""
    path = settings_path()
    with _lock:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".settings-", suffix=".json", dir=os.path.dirname(path))
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
            os.replace(tmp, path)
        except OSError:
            return False
    return True


def get(key: str, default: Any = None) -> Any:
    return load().get(key, default)


def update(**values: Any) -> bool:
    """Set some keys and keep the rest. A value of None removes the key."""
    data = load()
    for key, value in values.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    return save(data)


def content_folder() -> Optional[str]:
    folder = get("content_folder")
    return folder if isinstance(folder, str) and folder else None


# The credential


KEY_PREFIX = "HG3D-"
CREDENTIAL_KEYS = (
    "order_guid",
    "email",
    "license",
    "upgrade_url",
    "activated_at",
    "credential_status",
    "credential_error_code",
    "credential_error_message",
)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def credential_kind(value: str) -> str:
    """"key" for a licence key (HG3D-..., dashes and spaces optional), else
    "superhive". An order GUID is hexadecimal, so it never starts with HG3D."""
    compact = re.sub(r"[\s-]", "", value or "").upper()
    return "key" if compact.startswith(KEY_PREFIX.rstrip("-")) else "superhive"


@dataclass
class Credential:
    value: str
    email: str
    kind: str
    license: Optional[str]
    status: str
    error_code: str
    error_message: str
    upgrade_url: str

    @property
    def masked(self) -> str:
        """The last four characters, for showing which credential is stored."""
        tail = re.sub(r"[\s-]", "", self.value)[-4:]
        return "\u2022\u2022\u2022\u2022" + tail

    @property
    def masked_email(self) -> str:
        name, at, domain = self.email.partition("@")
        if not at:
            return self.email[:1] + "\u2022\u2022\u2022" if self.email else ""
        return name[:1] + "\u2022\u2022\u2022@" + domain

    @property
    def is_personal(self) -> bool:
        return self.license == "personal"

    @property
    def rejected(self) -> bool:
        return self.status == "rejected"


def credential() -> Optional[Credential]:
    """The stored credential, or None when the user never activated."""
    data = load()
    value = data.get("order_guid")
    if not isinstance(value, str) or not value:
        return None

    def text(key: str) -> str:
        found = data.get(key)
        return found if isinstance(found, str) else ""

    return Credential(
        value=value,
        email=text("email"),
        kind=credential_kind(value),
        license=text("license") or None,
        status=text("credential_status") or "ok",
        error_code=text("credential_error_code"),
        error_message=text("credential_error_message"),
        upgrade_url=text("upgrade_url"),
    )


def save_credential(value: str, email: str, license: Optional[str] = None, upgrade_url: Optional[str] = None) -> bool:
    """Store a credential the server accepted, with what it said about it."""
    return update(
        order_guid=value.strip(),
        email=email.strip(),
        license=license or None,
        upgrade_url=upgrade_url or None,
        activated_at=_now_iso(),
        credential_status="ok",
        credential_error_code=None,
        credential_error_message=None,
    )


def mark_credential_rejected(code: str, message: str) -> bool:
    """The server turned the stored credential down. It stays stored, so the
    form can show it again; only the status changes."""
    return update(credential_status="rejected", credential_error_code=code or None, credential_error_message=message or None)


def update_license(license: Optional[str], upgrade_url: Optional[str]) -> bool:
    """Store the tier a later answer reported. Nothing changes when the
    answer had no tier, so an older server never erases it."""
    if not license:
        return True
    return update(license=license, upgrade_url=upgrade_url or None)


def forget_credential() -> bool:
    """Remove the credential from this computer. Installed content and the
    other settings stay."""
    return update(**{key: None for key in CREDENTIAL_KEYS})


def mark_setup_shown() -> bool:
    return update(setup_shown_at=_now_iso())


def setup_shown() -> bool:
    return bool(get("setup_shown_at"))
