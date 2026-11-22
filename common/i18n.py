# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Translation of the texts the add-on shows.

Every user-facing string goes through `tr`, which asks Blender's translation
system (`bpy.app.translations`) for the text in the interface language the user
chose in the preferences. English is the key, so code reads naturally and a
missing translation falls back to it. To add a language, add its entries to
`TRANSLATIONS` (or load them from a file into it) before `register` runs:

    TRANSLATIONS["nl_NL"] = {("*", "Install"): "Installeren", ...}

Rules for translatable text, so translators can do their job:
- Pass whole sentences, never fragments glued together in code.
- Format after translating: `tr("{count} packs").format(count=n)`, no f-strings.
- Blender's `bl_label` and `bl_description` are translated by Blender itself
  once the dictionary is registered, nothing to do there.
"""
from typing import Dict, Tuple

import bpy

DOMAIN = "HumGen3D"
CONTEXT = "*"

# language code -> {(context, english): translation}
TRANSLATIONS: Dict[str, Dict[Tuple[str, str], str]] = {}


def tr(text: str) -> str:
    """The text in the interface language, or `text` itself."""
    return bpy.app.translations.pgettext_iface(text, CONTEXT)


def register() -> None:
    if TRANSLATIONS:
        try:
            bpy.app.translations.register(DOMAIN, TRANSLATIONS)
        except ValueError:  # already registered, after a reload
            bpy.app.translations.unregister(DOMAIN)
            bpy.app.translations.register(DOMAIN, TRANSLATIONS)


def unregister() -> None:
    if TRANSLATIONS:
        try:
            bpy.app.translations.unregister(DOMAIN)
        except ValueError:
            pass
