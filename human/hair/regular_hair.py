# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE


from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from HumGen3D.human.human import Human
from HumGen3D.human.hair.basehair import ImportableHair


class RegularHairSettings(ImportableHair):
    _pcoll_name: str = "hair"
    _pcoll_gender_split: bool = True
    _notstartswith = ("Eye", "fh")

    def __init__(self, _human: "Human") -> None:
        self._human = _human
        self._notstartswith = ("Eye", "ff_")
        self._pcoll_name = "hair"
        self._pcoll_gender_split = True
