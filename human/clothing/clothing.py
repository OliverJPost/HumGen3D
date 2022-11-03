from typing import TYPE_CHECKING

from .footwear import FootwearSettings
from .outfit import OutfitSettings

if TYPE_CHECKING:
    from human.human import Human


class ClothingSettings:
    def __init__(self, human: "Human") -> None:
        self._human = human

    @property  # TODO make cached
    def outfit(self) -> OutfitSettings:
        return OutfitSettings(self._human)

    @property  # TODO make cached
    def footwear(self) -> FootwearSettings:
        return FootwearSettings(self._human)
