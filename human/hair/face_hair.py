# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.human.hair.basehair import ImportableHair


class FacialHairSettings(ImportableHair):
    _pcoll_name = "face_hair"
    _pcoll_gender_split = False
    _startswith = "fh"
    _mat_idx = 3

    def __init__(self, _human: "Human") -> None:
        """Create instance to manipulate facial hair settings."""
        if _human.gender == "female":
            raise NotImplementedError(
                "Facial hair is currently not implemented for female humans"
            )

        self._human = _human
        self._startswith = "ff_"
