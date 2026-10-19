# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Where the add-on lives in Python, whatever name Blender loaded it under.

As a legacy add-on (Blender 4.0 and 4.1) the package is `HumGen3D`. As a
Blender extension (4.2 and later) it is `bl_ext.<repository>.humgen3d`, where
the repository part is the name of the repository the user installed it from.
Code that needs the package name, such as the preferences lookup, asks here
instead of assuming one. This module imports nothing from the add-on, so it is
safe to import while the package is still initializing.
"""
import os
import re
import sys
from typing import Tuple

PUBLIC_NAME = "HumGen3D"
"""The name scripts import the add-on by, kept working by `alias`."""

EXTENSION_PREFIX = "bl_ext."
"""Blender loads extensions as `bl_ext.<repository>.<id>`."""

MANIFEST_FILE = "blender_manifest.toml"

Version = Tuple[int, int, int]


def addon_package() -> str:
    """The dotted name of the add-on package.

    `HumGen3D` as a legacy add-on, `bl_ext.<repository>.humgen3d` as an extension.
    """
    # This module is <package>.package
    return __name__.rpartition(".")[0]


def is_extension() -> bool:
    """Whether Blender loaded the add-on through its extension system."""
    return addon_package().startswith(EXTENSION_PREFIX)


def addon_root() -> str:
    """Path of the folder of the add-on, the one with `__init__.py`."""
    return os.path.dirname(os.path.abspath(__file__))


def manifest_path() -> str:
    """Path of the extension manifest, also present in the legacy install."""
    return os.path.join(addon_root(), MANIFEST_FILE)


def manifest_version() -> Version:
    """The version in the extension manifest, the single source of the version.

    Parsed with a regular expression instead of `tomllib`, which Blender 4.0 and
    4.1 (Python 3.10) don't have.
    """
    with open(manifest_path(), encoding="utf-8") as f:
        text = f.read()
    match = re.search(r'^version\s*=\s*"(\d+)\.(\d+)\.(\d+)"', text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"No version in {manifest_path()}")
    return int(match[1]), int(match[2]), int(match[3])


def addon_version() -> Version:
    """The version of the running add-on."""
    return tuple(sys.modules[addon_package()].__version__)  # type: ignore[return-value]
