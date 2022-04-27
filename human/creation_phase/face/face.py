from ...base.prop_collection import PropCollection

import numpy as np
import random


class FaceKeys(PropCollection):
    def __init__(self, human):
        self._human = human
        sks = human.shape_keys
        ff_keys = [sk for sk in sks if sk.name.startswith("ff_")]
        pr_keys = [sk for sk in sks if sk.name.startswith("pr_")]
        super(FaceKeys, self).__init__(ff_keys + pr_keys)

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

    def reset(self):
        for sk in self:
            sk.value = 0

    def randomize(self, ff_subcateg="all", use_bell_curve=False):
        prefix_dict = self._get_ff_prefix_dict()
        face_sk = [
            sk for sk in self if sk.name.startswith(prefix_dict[ff_subcateg])
        ]
        all_v = 0
        for sk in face_sk:
            if use_bell_curve:
                new_value = np.random.normal(loc=0, scale=0.5)
            else:
                new_value = random.uniform(sk.slider_min, sk.slider_max)
            all_v += new_value
            sk.value = new_value

    def _get_ff_prefix_dict(self) -> dict:
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
