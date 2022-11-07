# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from typing import TYPE_CHECKING

from HumGen3D.human.hair.basehair import BaseHair

if TYPE_CHECKING:
    from HumGen3D.human.human import Human


class EyelashSettings(BaseHair):
    _haircap_tag = "hg_eyelashes"
    _startswith = "Eyelashes"
    _mat_idx = 1

    def __init__(self, _human: "Human") -> None:
        """Creates instance to mapipulate eyelash settings."""
        super().__init__()
        self._human = _human
        self._startswith = "Eyelash"
