# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""
context.scene.HG3D.batch
Properties related to the Human Generator batch generator
"""


import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty  # type: ignore
from HumGen3D.user_interface.batch_panel.batch_ui_lists import batch_uilist_refresh


class BatchProps(bpy.types.PropertyGroup):
    """Subclass of HG_SETTINGS, contains properties related to the batch generator"""

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
    caucasian_chance: IntProperty(
        name="Caucasian", subtype="PERCENTAGE", min=0, max=100, default=100
    )
    black_chance: IntProperty(
        name="Black", subtype="PERCENTAGE", min=0, max=100, default=100
    )
    asian_chance: IntProperty(
        name="Asian", subtype="PERCENTAGE", min=0, max=100, default=100
    )

    performance_statistics: BoolProperty(default=False)

    # For enabling the different features
    pose: BoolProperty(default=False)
    clothing: BoolProperty(default=False)
    expression: BoolProperty(default=False)
    hair: BoolProperty(default=False)
    bake: BoolProperty(default=False)

    hairtype: EnumProperty(
        name="Hair Type",
        items=[
            ("particle", "Particle hair", "", 0),
            ("haircards", "Haircards", "", 1),
        ],
        default="particle",
    )

    clothing_inside: BoolProperty(
        name="Inside",
        default=True,
        update=lambda a, b: batch_uilist_refresh(a, b, "outfits"),
    )
    clothing_outside: BoolProperty(
        name="Outside",
        default=True,
        update=lambda a, b: batch_uilist_refresh(a, b, "outfits"),
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

    standard_deviation: IntProperty(
        name="Standard deviation",
        default=5,
        subtype="PERCENTAGE",
        min=0,
        max=10,
    )
    show_height_examples: BoolProperty(default=False)

    delete_backup: BoolProperty(name="Delete backup human", default=True)
    apply_shapekeys: BoolProperty(name="Apply shape keys", default=True)
    apply_armature_modifier: BoolProperty(name="Apply armature modifier", default=True)
    remove_clothing_solidify: BoolProperty(
        name="Remove clothing solidify", default=True
    )
    remove_clothing_subdiv: BoolProperty(name="Remove clothing subdiv", default=True)
    apply_clothing_geometry_masks: BoolProperty(
        name="Apply geometry masks", default=True
    )

    texture_resolution: EnumProperty(
        name="Texture Resolution",
        items=[
            ("high", "High (~4K)", "", 0),
            ("optimised", "Optimised (~1K)", "", 1),
            ("performance", "Performance (~512px)", "", 2),
        ],
        default="optimised",
    )

    poly_reduction: EnumProperty(
        name="Polygon reduction",
        items=[
            ("none", "Disabled (original topology)", "", 0),
            ("medium", "Medium (33% polycount)", "", 1),  # 2x unsubdivide
            ("high", "High (15% polycount)", "", 2),  # 0.08 collapse
            ("ultra", "Ultra (5% polycount)", "", 3),  # 0.025 collapse
        ],
        default="none",
    )
    apply_poly_reduction: BoolProperty(name="Apply poly reduction", default=True)

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
