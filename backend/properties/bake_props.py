# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

""" # noqa D400
context.window_manager.humgen3d.process.baking

For storing properties related to texture baking of the Human Generator character
"""

import os

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty  # type: ignore


def make_path_absolute(self: bpy.types.PropertyGroup, prop_name: str) -> None:
    """Makes sure the passed path is absolute.

    Args:
        self: PropertyGroup the prop is in
        prop_name (str): name of property
    """
    current_path = self[prop_name]  # type:ignore[index]
    if current_path.startswith("//"):
        self[prop_name] = os.path.abspath(  # type:ignore[index]
            bpy.path.abspath(current_path)
        )


RESOLUTIONS_ENUM = [
    ("128", "128 x 128", "", 0),
    ("256", "256 x 256", "", 1),
    ("512", "512 x 512", "", 2),
    ("1024", "1024 x 1024", "", 3),
    ("2048", "2048 x 2048", "", 4),
    ("4096", "4096 x 4096", "", 5),
]


class BakeProps(bpy.types.PropertyGroup):
    """Subclass of HG_SETTINGS, contains properties related to texture baking."""

    _register_priority = 4

    # Resolution props
    res_body: EnumProperty(
        items=RESOLUTIONS_ENUM,
        default="1024",
    )
    res_eyes: EnumProperty(
        items=RESOLUTIONS_ENUM,
        default="256",
    )
    res_teeth: EnumProperty(
        items=RESOLUTIONS_ENUM,
        default="256",
    )
    res_clothes: EnumProperty(
        items=RESOLUTIONS_ENUM,
        default="1024",
    )

    export_folder: StringProperty(
        name="Baking export",
        subtype="DIR_PATH",
        default="",
        update=lambda self, _: make_path_absolute(self, "export_folder"),
    )

    samples: EnumProperty(
        items=[
            ("4", "4", "", 0),
            ("16", "16", "", 1),
            ("64", "64", "", 2),
        ],
        default="4",
    )

    file_type: EnumProperty(
        items=[
            ("png", ".PNG", "", 0),
            ("jpeg", ".JPEG", "", 1),
            ("tiff", ".TIFF", "", 2),
        ],
        default="png",
    )

    # Modal properties
    idx: IntProperty(default=0)
    total: IntProperty(default=0)
    progress: IntProperty(
        name="Progress", subtype="PERCENTAGE", min=0, max=100, default=0
    )
