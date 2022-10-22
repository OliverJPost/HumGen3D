# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from typing import TYPE_CHECKING, List, Union

import numpy as np
from HumGen3D.backend.type_aliases import C
from HumGen3D.human.base.decorators import injected_context

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.human.keys.keys import LiveKeyItem, ShapeKeyItem

from ..base.prop_collection import PropCollection


class FaceKeys(PropCollection):
    def __init__(self, human: "Human") -> None:
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
    def keys(self) -> List[Union[LiveKeyItem, ShapeKeyItem]]:
        return self._human.keys.filtered("face_proportions")

    @property
    def shape_keys(self) -> PropCollection:
        sks = self._human.keys
        ff_keys = [sk for sk in sks if sk.name.startswith("ff_")]
        pr_keys = [sk for sk in sks if sk.name.startswith("pr_")]
        return PropCollection(ff_keys + pr_keys)

    def reset(self) -> None:
        for sk in self.shape_keys:
            sk.value = 0

    @injected_context
    def randomize(
        self, subcategory: str = "all", use_bell_curve: bool = False, context: C = None
    ) -> None:
        if subcategory.lower() == "all":
            keys = self.keys
        else:
            keys = [key for key in self.keys if key.subcategory == subcategory]
        all_v = 0.0
        for key in keys:
            if use_bell_curve:
                new_value = np.random.normal(loc=0, scale=0.5)
            else:
                new_value = np.random.normal(loc=0, scale=0.5)
            all_v += new_value
            key.set_without_update(new_value)

        self._human.keys.update_human_from_key_change(context)
