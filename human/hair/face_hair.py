# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements class for manipulating face hair of human."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.human.hair.basehair import ImportableHair


class FacialHairSettings(ImportableHair):
    """Class for manipulating facial hair of human."""

    _haircap_tag = "hg_face_hair"
    _pcoll_name = "face_hair"
    _pcoll_gender_split = False
    _startswith = "fh"
    _mat_idx = 3

    def __init__(self, _human: "Human") -> None:
        super().__init__()
        if _human.gender == "female":
            raise NotImplementedError(
                "Facial hair is currently not implemented for female humans"
            )

        self._human = _human
        self._startswith = "ff_"

    def as_dict(self) -> dict[str, Any]:
        """Returns dict of face hair settings.

        Returns:
            dict[str, dict[str, Any]]: Dict of face hair settings
        """
        return_dict = {
            "set": self._active,
        }
        return_dict.update(super().as_dict())
        return return_dict
