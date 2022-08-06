from operator import attrgetter

import bpy  # type: ignore
from bpy.props import EnumProperty, StringProperty  # type: ignore
from HumGen3D.human.human import Human

from ..content_packs.custom_content_packs import build_content_collection
from ..preview_collections import get_pcoll_enum_items, refresh_pcoll
from .property_functions import find_folders


def get_items(attr):
    retreiver = attrgetter(attr)
    return lambda self, context: retreiver(
        Human.from_existing(context.object)
    )._get_full_options()


def get_folders(attr):
    retreiver = attrgetter(attr)
    return lambda self, context: retreiver(
        Human.from_existing(context.object)
    ).get_categories()


def update(attr):
    retreiver = attrgetter(attr)
    return lambda self, context: retreiver(Human.from_existing(context.object))._set(
        context
    )

def refresh(attr):
    retreiver = attrgetter(attr)
    return lambda self, context: retreiver(Human.from_existing(context.object))._refresh(
        context
    )
class PreviewCollectionProps(bpy.types.PropertyGroup):
    ####### preview collections ########
    # creation
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
        update=lambda a, b: refresh_pcoll(a, b, "poses"),
    )

    # outfit
    outfit: EnumProperty(
        items=get_items("finalize_phase.outfit"), update=update("finalize_phase.outfit")
    )
    outfit_category: EnumProperty(
        name="Outfit Library",
        items=lambda a, b: find_folders(a, b, "outfits", True),
        update=lambda a, b: refresh_pcoll(a, b, "outfit"),
    )
    search_term_outfit: StringProperty(
        name="Search:",
        default="",
        update=lambda a, b: refresh_pcoll(a, b, "outfit"),
    )

    # hair
    hair: EnumProperty(
        items=get_items("hair.regular_hair"),
        update=update("hair.regular_hair"),
    )
    hair_category: EnumProperty(
        name="Hair Library",
        items=lambda a, b: find_folders(a, b, "hair/head", True),
        update=lambda a, b: refresh_pcoll(a, b, "hair"),
    )
    face_hair: EnumProperty(
        items=update("hair.face_hair"),
        update=update("hair.face_hair"),
    )
    face_hair_category: EnumProperty(
        name="Facial Hair Library",
        items=lambda a, b: find_folders(a, b, "hair/face_hair", False),
        update=lambda a, b: refresh_pcoll(a, b, "face_hair"),
    )

    # expression
    expressions: EnumProperty(
        items=get_items("finalize_phase.expression"),
        update=update("finalize_phase.expression"),
    )
    expressions_category: EnumProperty(
        name="Expressions Library",
        items=lambda a, b: find_folders(a, b, "expressions", False),
        update=lambda a, b: refresh_pcoll(a, b, "expressions"),
    )
    search_term_expressions: StringProperty(
        name="Search:",
        default="",
        update=lambda a, b: refresh_pcoll(a, b, "expressions"),
    )

    # footwear
    footwear: EnumProperty(
        items=lambda a, b: get_pcoll_enum_items(a, b, "footwear"),
        update=lambda s, c: Human.from_existing(c.object).finalize_phase.footwear.set(
            s.footwear, c
        ),
    )
    footwear_category: EnumProperty(
        name="Footwear Library",
        items=lambda a, b: find_folders(a, b, "footwear", True),
        update=lambda a, b: refresh_pcoll(a, b, "footwear"),
    )
    search_term_footwear: StringProperty(
        name="Search:",
        default="",
        update=lambda a, b: refresh_pcoll(a, b, "footwear"),
    )

    # patterns
    patterns: EnumProperty(
        items=get_items("finalize_phase.outfit.pattern"),
        update=update("finalize_phase.outfit.pattern"),
    )
    patterns_category: EnumProperty(
        name="Pattern Library",
        items=lambda a, b: find_folders(a, b, "patterns", False),
        update=lambda a, b: refresh_pcoll(a, b, "patterns"),
    )
    search_term_patterns: StringProperty(
        name="Search:",
        default="",
        update=lambda a, b: refresh_pcoll(a, b, "patterns"),
    )

    textures: EnumProperty(
        items=lambda a, b: get_pcoll_enum_items(a, b, "textures"),
        update=lambda s, c: Human.from_existing(c.object).skin.texture.set(s.textures),
    )
    texture_library: EnumProperty(
        name="Texture Library",
        items=lambda a, b: find_folders(a, b, "textures", True, include_all=False),
        update=lambda a, b: refresh_pcoll(a, b, "textures"),
    )
