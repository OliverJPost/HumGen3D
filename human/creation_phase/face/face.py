from ...base.prop_collection import PropCollection


class FaceKeys(PropCollection):
    def __init__(self, human):
        self._human = human
        sks = human.shape_keys
        ff_keys = [sk for sk in sks if sk.name.startswith("ff_")]
        pr_keys = [sk for sk in sks if sk.name.startswith("pr_")]
        super(FaceKeys, self).__init__(ff_keys + pr_keys)

        facekeys_dict = {
            "u_skull": ("ff_a", "ff_b"),
            "eyes": "ff_c_eye",
            "l_skull": "ff_d",
            "nose": "ff_e_nose",
            "mouth": "ff_f_lip",
            "chin": "ff_g_chin",
            "cheeks": "ff_h_cheek",
            "jaw": "ff_i_jaw",
            "ears": "ff_j_ear",
            "custom": "ff_x",
        }

        for type_name, prefix in facekeys_dict.items():
            setattr(
                FaceKeys,
                type_name,
                property(self._set_prop(type_name, prefix)),
            )

    def _set_prop(self, type_name, prefix):
        if not hasattr(self, f"_{type_name}"):
            filtered_sks = [sk for sk in self if sk.name.startswith(prefix)]
            setattr(self, f"_{type_name}", PropCollection(filtered_sks))
        return getattr(self, f"_{type_name}")
