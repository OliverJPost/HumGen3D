# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Module containing ClothingSettings.

This is an interface class for getting to OutfitSettings and FootwearSettings.
"""

import os
from typing import TYPE_CHECKING, Any

from .footwear import FootwearSettings
from .outfit import OutfitSettings

if TYPE_CHECKING:
    from HumGen3D.human.human import Human


class ClothingSettings:
    """Interface class for accessing OutfitSettings and FootwearSettings."""

    def __init__(self, human: "Human") -> None:
        """Initiate instance for modifying clothing of human.

        Args:
            human (Human): Human instance.
        """
        self._human = human

    @property  # TODO make cached
    def outfit(self) -> OutfitSettings:
        """Use this property to access OutfitSettings.

        OutfitSettings allows you to change the outfits (excluding footwear) of
        the human.

        Returns:
            OutfitSettings: Instance of OutfitSettings belonging to this human.
        """
        return OutfitSettings(self._human)

    @property  # TODO make cached
    def footwear(self) -> FootwearSettings:
        """Use this property to access FootwearSettings.

        FootwearSettings allows you to change the footwear of the human.

        Returns:
            FootwearSettings: Instance of FootwearSettings belonging to this human.
        """
        return FootwearSettings(self._human)

    def as_dict(self) -> dict[str, dict[str, Any]]:
        """Returns dict of clothing settings.

        Returns:
            dict[str, dict[str, Any]]: Dict of clothing settings.
        """
        return_dict = {
            "outfit": self.outfit.as_dict(),
            "footwear": self.footwear.as_dict(),
        }
        return return_dict

    def set_from_dict(self, data: dict[str, Any]) -> list[str]:
        """Set clothing settings from dict.

        Args:
            data (dict[str, Any]): Dict of clothing settings.

        Returns:
            list[str]: List of errors occurred during setting.
        """
        errors = []
        if data["outfit"]["set"] is not None:
            try:
                self.outfit.set(data["outfit"]["set"])
            except FileNotFoundError:
                outfitname = os.path.basename(data["outfit"]["set"])
                errors.append("Outfit error:")
                errors.append(f"'{outfitname}' not found.")
        if data["footwear"]["set"] is not None:
            try:
                self.footwear.set(data["footwear"]["set"])
            except FileNotFoundError:
                footwearname = os.path.basename(data["footwear"]["set"])
                errors.append("Footwear error:")
                errors.append(f"'{footwearname}' not found.")

        return errors
