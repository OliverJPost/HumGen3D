from HumGen3D.human.human import Human
from HumGen3D.tests.test_fixtures import *
import pytest
from HumGen3D.batch_generator.generator import BatchHumanGenerator


@pytest.mark.parametrize("gender", ["male", "female"])
def test_batch_gender_chance(gender, context):
    generator = BatchHumanGenerator()
    opposite_gender = "female" if gender == "male" else "male"
    setattr(generator, f"{gender}_chance", 1)
    setattr(generator, f"{opposite_gender}_chance", 0)
    for _ in range(5):
        generated_human = generator.generate_human(context)
        assert generated_human.gender == gender


def test_batch_preset_category_chance(context):
    generator = BatchHumanGenerator()
    chances = {categ: 0 for categ in Human.get_categories("male")}
    chances["Black"] = 1
    generator.human_preset_category_chances = chances
    for _ in range(5):
        generated_human = generator.generate_human(context)
        assert "black" in generated_human._active.lower()


@pytest.mark.parametrize("add_clothing", [True, False])
@pytest.mark.parametrize("add_hair", [True, False])
@pytest.mark.parametrize("add_expression", [True, False])
def test_batch_add(add_clothing, add_hair, add_expression):
    generator = BatchHumanGenerator(
        add_clothing=add_clothing, add_hair=add_hair, add_expression=add_expression
    )
    generated_human = generator.generate_human()
    if add_clothing:
        assert generated_human.clothing.outfit.objects
        assert generated_human.clothing.footwear.objects
    if add_hair:
        assert generated_human.hair.regular_hair.particle_systems
    if add_expression:
        assert generated_human.keys.filtered("expressions")


POSE_TYPES = [
    "a_pose",
    "t_pose",
    "Running",
    "Sitting",
    "Standing around",
    "Walking",
    "Socializing",
]


@pytest.mark.parametrize("pose_type", POSE_TYPES)
def test_batch_pose_type(pose_type, context):
    generator = BatchHumanGenerator()
    generated_human = generator.generate_human(context, pose_type)
    if not pose_type == "a_pose":
        assert pose_type.lower() in generated_human.pose._active.lower()


def test_batch_hair_type(context):
    generator = BatchHumanGenerator(add_hair=True)
    generator.hair_type = "haircards"
    generated_human = generator.generate_human(context)
    assert generated_human.objects.haircards


@pytest.mark.parametrize("resolution", ["high", "medium", "low"])
def test_batch_texture_resolution(resolution, context):
    resolution_names = {
        "high": "4k",
        "medium": "1k",
        "low": "512px",
    }
    generator = BatchHumanGenerator()
    generator.texture_resolution = resolution
    generated_human = generator.generate_human(context)
    assert resolution_names[resolution] in generated_human.skin.texture._active.lower()
