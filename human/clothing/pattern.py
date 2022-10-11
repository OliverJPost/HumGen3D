# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import os
import random
from typing import TYPE_CHECKING, cast

import bpy
from HumGen3D.backend.type_aliases import C
from bpy.types import ShaderNode  # type:ignore

if TYPE_CHECKING:
    from HumGen3D.human.human import Human
from HumGen3D.backend import get_prefs
from HumGen3D.human.base.decorators import injected_context
from HumGen3D.human.base.pcoll_content import PreviewCollectionContent


class PatternSettings(PreviewCollectionContent):
    def __init__(self, _human: "Human") -> None:
        self._human = _human
        self._pcoll_gender_split = False
        self._pcoll_name = "pattern"
        self._node_names = (
            "HG_Pattern",
            "HG_Pattern_Mapping",
            "HG_Pattern_Coordinates",
        )

    def set(self, preset: str, obj: bpy.types.Object) -> None:
        """
        Loads the pattern that is the current active item in the patterns preview_collection
        """
        pref = get_prefs()
        mat = obj.active_material

        for node_name in self._node_names:
            self._create_node_if_doesnt_exist(node_name)

        img_node = mat.node_tree.nodes["HG_Pattern"]  # type:ignore[index]

        filepath = os.path.join(pref.filepath, preset)
        images = bpy.data.images
        pattern = images.load(filepath, check_existing=True)

        img_node.image = pattern

    @injected_context
    def set_random(self, obj: bpy.types.Object, context: C = None) -> None:
        options = self.get_options(context)
        chosen = random.choice(options)
        self.set(chosen, obj)

    def _set(self, context: bpy.types.Context) -> None:
        obj = context.object
        active_item = getattr(context.scene.HG3D, f"pcoll_{self._pcoll_name}")
        self.set(active_item, obj)

    def remove(self, obj: bpy.types.Object) -> None:
        mat = obj.active_material
        for node_name in self._node_names:
            mat.node_tree.nodes.remove(
                mat.node_tree.nodes.get(node_name)  # type:ignore[arg-type]
            )
            pattern_input = mat.node_tree.nodes[  # type:ignore[call-overload]
                "HG_Control"
            ].inputs[  # type:ignore[index]
                "Pattern"
            ]
            pattern_input.default_value = (
                0,
                0,
                0,
                1,
            )

    def _create_node_if_doesnt_exist(self, name: str) -> ShaderNode:
        """Returns the node, creating it if it doesn't exist

        Args:
            name (str): name of node to check

        Return
            node (ShaderNode): node that was being searched for
        """
        # try to find the node, returns it if it already exists
        for node in self._human.skin.nodes:
            if node.name == name:
                return cast(ShaderNode, node)

        # adds the node, because it doesn't exist yet
        type_dict = {
            "HG_Pattern": "ShaderNodeTexImage",
            "HG_Pattern_Mapping": "ShaderNodeMapping",
            "HG_Pattern_Coordinates": "ShaderNodeTexCoord",
        }

        node: ShaderNode = self._human.skin.nodes.new(type_dict[name])  # type:ignore
        node.name = name

        link_dict = {
            "HG_Pattern": (0, "HG_Control", 9),
            "HG_Pattern_Mapping": (0, "HG_Pattern", 0),
            "HG_Pattern_Coordinates": (2, "HG_Pattern_Mapping", 0),
        }
        target_node = self._human.skin.nodes[link_dict[name][1]]  # type:ignore[index]
        self._human.skin.links.new(
            node.outputs[link_dict[name][0]],
            target_node.inputs[link_dict[name][2]],
        )

        return cast(ShaderNode, node)
