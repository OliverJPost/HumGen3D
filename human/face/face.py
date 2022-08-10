import os
import random

import numpy as np
from HumGen3D.backend.preferences.preference_func import get_prefs

from ..base.prop_collection import PropCollection


class FaceKeys(PropCollection):
    def __init__(self, human):
        self._human = human

    #     facekeys_dict = self._get_ff_prefix_dict()

    #     for type_name, prefix in facekeys_dict.items():
    #         setattr(
    #             FaceKeys,
    #             type_name,
    #             property(self._set_prop(type_name, prefix)),
    #         )

    # def _set_prop(self, type_name, prefix):
    #     if not hasattr(self, f"_{type_name}"):
    #         filtered_sks = [sk for sk in self if sk.name.startswith(prefix)]
    #         setattr(self, f"_{type_name}", PropCollection(filtered_sks))
    #     return getattr(self, f"_{type_name}")

    @property
    def temp_key(self):
        return next(
            (
                sk
                for sk in self._human.shape_keys
                if sk.name.startswith("LIVE_KEY_TEMP_")
            ),
            None,
        )

    @property
    def permanent_key(self):
        return self._human.shape_keys.get("LIVE_KEY_PERMANENT")

    @property
    def shape_keys(self) -> PropCollection:
        sks = self._human.shape_keys
        ff_keys = [sk for sk in sks if sk.name.startswith("ff_")]
        pr_keys = [sk for sk in sks if sk.name.startswith("pr_")]
        return PropCollection(ff_keys + pr_keys)

    def realtime_set(self, preset, value):
        name = os.path.basename(os.path.splitext(preset)[0])
        temp_key = self.temp_key
        if temp_key and temp_key.name.endswith(name):
            temp_key.value = value
            return

        body = self._human.body_obj
        vert_count = len(body.data.vertices)
        obj_coords = np.empty(vert_count * 3, dtype=np.float64)
        body.data.vertices.foreach_get("co", obj_coords)

        filepath = os.path.join(get_prefs().filepath, preset)
        new_key_relative_coords = np.load(filepath)
        new_key_coords = obj_coords + new_key_relative_coords

        current_sk_values = self._human.props.sk_values

        if temp_key:
            permanent_key_coords = np.empty(vert_count * 3, dtype=np.float64)
            self.permanent_key.data.foreach_get("co", permanent_key_coords)
            temp_key_coords = np.empty(vert_count * 3, dtype=np.float64)
            self.temp_key.data.foreach_get("co", temp_key_coords)

            relative_temp_coords = temp_key_coords - obj_coords
            permanent_key_coords += relative_temp_coords

            old_temp_key_name = temp_key.name.replace("LIVE_KEY_TEMP_", "")
            current_sk_values[old_temp_key_name] = temp_key.value

            if temp_key and name in current_sk_values:
                old_value = current_sk_values[name]
                permanent_key_coords -= new_key_relative_coords * old_value

            self.permanent_key.data.foreach_set("co", permanent_key_coords)

        if not temp_key:
            temp_key = self._human.body_obj.shape_key_add(name="LIVE_KEY_TEMP_" + name)

        self.temp_key.data.foreach_set("co", new_key_coords)
        self.temp_key.name = "LIVE_KEY_TEMP_" + name

        temp_key.value = value

    def reset(self):
        for sk in self.shape_keys:
            sk.value = 0

    def randomize(self, ff_subcateg="all", use_bell_curve=False):
        prefix_dict = self._get_ff_prefix_dict()
        face_sk = [
            sk for sk in self.shape_keys if sk.name.startswith(prefix_dict[ff_subcateg])
        ]
        all_v = 0
        for sk in face_sk:
            if use_bell_curve:
                new_value = np.random.normal(loc=0, scale=0.5)
            else:
                new_value = random.uniform(sk.slider_min, sk.slider_max)
            all_v += new_value
            sk.value = new_value

    @staticmethod
    def _get_ff_prefix_dict() -> dict:
        """Returns facial features prefix dict

        Returns:
            dict: key: internal naming of facial feature category
                value: naming prefix of shapekeys that belong to that category
        """
        prefix_dict = {
            "all": "ff",
            "u_skull": ("ff_a", "ff_b"),
            "eyes": "ff_c",
            "l_skull": "ff_d",
            "nose": "ff_e",
            "mouth": "ff_f",
            "chin": "ff_g",
            "cheeks": "ff_h",
            "jaw": "ff_i",
            "ears": "ff_j",
            "custom": "ff_x",
        }

        return prefix_dict
