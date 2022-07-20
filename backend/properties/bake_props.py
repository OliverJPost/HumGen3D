import bpy

from bpy.props import (  # type: ignore
    StringProperty,
    EnumProperty,
    IntProperty,
)
from .property_functions import get_resolutions

from HumGen3D.utility_section.baking import make_path_absolute


class BakeProps(bpy.types.PropertyGroup):

    # baking
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

    idx: IntProperty(default=0)

    total: IntProperty(default=0)

    progress: IntProperty(
        name="Progress", subtype="PERCENTAGE", min=0, max=100, default=0
    )
