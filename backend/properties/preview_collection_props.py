# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

# type:ignore
# flake8: noqa CM001
"""
context.scene.HG3D.pcoll
Stores the preview collections of Human Generator. These collections are used to allow
the user to choose between different options by looking at thumbnail pictures.
"""
from operator import attrgetter

import bpy  # type: ignore
from bpy.props import EnumProperty, StringProperty  # type: ignore
from HumGen3D.backend.preview_collections import preview_collections
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.human.human import Human


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
        if attr == "humans":
            return Human._get_categories(context.scene.HG3D.gender)
        human = Human.from_existing(context.object, strict_check=False)
        try:
            return retreiver(human)._get_categories()
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
    ).refresh_pcoll(context)


# TODO create repetetive properties in loop
class PreviewCollectionProps(bpy.types.PropertyGroup):
    """Subclass of HG_SETTINGS, properties of and about the preview collections of HG"""

    _register_priority = 4

    humans: EnumProperty(
        items=lambda self, context: Human._get_full_options(self, context)
    )
    humans_category: EnumProperty(
        name="Human Library",
        items=get_folders("humans"),
        update=lambda _, context: preview_collections["humans"].refresh(
            context, context.scene.HG3D.gender
        ),
    )

    # posing
    pose: EnumProperty(
        items=get_items("pose"),
        update=update("pose"),
    )
    pose_category: EnumProperty(
        name="Pose Library",
        items=get_folders("pose"),
        update=refresh("pose"),
    )
    search_term_pose: StringProperty(
        name="Search:",
        default="",
        update=refresh("pose"),
    )

    # outfits
    outfit: EnumProperty(
        items=get_items("clothing.outfit"), update=update("clothing.outfit")
    )
    outfit_category: EnumProperty(
        name="Outfit Library",
        items=get_folders("clothing.outfit"),
        update=refresh("clothing.outfit"),
    )
    search_term_outfit: StringProperty(
        name="Search:",
        default="",
        update=refresh("clothing.outfit"),
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
    search_term_hair: StringProperty(
        name="Search:",
        default="",
        update=refresh("hair"),
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
    search_term_face_hair: StringProperty(
        name="Search:",
        default="",
        update=refresh("hair.face_hair"),
    )
    # expression
    expression: EnumProperty(
        items=get_items("expression"),
        update=update("expression"),
    )
    expression_category: EnumProperty(
        name="Expressions Library",
        items=get_folders("expression"),
        update=refresh("expression"),
    )
    search_term_expression: StringProperty(
        name="Search:",
        default="",
        update=refresh("expression"),
    )

    # footwear # noqa
    footwear: EnumProperty(
        items=get_items("clothing.footwear"),
        update=update("clothing.footwear"),
    )
    footwear_category: EnumProperty(
        name="Footwear Library",
        items=get_folders("clothing.footwear"),
        update=refresh("clothing.footwear"),
    )
    search_term_footwear: StringProperty(
        name="Search:",
        default="",
        update=refresh("clothing.footwear"),
    )

    # patterns
    pattern: EnumProperty(
        items=get_items("clothing.outfit.pattern"),
        update=update("clothing.outfit.pattern"),
    )
    pattern_category: EnumProperty(
        name="Pattern Library",
        items=get_folders("clothing.outfit.pattern"),
        update=refresh("clothing.outfit.pattern"),
    )
    search_term_pattern: StringProperty(
        name="Search:",
        default="",
        update=refresh("clothing.outfit.pattern"),
    )

    texture: EnumProperty(
        items=get_items("skin.texture"),
        update=update("skin.texture"),
    )
    texture_category: EnumProperty(
        name="Texture Library",
        items=get_folders("skin.texture"),
        update=refresh("skin.texture"),
    )
    search_term_texture: StringProperty(
        name="Search:",
        default="",
        update=refresh("skin.texture"),
    )
