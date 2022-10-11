# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from HumGen3D.human.human import Human


class EyelashSettings:
    _startswith = "Eyelashes"

    def __init__(self, _human: "Human") -> None:
        self._human = _human
        self._startswith = "Eyelash"
