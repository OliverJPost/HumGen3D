"""
context.scene.HG3D.bake
For storing properties related to texture baking of the Human Generator character
"""

import os

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty  # type: ignore


def make_path_absolute(key):
    """Makes sure the passed path is absolute

    Args:
        key (str): path
    """

    props = bpy.context.scene.HG3D
    sane_path = lambda p: os.path.abspath(bpy.path.abspath(p))
    if key in props and props[key].startswith("//"):
        props[key] = sane_path(props[key])


def get_resolutions():
    return [
        ("128", "128 x 128", "", 0),
        ("256", "256 x 256", "", 1),
        ("512", "512 x 512", "", 2),
        ("1024", "1024 x 1024", "", 3),
        ("2048", "2048 x 2048", "", 4),
        ("4096", "4096 x 4096", "", 5),
    ]


class BakeProps(bpy.types.PropertyGroup):
    """Subclass of HG_SETTINGS, contains properties related to texture baking"""

    # Resolution props
    res_body: EnumProperty(
        items=get_resolutions(),
        default="1024",
    )
    res_eyes: EnumProperty(
        items=get_resolutions(),
        default="256",
    )
    res_teeth: EnumProperty(
        items=get_resolutions(),
        default="256",
    )
    res_clothes: EnumProperty(
        items=get_resolutions(),
        default="1024",
    )

    export_folder: StringProperty(
        name="Baking export",
        subtype="DIR_PATH",
        default="",
        update=lambda s, c: make_path_absolute("export_folder"),
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
