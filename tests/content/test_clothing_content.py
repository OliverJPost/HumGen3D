import bpy
import pytest
from HumGen3D.tests.fixtures import (
    ALL_HUMAN_FIXTURES,
    context,
    female_human,
    male_human,
)

POSE_NAMES = ["plank", "sitting_body_forward", "running_7", "squat"]


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
@pytest.mark.parametrize("clothing_category", ("outfit", "footwear"))
def test_clothing(human, clothing_category, context):
    _test_all_clothing_options(human, clothing_category, context)


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
@pytest.mark.parametrize("pose_name", POSE_NAMES)
@pytest.mark.parametrize("clothing_category", ("outfit", "footwear"))
def test_clothing_in_pose(human, pose_name, clothing_category, context):
    pose_options = human.pose.get_options(context)
    chosen = next(opt for opt in pose_options if pose_name in opt.lower())
    human.pose.set(chosen)
    _test_all_clothing_options(human, clothing_category, context, all_tests=False)


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
@pytest.mark.parametrize("height", (155, 200))
@pytest.mark.parametrize("clothing_category", ("outfit", "footwear"))
def test_clothing_with_heightchange(human, height, clothing_category, context):
    human.height.set(height)
    _test_all_clothing_options(human, clothing_category, context, all_tests=False)


def _test_all_clothing_options(human, category, context, all_tests=True):
    for i, option in enumerate(getattr(human, category).get_options(context)):
        getattr(human, category).set(option)

        # Check if the outfit doesn't clip too much
        assert (
            getattr(human, category)._calc_percentage_clipping_vertices() < 0.06
        ), f"{option} produces too much clipping. {i = }"

        if not all_tests:
            continue

        # Check if all textures are loaded
        for obj in getattr(human, category).objects:
            mat = obj.active_material

            for img_node in [n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE"]:
                img = img_node.image
                # assert img.has_data
