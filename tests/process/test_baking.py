# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
# flake8:noqa: F811


import numpy as np
import pytest

from HumGen3D.backend import hg_log
from HumGen3D.human.human import Human
from HumGen3D.human.process.bake import BakeTexture
from HumGen3D.tests.test_fixtures import *

bake_types = {
    "body": (["Base Color", "Specular", "Roughness", "Normal"], 0),
    "eyes": (["Base Color"], 1),
    "cloth": (["Base Color", "Roughness", "Normal"], 0),
    "lower_teeth": (["Base Color", "Roughness", "Normal"], 0),
    "upper_teeth": (["Base Color", "Roughness", "Normal"], 0),
}


@pytest.mark.parametrize("human", ALL_HUMAN_FIXTURES)
@pytest.mark.parametrize("bake_obj", bake_types.keys())
def test_bake_single(human: Human, context, bake_obj, tmp_path):
    human.process.baking._check_bake_render_settings(context, 4, force_cycles=True)
    baketextures = []
    bake_obj_actual = getattr(human.objects, bake_obj)
    for bake_type in bake_types[bake_obj][0]:
        if (
            bake_type == "cloth"
            and not human.clothing.outfit.objects
            or human.clothing.footwear.objects
        ):
            continue
        baketextures.append(
            BakeTexture(
                human.name,
                bake_obj,
                bake_obj_actual,
                bake_types[bake_obj][1],
                bake_type,
            )
        )

    images = []
    for bake_texture in baketextures:
        img = human.process.baking.bake_single_texture(
            bake_texture, tmp_path, context=context
        )
        hg_log(img.filepath)
        pixels = np.array(img.pixels)
        # Skip alpha
        pixels = pixels[::4]
        assert np.max(pixels) > np.min(pixels) + 0.01, (
            "Image does not have any contrast, saved at " + img.filepath
        )
        images.append(img)

    print(images)
