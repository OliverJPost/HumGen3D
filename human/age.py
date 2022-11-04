"""Module for changing the age of the human."""

from typing import TYPE_CHECKING, Union

from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C
from HumGen3D.human.keys.keys import LiveKeyItem, ShapeKeyItem
from HumGen3D.human.skin.skin import SkinNodes, create_node_property

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

    @property
    def _current(self) -> int:
        try:
            return self._human.body_obj["Age"]
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
        normal_value = min((age - 10) / 10, 4.0)
        if age > 30:
            skin_multiply_value = (age - 30) / 30
        else:
            skin_multiply_value = 0
        if age > 40:
            age_key_value = (age - 40) / 30
        else:
            age_key_value = 0

        for key in self.keys:
            if realtime:
                key.as_bpy().value = age_key_value
            else:
                key.value = age_key_value

        nodes = SkinNodes(self._human)
        node_age_normal = nodes.get("HG_Age")
        node_age_normal.inputs["Strength"].default_value = age_key_value * 6

        node_age_color = nodes.get("Age_Multiply")
        node_age_color.inputs["Fac"].default_value = age_key_value

        node_age_color = nodes.get("Cavity_Multiply")
        node_age_color.inputs["Fac"].default_value = skin_multiply_value

        node_normal = nodes.get("Normal Map")
        node_normal.inputs["Strength"].default_value = normal_value

        self._human.body_obj["Age"] = age
