# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Links from the interface to the documentation website.

Every "Documentation" and "Learn more" button goes through `docs_url`, so the
site can move by changing `DOCS_URL`. Pages are named by their URL path on the
site, which is the folder and file name of the page in `docs/` in lower case
with dashes: `docs/Process/Bake Textures.md` is "process/bake-textures". An
anchor can follow it: "process/output#processed-copies".
"""

from typing import Any

DOCS_URL = "https://humgen3d.com/docs/"


def docs_url(page: str = "") -> str:
    """The URL of a page of the documentation.

    Args:
        page (str): Path of the page on the site, "" for the start page.
    """
    return DOCS_URL + page.strip("/")


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
