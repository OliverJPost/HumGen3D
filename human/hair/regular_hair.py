# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy
from HumGen3D.human.base.decorators import injected_context
from HumGen3D.human.hair.basehair import ImportableHair


class RegularHairSettings(ImportableHair):
    _pcoll_name: str = "hair"
    _pcoll_gender_split: bool = True
    _notstartswith = ("Eye", "fh")

    def __init__(self, _human):
        self._human = _human
        self._notstartswith = ("Eye", "ff_")
        self._pcoll_name = "hair"
        self._pcoll_gender_split = True
