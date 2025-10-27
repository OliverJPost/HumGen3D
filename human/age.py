"""Module for changing the age of the human."""

from typing import TYPE_CHECKING, Any, Union

from HumGen3D.common.shadernode import FACTOR_INPUT_NAME, NodeInput
from HumGen3D.human.keys.keys import (
    LiveKeyItem,
    ShapeKeyItem,
    update_livekey_collection,
)
from HumGen3D.human.skin.skin import SkinNodes

if TYPE_CHECKING:
    from HumGen3D.human.human import Human


class AgeSettings:
    """Class to edit age of the human."""

    def __init__(self, human: "Human") -> None:
        """Initiate instance for modifying body of human.

        Args:
            human (Human): Human instance.
        """
        self._human: "Human" = human

        self.age_color = NodeInput(human.skin, "Age_Multiply", FACTOR_INPUT_NAME)
        self.age_wrinkles = NodeInput(human.skin, "HG_Age", "Strength")

    @property
    def _current(self) -> int:
        try:
            return self._human.objects.body["Age"]
        except KeyError:
            return 30

    @property
    def keys(self) -> list[Union["ShapeKeyItem", "LiveKeyItem"]]:
        """Get a list of all shapekeys and livekeys that affect the age of the human.

        Returns:
            list[Union[ShapeKeyItem, LiveKeyItem]]: List of shapekeys and livekeys.
        """
        return self._human.keys.filtered("special", "age")

    def set(self, age: int, realtime: bool = False) -> None:  # noqa A003
        """Set the age of the human.

        Args:
            age (int): Age to set. UI uses increments of 10.
            realtime: (bool): Use true if the value will be changed in realtime by a
                slider in the UI.
        """
        # Return early if same age, prevents crash when user cancels the slider.
        if age == self._current:
            return

        normal_value = min((age - 10) / 10, 2.5)
        young_value = (-0.1 * age + 3) if age < 30 else 0
        if age > 30:
            skin_multiply_value = (age - 30) / 30
        else:
            skin_multiply_value = 0
        if age > 40:
            age_key_value = (age - 40) / 30
        else:
            age_key_value = 0

        young_key = next((k for k in self.keys if k.name == "aged_young"), None)
        if not young_key:
            update_livekey_collection()
            young_key = next(k for k in self.keys if k.name == "aged_young")

        if realtime:
            young_key.as_bpy().value = young_value
        else:
            young_key.value = young_value
        for key in self.keys:
            if key == young_key:
                continue
            if realtime:
                key.as_bpy().value = age_key_value
            else:
                key.value = age_key_value

        nodes = SkinNodes.from_human(self._human)
        node_age_normal = nodes.get("HG_Age")
        node_age_normal.inputs["Strength"].default_value = age_key_value * 6

        node_age_color = nodes.get("Age_Multiply")
        node_age_color.inputs[FACTOR_INPUT_NAME].default_value = age_key_value

        node_age_color = nodes.get("Cavity_Multiply")
        node_age_color.inputs[FACTOR_INPUT_NAME].default_value = skin_multiply_value

        node_normal = nodes.get("Normal Map")
        node_normal.inputs["Strength"].default_value = normal_value

        self._human.objects.body["Age"] = age

    def as_dict(self) -> dict[str, Any]:
        """Get the age settings of the human as a dictionary.

        Returns:
            dict: Dictionary with the age settings of the human.
        """
        return {
            "set": self._current,
            "age_color": self.age_color.value,
            "age_wrinkles": self.age_wrinkles.value,
        }

    def set_from_dict(self, data: dict[str, Any]) -> None:
        """Set the age of the human from a dictionary.

        Args:
            data (dict): Dictionary with the age of the human.
        """
        if data["set"] != 30:
            self.set(data["set"])
        self.age_color.value = data["age_color"]
        self.age_wrinkles.value = data["age_wrinkles"]

        return []
