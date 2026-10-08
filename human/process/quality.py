# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Quality tiers: one choice that fills the detail of every mesh of a LOD level.

The tiers are the presets of `QualitySettings`, the interface shows which tier
the settings match and the per-part pickers change them further. The same for
the texture resolutions.
"""

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from .settings import QualitySettings

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

# Identifier, label, description and settings of each tier, in interface order
QUALITY_TIERS: List[Tuple[str, str, str, QualitySettings]] = [
    (
        "original",
        "Original",
        "Every mesh as it is, with the layered eyes that only render in Blender",
        QualitySettings(
            body=0,
            clothing="original",
            eyes="original",
            teeth=0,
            haircards="ultra",
            bones_per_vertex=0,
        ),
    ),
    (
        "ultra",
        "Ultra",
        "Full body and clothing, the most hair cards, eight bones per vertex",
        QualitySettings(
            body=0,
            clothing="original",
            eyes="high",
            teeth=0,
            haircards="ultra",
            bones_per_vertex=8,
        ),
    ),
    (
        "high",
        "High",
        "Full body, clothing halved, high hair cards",
        QualitySettings(
            body=0, clothing="high", eyes="high", teeth=1, haircards="high"
        ),
    ),
    (
        "medium",
        "Medium",
        "Lower face, clothing a quarter, medium hair cards",
        QualitySettings(
            body=1, clothing="medium", eyes="medium", teeth=1, haircards="medium"
        ),
    ),
    (
        "low",
        "Low",
        "A quarter of the body, clothing a tenth, low hair cards",
        QualitySettings(
            body=2, clothing="low", eyes="low", teeth=2, haircards="low"
        ),
    ),
    (
        "mobile",
        "Mobile",
        "Like low with only a hair texture on the skin and two bones per vertex",
        QualitySettings(
            body=2,
            clothing="low",
            eyes="low",
            teeth=2,
            haircards="haircap_only",
            bones_per_vertex=2,
        ),
    ),
]
CUSTOM_TIER = ("custom", "Custom", "Changed per part")

# Identifier, label and resolutions per texture set of each texture tier
TEXTURE_TIERS: List[Tuple[str, str, Dict[str, int]]] = [
    ("4k", "4k", {"body": 4096, "clothing": 4096, "eyes": 1024, "teeth": 512, "hair": 2048}),
    ("2k", "2k", {"body": 2048, "clothing": 2048, "eyes": 512, "teeth": 512, "hair": 1024}),
    ("1k", "1k", {"body": 1024, "clothing": 1024, "eyes": 256, "teeth": 256, "hair": 512}),
    ("512", "512", {"body": 512, "clothing": 512, "eyes": 128, "teeth": 128, "hair": 256}),
]
RESOLUTIONS = (128, 256, 512, 1024, 2048, 4096)


def tier_of(quality: QualitySettings) -> str:
    """The tier these settings match, "custom" if none."""
    for identifier, _, _, tier in QUALITY_TIERS:
        if tier == quality:
            return identifier
    return CUSTOM_TIER[0]


def quality_of_tier(tier: str) -> QualitySettings:
    """The settings of a tier.

    Raises:
        ValueError: If the tier does not exist.
    """
    for identifier, _, _, quality in QUALITY_TIERS:
        if identifier == tier:
            return quality.copy()
    raise ValueError(f"Unknown quality tier '{tier}'")


def texture_tier_of(resolution: Dict[str, int]) -> str:
    """The texture tier these resolutions match, "custom" if none."""
    for identifier, _, tier in TEXTURE_TIERS:
        if tier == resolution:
            return identifier
    return CUSTOM_TIER[0]


def resolution_of_tier(tier: str) -> Dict[str, int]:
    """The resolutions of a texture tier.

    Raises:
        ValueError: If the tier does not exist.
    """
    for identifier, _, resolution in TEXTURE_TIERS:
        if identifier == tier:
            return dict(resolution)
    raise ValueError(f"Unknown texture tier '{tier}'")


def estimate_triangles(
    human: "Human",
    quality: QualitySettings,
    haircards: bool,
    remove_clothing_subdiv: bool = True,
    remove_clothing_solidify: bool = True,
) -> Dict[str, int]:
    """Triangles per part of the human at this quality, cheap enough for the UI.

    Returns:
        Dict[str, int]: "body", "clothing", "eyes", "teeth" and "hair", the hair
            is 0 when the particle hair is not converted to cards.
    """
    tris = human.process.lod.estimate_triangles(
        quality.body,
        quality.clothing,
        quality.eyes,
        quality.teeth,
        remove_clothing_subdiv,
        remove_clothing_solidify,
    )
    tris["hair"] = (
        human.hair.estimate_haircards_triangles(quality.haircards) if haircards else 0
    )
    return tris


def tier_label(identifier: str) -> Optional[str]:
    """Label of a quality tier, None for an unknown identifier."""
    for tier_id, label, *_ in QUALITY_TIERS + [CUSTOM_TIER]:
        if tier_id == identifier:
            return label
    return None
