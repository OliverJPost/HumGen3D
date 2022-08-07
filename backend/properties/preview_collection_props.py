"""
context.scene.HG3D.pcoll
Stores the preview collections of Human Generator. These collections are used to allow
the user to choose between different options by looking at thumbnail pictures.
"""
from operator import attrgetter
from weakref import ref

import bpy  # type: ignore
from bpy.props import EnumProperty, StringProperty  # type: ignore
from HumGen3D.human.human import Human
from HumGen3D.human.base.exceptions import HumGenException

from ..content_packs.custom_content_packs import build_content_collection
from ..preview_collections import get_pcoll_enum_items, refresh_pcoll
from .property_functions import find_folders


def get_items(attr):
    """Populates the preview collection. As separate function to prevent repetitive
    statements.

    Args:
        attr (str): Dot notation between Human and the method you want to access. For
        example Human.creation_phase.length.set() would have "creation_phase.length" as
        attr.

    Returns:
        func: Function in the format Blender expects it
    """
    retreiver = attrgetter(attr)
    return lambda self, context: retreiver(
        Human.from_existing(context.object)
    )._get_full_options()


def get_folders(attr):
    """Supplies function that populates the category collection.
    For args & return see get_items()"""
    retreiver = attrgetter(attr)

    def func(self, context):
        human = Human.from_existing(context.object, strict_check=False)
        try:
            return retreiver(human).get_categories()
        # Catch for weird behaviour where pose_category refreshes early
        except (AttributeError, HumGenException):
            return [("ERROR", "ERROR", "", i) for i in range(99)]

    return func


def update(attr):
    """Supplies function for callback when the preview collection changes.
    For args & return see get_items()"""
    retreiver = attrgetter(attr)
    return lambda self, context: retreiver(Human.from_existing(context.object))._set(
        context
    )


def refresh(attr):
    """Supplies function that refreshes the content of the preview collection.
    For args & return see get_items()"""
    retreiver = attrgetter(attr)
    return lambda self, context: retreiver(
        Human.from_existing(context.object)
    )._refresh(context)


# TODO create repetetive properties in loop
class PreviewCollectionProps(bpy.types.PropertyGroup):
    """Subclass of HG_SETTINGS, properties of and about the preview collections of HG"""

    humans: EnumProperty(items=lambda a, b: get_pcoll_enum_items(a, b, "humans"))

    # posing
    poses: EnumProperty(
        items=get_items("finalize_phase.pose"),
        update=update("finalize_phase.pose"),
    )
    pose_category: EnumProperty(
        name="Pose Library",
        items=get_folders("finalize_phase.pose"),
        update=refresh("finalize_phase.pose"),
    )
    search_term_poses: StringProperty(
        name="Search:",
        default="",
        update=refresh("finalize_phase.pose"),
    )

    # outfits
    outfits: EnumProperty(
        items=get_items("finalize_phase.outfit"), update=update("finalize_phase.outfit")
    )
    outfit_category: EnumProperty(
        name="Outfit Library",
        items=get_folders("finalize_phase.outfit"),
        update=refresh("finalize_phase.outfit"),
    )
    search_term_outfit: StringProperty(
        name="Search:",
        default="",
        update=refresh("finalize_phase.outfit"),
    )

    # hair
    hair: EnumProperty(
        items=get_items("hair.regular_hair"),
        update=update("hair.regular_hair"),
    )
    hair_category: EnumProperty(
        name="Hair Library",
        items=get_folders("hair.regular_hair"),
        update=refresh("hair.regular_hair"),
    )
    face_hair: EnumProperty(
        items=get_items("hair.face_hair"),
        update=update("hair.face_hair"),
    )
    face_hair_category: EnumProperty(
        name="Facial Hair Library",
        items=get_folders("hair.face_hair"),
        update=refresh("hair.face_hair"),
    )

    # expression
    expressions: EnumProperty(
        items=get_items("finalize_phase.expression"),
        update=update("finalize_phase.expression"),
    )
    expressions_category: EnumProperty(
        name="Expressions Library",
        items=get_folders("finalize_phase.expression"),
        update=refresh("finalize_phase.expression"),
    )
    search_term_expressions: StringProperty(
        name="Search:",
        default="",
        update=refresh("finalize_phase.expression"),
    )

    # footwear
    footwear: EnumProperty(
        items=get_items("finalize_phase.footwear"),
        update=update("finalize_phase.footwear"),
    )
    footwear_category: EnumProperty(
        name="Footwear Library",
        items=get_folders("finalize_phase.footwear"),
        update=refresh("finalize_phase.footwear"),
    )
    search_term_footwear: StringProperty(
        name="Search:",
        default="",
        update=refresh("finalize_phase.footwear"),
    )

    # patterns
    patterns: EnumProperty(
        items=get_items("finalize_phase.outfit.pattern"),
        update=update("finalize_phase.outfit.pattern"),
    )
    patterns_category: EnumProperty(
        name="Pattern Library",
        items=get_folders("finalize_phase.outfit.pattern"),
        update=refresh("finalize_phase.outfit.pattern"),
    )
    search_term_patterns: StringProperty(
        name="Search:",
        default="",
        update=refresh("finalize_phase.outfit.pattern"),
    )

    textures: EnumProperty(
        items=get_items("skin.texture"),
        update=update("skin.texture"),
    )
    texture_library: EnumProperty(
        name="Texture Library",
        items=get_folders("skin.texture"),
        update=refresh("skin.texture"),
    )
