# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import os

import bpy
import numpy as np
from HumGen3D.backend.preferences.preference_func import get_prefs

SK_NAME = "hg_shorter"


def main():
    body = bpy.data.objects["HG_Body"]
    vert_count = len(body.data.vertices)
    body_coordinates = np.empty(vert_count * 3, dtype=np.float64)
    body.data.vertices.foreach_get("co", body_coordinates)

    sk = body.data.shape_keys.key_blocks.get(SK_NAME)
    assert sk
    sk_coordinates = np.empty(vert_count * 3, dtype=np.float64)
    sk.data.foreach_get("co", sk_coordinates)

    relative_coordinates = sk_coordinates - body_coordinates

    save_name = sk.name
    path = os.path.join(get_prefs().filepath, "livekeys")

    if not os.path.exists(path):
        os.makedirs(path)

    np.save(os.path.join(path, save_name), relative_coordinates)
    print("saved to", path)
