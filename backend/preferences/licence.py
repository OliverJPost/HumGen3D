# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""What the licence row of the preferences shows, apart from the drawing.

The credential is the Superhive order ID or licence key the user activated
with, kept in the settings file (`backend/setup/user_settings.py`). The row
shows it masked, with the tier the server reported. Plain data in, plain data
out, so it can be tested without Blender's interface.
"""
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlencode

SUPPORT_EMAIL = "support@humgen3d.com"

TIER_LABELS = {
    "personal": "Personal licence",
    "commercial": "Commercial licence",
}


@dataclass
class LicenceRow:
    tier: str
    """"Personal licence", "Commercial licence" or "" when the server didn't say."""
    summary: str
    """The masked credential and email, "Order ••••1a2b · j•••@example.com"."""
    upgrade: bool
    """Whether to offer the upgrade to a commercial licence."""
    rejected: bool
    """Whether the server turned the credential down on its last use."""
    message: str
    """Why it was turned down, for the alert row. "" when not rejected."""


def licence_row(credential: Optional[Any]) -> Optional[LicenceRow]:
    """The row for `user_settings.credential()`, None when nothing is stored."""
    if credential is None or not getattr(credential, "value", ""):
        return None
    kind = "Licence key" if credential.kind == "key" else "Order"
    summary = f"{kind} {credential.masked}"
    if credential.email:
        summary += f" · {credential.masked_email}"
    rejected = credential.status == "rejected"
    message = ""
    if rejected:
        message = credential.error_message or "This order or licence key was not accepted."
    return LicenceRow(
        tier=TIER_LABELS.get(credential.license or "", ""),
        summary=summary,
        upgrade=bool(credential.is_personal) and not rejected,
        rejected=rejected,
        message=message,
    )


def support_url(code: str = "") -> str:
    """A mail to support about the licence, with the error code in the subject."""
    subject = "Human Generator licence" + (f" ({code})" if code else "")
    return f"mailto:{SUPPORT_EMAIL}?subject=" + subject.replace(" ", "%20")


BUY_URL = "https://humgen3d.com/pricing"


def buy_url(panel: str, rid: Optional[str] = None) -> str:
    """The pricing page for a "Buy" button of the trial.

    `panel` (utm_content) tells the buttons apart, `rid` is the trial request
    id, so a purchase can be linked to the trial it came from.
    """
    params = {
        "utm_source": "addon",
        "utm_medium": "ui_link",
        "utm_campaign": "trial_click",
        "utm_content": panel,
    }
    if rid:
        params["hg_rid"] = rid
    return BUY_URL + "?" + urlencode(params)
