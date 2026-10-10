# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Links from the interface to the documentation website.

Every "Documentation" and "Learn more" button goes through `docs_url`, so the
site can move by changing `DOCS_URL`. Pages are named by their URL path on the
site, which is the folder and file name of the page in `docs/` in lower case
with dashes: `docs/Process/Bake Textures.md` is "process/bake-textures". An
anchor can follow it: "process/output#processed-copies".
"""

from typing import Any, Mapping, Optional
from urllib.parse import urlencode

DOCS_URL = "https://humgen3d.com/docs/"
# Where the "Give feedback" button of the Process tab goes
FEEDBACK_URL = "https://humgen3d.com/feedback/process"
# The switch for every early-access notice and feedback button of the process
# system, set to False when it leaves early access
EARLY_ACCESS = True


def docs_url(page: str = "") -> str:
    """The URL of a page of the documentation.

    Args:
        page (str): Path of the page on the site, "" for the start page.
    """
    return DOCS_URL + page.strip("/")


def feedback_url(params: Optional[Mapping[str, Any]] = None, **more: Any) -> str:
    """The feedback page, with where the button is as query string.

    Args:
        params (Optional[Mapping[str, Any]]): Query parameters, for names that
            are Python keywords like "from". None values are left out.
        more (Any): Query parameters as keyword arguments, same rules.
    """
    query = {**(params or {}), **more}
    query = {key: value for key, value in query.items() if value is not None}
    return FEEDBACK_URL + ("?" + urlencode(query) if query else "")


def draw_docs_button(
    layout: Any,
    page: str,
    text: str = "Documentation",
    icon: str = "HELP",
    emboss: bool = True,
) -> None:
    """Draws a button that opens a page of the documentation in the browser.

    Args:
        layout (bpy.types.UILayout): Where the button goes.
        page (str): Path of the page, see `docs_url`.
        text (str): Label of the button.
        icon (str): Blender icon of the button.
        emboss (bool): False draws it as a plain link.
    """
    layout.operator("wm.url_open", text=text, icon=icon, emboss=emboss).url = docs_url(page)


def draw_early_access(layout: Any, text: str = "Early access", url: str = FEEDBACK_URL) -> None:
    """Draws an early-access label with a button to give feedback.

    Draws nothing when `EARLY_ACCESS` is off.

    Args:
        layout (bpy.types.UILayout): Where the row goes.
        text (str): Label next to the button.
        url (str): Where the button goes, see `feedback_url`.
    """
    if not EARLY_ACCESS:
        return
    row = layout.row(align=True)
    row.label(text=text, icon="EXPERIMENTAL")
    row.operator("wm.url_open", text="Give feedback", icon="COMMUNITY").url = url
