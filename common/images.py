# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Image file operations done with Blender's own image API.

Used where the add-on once needed Pillow. An extension may not install Python
packages at runtime, and Blender can load, scale and save the formats the
content library uses.
"""
import os

import bpy

FILE_FORMATS = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".tif": "TIFF",
    ".tiff": "TIFF",
}


def file_format(path: str) -> str:
    """Blender's file format name for the extension of `path`.

    Raises:
        NotImplementedError: For an extension the content library doesn't use.
    """
    ext = os.path.splitext(path)[1].lower()
    try:
        return FILE_FORMATS[ext]
    except KeyError:
        raise NotImplementedError(f"Cannot save images as {ext!r}") from None


def save_resized(source: str, destination: str, size: int) -> None:
    """Save a copy of the image file `source` scaled to `size` by `size` pixels.

    The format comes from the extension of `destination`.
    """
    fmt = file_format(destination)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    image = bpy.data.images.load(source, check_existing=False)
    try:
        image.scale(size, size)
        image.filepath_raw = destination
        image.file_format = fmt
        image.save()
    finally:
        bpy.data.images.remove(image)
