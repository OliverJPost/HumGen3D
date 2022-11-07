from typing import Any, Union

from bpy.types import NodeSocket  # type:ignore


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
        node = self.instance.nodes.get(self.node_name)
        value = node.inputs[self.input_name].default_value

        if not isinstance(value, (int, float, str)):
            value = tuple(value)

        return value

    @value.setter
    def value(self, value: Any) -> None:
        # Iterate through nodes because haircard objects will have multiple materials
        # with the sae node
        for node in [n for n in self.instance.nodes if n.name == self.node_name]:
            node.inputs[self.input_name].default_value = value

    def as_bpy(self) -> NodeSocket:
        return self.instance.nodes[self.node_name].inputs[self.input_name]
