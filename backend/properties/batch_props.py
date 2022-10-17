# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

""" # noqa D400
context.scene.HG3D.batch

Properties related to the Human Generator batch generator
"""


import bpy
from bpy.props import (  # type: ignore
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
)


class BatchProps(bpy.types.PropertyGroup):
    """Subclass of HG_SETTINGS, contains properties related to the batch generator."""

    _register_priority = 4

    # Modal props
    progress: IntProperty(
        name="Progress", subtype="PERCENTAGE", min=0, max=100, default=0
    )
    idx: IntProperty(default=0)

    # Statistics props
    male_chance: IntProperty(
        name="Male", subtype="PERCENTAGE", min=0, max=100, default=100
    )
    female_chance: IntProperty(
        name="Female", subtype="PERCENTAGE", min=0, max=100, default=100
    )

    performance_statistics: BoolProperty(default=False)

    # For enabling the different features
    pose: BoolProperty(default=False)
    clothing: BoolProperty(default=False)
    expression: BoolProperty(default=False)
    hair: BoolProperty(default=False)
    bake: BoolProperty(default=False)

    expression_type: EnumProperty(
        name="Expression type",
        items=[
            ("natural", "Natural", "", 0),
            ("most_varied", "Most varied", "", 1),
        ],
        default="natural",
    )
    hairtype: EnumProperty(
        name="Hair Type",
        items=[
            ("particle", "Particle hair", "", 0),
            ("haircards", "Haircards", "", 1),
        ],
        default="particle",
    )

    marker_selection: EnumProperty(
        name="Generate batch markers",
        items=[
            ("all", "All markers", "", 0),
            ("selected", "Selected markers", "", 1),
            ("empty", "Empty markers", "", 2),
        ],
        default="all",
    )

    height_system: EnumProperty(
        name="System",
        items=[("metric", "Metric", "", 0), ("imperial", "Imperial", "", 1)],
        default="metric",
    )
    average_height_cm_male: IntProperty(name="Male [cm]", default=175, min=160, max=190)
    average_height_cm_female: IntProperty(
        name="Female [cm]", default=170, min=160, max=190
    )

    average_height_ft_male: IntProperty(name="ft", default=5, min=4, max=6)
    average_height_ft_female: IntProperty(name="ft", default=5, min=4, max=6)
    average_height_in_male: IntProperty(name="in", default=10, min=0, max=12)
    average_height_in_female: IntProperty(name="in", default=10, min=0, max=12)

    standard_deviation: FloatProperty(
        name="Standard deviation",
        default=0.05,
        min=0,
        max=0.1,
    )
    show_height_examples: BoolProperty(default=False)

    texture_resolution: EnumProperty(
        name="Texture Resolution",
        items=[
            ("high", "High (~4K)", "", 0),
            ("optimised", "Optimised (~1K)", "", 1),
            ("performance", "Performance (~512px)", "", 2),
        ],
        default="optimised",
    )

    hair_quality_particle: EnumProperty(
        name="Particle hair quality",
        items=[
            ("high", "High", "", 0),
            ("medium", "Medium", "", 1),
            ("low", "Low", "", 2),
            ("ultralow", "Ultra Low", "", 3),
        ],
        default="medium",
    )
    hair_quality_haircards: EnumProperty(
        name="Haircard quality",
        items=[
            ("low", "Low", "", 1),
            ("ultralow", "Ultra Low", "", 2),
        ],
        default="low",
    )
