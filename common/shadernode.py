"""Implements interface for interacting with inputs of Blender Shader Nodes.

This is used to interact with known nodes in the materials used by the addon.
"""
from typing import Any, Union

import bpy
from bpy.types import NodeSocket, UILayout

FACTOR_INPUT_NAME = "Factor" if bpy.app.version >= (3, 4, 0) else "Fac"
COLOR1_INPUT_NAME = 6 if bpy.app.version >= (3, 4, 0) else "Color1"
COLOR2_INPUT_NAME = 7 if bpy.app.version >= (3, 4, 0) else "Color2"


class NodeInput:
    """Representation of a Blender Shader Node input socket."""

    def __init__(
        self, instance: Any, node_nane: str, input_name: Union[str, int]
    ) -> None:
        self.instance = instance
        self.node_name = node_nane
        self.input_name = input_name

    @property
    def value(self) -> Any:
        """Get value of the default_value of the input socket.

        Returns:
            Any: Value of the default_value of the input socket. Most likely float or
                FloatVectorProperty
        """
        node = self.instance.nodes.get(self.node_name)
        value = node.inputs[self.input_name].default_value

        if not isinstance(value, (int, float, str)):
            value = tuple(value)

        return value

    @value.setter
    def value(self, value: Any) -> None:
        """Set the value of the default_value of the input socket.

        Args:
            value (Any): Value to set. Most likely float or FloatVectorProperty
        """
        # Iterate through nodes because haircard objects will have multiple materials
        # with the sae node
        for node in [n for n in self.instance.nodes if n.name == self.node_name]:
            node.inputs[self.input_name].default_value = value

    def as_bpy(self) -> NodeSocket:
        """Get a pointer to the Blender node input socket. Useful for sliders.

        Returns:
            NodeSocket: Pointer to the Blender node input socket.
        """
        nodes = self.instance.nodes.get(self.node_name)
        return nodes.inputs[self.input_name]

    def draw_prop(self, layout: UILayout, text: str) -> None:
        """Draw a slider for this input in the UI.

        Args:
            layout (UILayout): Layout to draw the slider in.
            text (str): Text to display next to the slider.
        """
        layout.prop(
            self.as_bpy(),
            "default_value",
            text=text,
            slider=True,
        )
