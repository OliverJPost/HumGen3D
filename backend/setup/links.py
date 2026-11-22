# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Links to humgen3d.com that the interface opens in the browser, and the
address of support. The one place either is written down."""
from typing import Optional
from urllib.parse import urlencode

BUY_URL = "https://humgen3d.com/pricing"
TRIAL_URL = "https://humgen3d.com/trial"
SUPPORT_EMAIL = "support@humgen3d.com"


def trial_url(rid: Optional[str] = None) -> str:
    """The install guide of a trial request, where its add-on zip is downloaded.

    An install from a zip is updated there: the newer zip, dragged into
    Blender, replaces the installed version and keeps its settings.
    """
    return TRIAL_URL + ("?" + urlencode({"r": rid}) if rid else "")


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
