# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Contains PatternSettings, for changing patterns on individual clothing items."""

import os
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast

import bpy
from bpy.types import ShaderNode  # type:ignore
from HumGen3D.common.type_aliases import C

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.backend import get_prefs
from HumGen3D.common.decorators import injected_context
from HumGen3D.human.common_baseclasses.pcoll_content import PreviewCollectionContent


@dataclass
class _PatternNode:
    node_name: str
    node_type: Literal["ShaderNodeTexImage", "ShaderNodeMapping", "ShaderNodeTexCoord"]
    output_slot: int
    input_slot: int
    output_node_name: str

    def exists_in(self, mat: bpy.types.Material) -> bool:
        return self.node_name in mat.node_tree.nodes

    def create_in(self, mat: bpy.types.Material) -> None:
        node_tree = mat.node_tree
        node = node_tree.nodes.new(self.node_type)
        node.name = self.node_name
        node.label = self.node_name
        node_tree.links.new(
            node.outputs[self.output_slot],
            node_tree.nodes[self.output_node_name].inputs[self.input_slot],
        )

    def remove_from(self, mat: bpy.types.Material) -> None:
        node_tree = mat.node_tree
        node = node_tree.nodes[self.node_name]
        node_tree.nodes.remove(node)

        # Make sure the pattern input is set to black
        pattern_input = mat.node_tree.nodes["HG_Control"].inputs["Pattern"]
        pattern_input.default_value = (0, 0, 0, 1)


class PatternSettings(PreviewCollectionContent):
    """Class for changing patterns on individual clothing items."""

    _pcoll_gender_split = False
    _pcoll_name = "pattern"
    _nodes = [
        _PatternNode(
            node_name="HG_Pattern",
            node_type="ShaderNodeTexImage",
            output_slot=0,
            input_slot=9,
            output_node_name="HG_Control",
        ),
        _PatternNode(
            node_name="HG_Pattern_Mapping",
            node_type="ShaderNodeMapping",
            output_slot=0,
            input_slot=0,
            output_node_name="HG_Pattern",
        ),
        _PatternNode(
            node_name="HG_Pattern_Coordinates",
            node_type="ShaderNodeTexCoord",
            output_slot=2,
            input_slot=0,
            output_node_name="HG_Pattern_Mapping",
        ),
    ]

    def __init__(self, _human: "Human") -> None:
        """Creates new instance to manipulate pattern of clothing items.

        Args:
            _human (Human): Human instance.
        """
        self._human = _human

    def set(self, preset: str, obj: bpy.types.Object) -> None:  # noqa: A003
        """Loads passed pattern on passed object.

        NOTE: Expects passed object to use HG clothing material.

        Args:
            preset (str): Relative path of pattern to load.
            obj (bpy.types.Object): Object to apply pattern to.
        """
        pref = get_prefs()
        mat = obj.active_material

        if not self._is_hg_material(mat):
            raise ValueError("Passed object does not use HG material.")

        self._active = preset

        for node_template in self._nodes:
            if not node_template.exists_in(mat):
                node_template.create_in(mat)

        img_node = mat.node_tree.nodes["HG_Pattern"]  # type:ignore

        filepath = os.path.join(pref.filepath, preset)
        images = bpy.data.images
        pattern = images.load(filepath, check_existing=True)

        img_node.image = pattern

    @injected_context
    def set_random(self, obj: bpy.types.Object, context: C = None) -> None:
        """Set a random pattern as active on the passed object.

        Args:
            obj (bpy.types.Object): Object to add pattern to.
            context (C): Blender context. bpy.context if not provided.
        """
        options = self.get_options(context)
        chosen = random.choice(options)
        self.set(chosen, obj)

    def remove(self, obj: bpy.types.Object) -> None:
        """Remove pattern from passed object.

        Args:
            obj (bpy.types.Object): Object to remove pattern from.
        """
        mat = obj.active_material
        for node in self._nodes:
            node.remove_from(mat)

    def _set(self, context: bpy.types.Context) -> None:
        """Internal method for calling from update function.

        Args:
            context (bpy.types.Context): Blender context.
        """
        obj = context.object
        active_item = getattr(context.scene.HG3D.pcoll, self._pcoll_name)
        self.set(active_item, obj)

    def _is_hg_material(self, mat: bpy.types.Material) -> bool:
        """Checks if passed material is an HG material."""
        if mat is None:
            return False

        node_tree = mat.node_tree
        if node_tree is None:
            return False

        if "HG_Control" not in node_tree.nodes:
            return False

        return True
