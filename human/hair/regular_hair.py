# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements class for manipulating the hair on the top of the head of the human."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.human.hair.basehair import ImportableHair


class RegularHairSettings(ImportableHair):
    """Class for manipulating regular (head) hair of human."""

    _haircap_tag = "hg_main_hair"
    _pcoll_name: str = "hair"
    _pcoll_gender_split: bool = True
    _notstartswith = ("Eye", "fh")
    _mat_idx = 2

    def __init__(self, _human: "Human") -> None:
        super().__init__()
        self._human = _human
        self._pcoll_name = "hair"
        self._pcoll_gender_split = True

    def as_dict(self) -> dict[str, Any]:
        """Returns dict of eyebrow settings.

        Returns:
            dict[str, Any]: Dict of regular hair settings
        """
        return_dict = {
            "set": self._active,
        }

        return_dict.update(super().as_dict())
        return return_dict
