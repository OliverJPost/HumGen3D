# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import os
import random
from typing import Literal, Optional, Union

import bpy
from HumGen3D.batch_generator.batch_functions import height_from_bell_curve
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C  # type:ignore
from HumGen3D.human.human import Human

SettingsDict = dict[str, Union[str, int, float]]


class BatchHumanGenerator:
    """Generator/factory (?) for making completed HG_Humans in the background.

    Also used by the batch panel in the Human Generator GUI
    """

    female_chance: float = 1.0
    male_chance: float = 1.0
    human_preset_category_chances: Optional[dict[str, float]] = None
    add_clothing: bool = True
    clothing_categories: Optional[list[str]] = None
    add_expression: bool = True
    expression_type: Literal["natural", "most_varied"] = "natural"
    add_hair: bool = True
    hair_type: Literal["particle", "haircards"] = "particle"
    hair_quality: Literal[
        "high", "medium", "low", "ultralow", "haircap_only"
    ] = "medium"
    average_height_male: int = 177
    average_height_female: int = 172
    height_one_standard_deviation: float = 0.05
    texture_resolution: Literal["high", "medium", "low"] = "medium"

    def __init__(
        self,
        add_clothing: bool = True,
        add_hair: bool = True,
        add_expression: bool = True,
    ) -> None:
        self.add_clothing = add_clothing
        self.add_hair = add_hair
        self.add_expression = add_expression

    @injected_context
    def generate_human(
        self,
        context: C = None,
        pose_type: str = "a_pose",
    ) -> "Human":

        gender = random.choices(
            ("male", "female"), (self.male_chance, self.female_chance)
        )[0]
        if not self.human_preset_category_chances:
            presets = Human.get_preset_options(gender)
        else:
            presets = []
            # While loop to ensure at least one preset is in the list
            while not presets:
                chosen_category: str = random.choices(
                    *zip(*self.human_preset_category_chances.items())  # type:ignore
                )[0]
                presets = Human.get_preset_options(gender, chosen_category, context)

        chosen_preset = random.choice(presets)
        human = Human.from_preset(chosen_preset, from_batch_generator=True)

        human.body.randomize()
        human.face.randomize(use_bell_curve=gender == "female")

        human.skin.randomize()
        human.skin.texture.set_resolution(self.texture_resolution)
        human.eyes.randomize()

        if self.add_hair:
            human.hair.regular_hair.randomize(context)
            if human.gender == "male" and random.choice((1, 2, 3)) == 1:
                human.hair.face_hair.randomize(context)
                human.hair.face_hair.lightness = human.hair.regular_hair.lightness
                human.hair.face_hair.redness = human.hair.regular_hair.redness

        human.hair.eyebrows.randomize_color()
        if self.hair_type == "particle":
            human.hair.set_hair_quality(self.hair_quality)
            human.hair.children_set_hide(True)
        else:
            for hairtype in ("regular_hair", "face_hair", "eyebrows", "eyelashes"):
                if hairtype == "face_hair" and human.gender == "female":
                    continue
                hair_attr = getattr(human.hair, hairtype)
                if not hair_attr.particle_systems:
                    continue
                hair_attr.convert_to_haircards(self.hair_quality, context)

        human.height.set(
            height_from_bell_curve(
                self.average_height_male
                if gender == "male"
                else self.average_height_female,
                self.height_one_standard_deviation,
            )[0]
        )

        if self.add_clothing:
            self._set_clothing(context, human)

        if pose_type != "a_pose":
            if pose_type == "t_pose":
                human.pose.set(os.path.join("poses", "Base Poses", "HG_T_Pose.blend"))
            else:
                options = human.pose.get_options(
                    context, category=pose_type.replace("_", " ")
                )
                human.pose.set(random.choice(options))

        if self.add_expression:
            self._set_expression(context, human)

        return human

    def _set_clothing(self, context: bpy.types.Context, human: Human) -> None:
        if self.clothing_categories:
            clothing_category = random.choice(self.clothing_categories)
        else:
            clothing_category = "All"
        clothing_options = human.clothing.outfit.get_options(context, clothing_category)
        if not clothing_options:
            clothing_options = human.clothing.outfit.get_options(context)

        human.clothing.outfit.set(random.choice(clothing_options))
        human.clothing.footwear.set_random(context)

        for cloth in human.clothing.outfit.objects:
            human.clothing.outfit.randomize_colors(cloth)
            human.clothing.outfit.set_texture_resolution(cloth, self.texture_resolution)

        for cloth in human.clothing.footwear.objects:
            human.clothing.footwear.randomize_colors(cloth)
            human.clothing.footwear.set_texture_resolution(
                cloth, self.texture_resolution
            )

    def _set_expression(self, context: bpy.types.Context, human: Human) -> None:
        categories = human.expression.get_categories()
        if self.expression_type == "most_varied":
            chosen_category = random.choice(categories)
        else:
            weight_dict = {"happy": 1.0, "neutral": 1.0}
            weights = tuple(
                weight_dict.get(category.lower(), 0.08) for category in categories
            )
            chosen_category = random.choices(categories, weights=weights)[0]

        options = human.expression.get_options(context, category=chosen_category)
        if options:
            human.expression.set(random.choice(options))
        else:
            human.expression.set_random(context)
