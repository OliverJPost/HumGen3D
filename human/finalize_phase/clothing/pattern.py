import os
from pathlib import Path

import bpy
from HumGen3D.backend import get_prefs
from HumGen3D.human.base.decorators import injected_context
from HumGen3D.human.base.pcoll_content import PreviewCollectionContent
from HumGen3D.user_interface.feedback_func import ShowMessageBox


class PatternSettings(PreviewCollectionContent):
    def __init__(self, _human) -> None:
        self._human = _human
        self._pcoll_gender_split = False
        self._pcoll_name = "patterns"
        self._node_names = (
            "HG_Pattern",
            "HG_Pattern_Mapping",
            "HG_Pattern_Coordinates",
        )

    def set(self, preset, obj):
        """
        Loads the pattern that is the current active item in the patterns preview_collection
        """
        pref = get_prefs()
        mat = obj.active_material

        for node_name in self._node_names:
            self._create_node_if_doesnt_exist(node_name)

        img_node = mat.node_tree.nodes["HG_Pattern"]

        filepath = os.path.join(pref.filepath, preset)
        images = bpy.data.images
        pattern = images.load(filepath, check_existing=True)

        img_node.image = pattern

    def _set(self, context):
        obj = context.object
        active_item = getattr(context.scene.HG3D, f"pcoll_{self._pcoll_name}")
        self.set(active_item, obj)

    def remove(self, obj):
        mat = obj.active_material
        for node_name in self._node_names:
            mat.node_tree.nodes.remove(mat.node_tree.nodes.get(node_name))

            pattern_input = mat.node_tree.nodes["HG_Control"].inputs["Pattern"]
            pattern_input.default_value = (
                0,
                0,
                0,
                1,
            )

    def _create_node_if_doesnt_exist(self, name) -> bpy.types.ShaderNode:
        """Returns the node, creating it if it doesn't exist

        Args:
            name (str): name of node to check

        Return
            node (ShaderNode): node that was being searched for
        """
        # try to find the node, returns it if it already exists
        for node in self.nodes:
            if node.name == name:
                return node

        # adds the node, because it doesn't exist yet
        type_dict = {
            "HG_Pattern": "ShaderNodeTexImage",
            "HG_Pattern_Mapping": "ShaderNodeMapping",
            "HG_Pattern_Coordinates": "ShaderNodeTexCoord",
        }

        node = self.nodes.new(type_dict[name])
        node.name = name

        link_dict = {
            "HG_Pattern": (0, "HG_Control", 9),
            "HG_Pattern_Mapping": (0, "HG_Pattern", 0),
            "HG_Pattern_Coordinates": (2, "HG_Pattern_Mapping", 0),
        }
        target_node = self.nodes[link_dict[name][1]]
        self.links.new(
            node.outputs[link_dict[name][0]],
            target_node.inputs[link_dict[name][2]],
        )

        return node
