# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""The node setup of baked materials, as the file exporters read it.

Blender's glTF exporter writes a material as alphaMode MASK only when the alpha
runs through a Math Round node, and the FBX and glTF exporters only find a
normal map whose image is linked straight to the Normal Map node. Both are
checked here without baking anything.
"""

import bpy
import pytest

from HumGen3D.human.process.export import direct_normal_maps
from HumGen3D.human.process.textures import (
    DIRECTX_FLIP_NODE,
    _link_alpha,
    _link_directx_normal,
)
from HumGen3D.tests.test_fixtures import *  # noqa: F401, F403


def _material(name: str):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    image = nodes.new("ShaderNodeTexImage")
    return material, nodes, material.node_tree.links, image, nodes["Principled BSDF"]


def test_alpha_of_cards_is_rounded():
    material, nodes, links, image, principled = _material("cards")
    _link_alpha(nodes, links, image.outputs["Alpha"], principled, clip=True)
    link = principled.inputs["Alpha"].links[0]
    assert link.from_node.type == "MATH" and link.from_node.operation == "ROUND"
    assert link.from_node.inputs[0].links[0].from_node == image
    bpy.data.materials.remove(material)


def test_alpha_of_haircap_is_linked_directly():
    material, nodes, links, image, principled = _material("cap")
    _link_alpha(nodes, links, image.outputs["Color"], principled, clip=False)
    assert principled.inputs["Alpha"].links[0].from_node == image
    bpy.data.materials.remove(material)


class _Objects:
    """Stands in for human.objects: iterates over the given objects."""

    def __init__(self, objects):
        self._objects = objects

    def __iter__(self):
        return iter(self._objects)


class _Human:
    def __init__(self, obj):
        self.objects = _Objects([obj])


@pytest.fixture
def directx_material():
    material, nodes, links, image, principled = _material("directx")
    normal_node = nodes.new("ShaderNodeNormalMap")
    links.new(normal_node.outputs["Normal"], principled.inputs["Normal"])
    _link_directx_normal(nodes, links, image, normal_node)
    mesh = bpy.data.meshes.new("directx")
    obj = bpy.data.objects.new("directx", mesh)
    obj.data.materials.append(material)
    yield material, image, normal_node, obj
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(mesh)
    bpy.data.materials.remove(material)


def test_directx_flip_is_bypassed_while_exporting(directx_material):
    material, image, normal_node, obj = directx_material
    color = normal_node.inputs["Color"]
    assert color.links[0].from_node.name == DIRECTX_FLIP_NODE, "The flip chain feeds the Normal Map node"

    with direct_normal_maps(_Human(obj)):
        assert color.links[0].from_node == image, "Exporters see the image directly"

    assert color.links[0].from_node.name == DIRECTX_FLIP_NODE, "The chain is put back afterwards"
    assert len(color.links) == 1


def test_materials_without_flip_are_left_alone():
    material, nodes, links, image, principled = _material("opengl")
    normal_node = nodes.new("ShaderNodeNormalMap")
    links.new(image.outputs["Color"], normal_node.inputs["Color"])
    links.new(normal_node.outputs["Normal"], principled.inputs["Normal"])
    mesh = bpy.data.meshes.new("opengl")
    obj = bpy.data.objects.new("opengl", mesh)
    obj.data.materials.append(material)
    try:
        with direct_normal_maps(_Human(obj)):
            assert normal_node.inputs["Color"].links[0].from_node == image
        assert normal_node.inputs["Color"].links[0].from_node == image
    finally:
        bpy.data.objects.remove(obj)
        bpy.data.meshes.remove(mesh)
        bpy.data.materials.remove(material)
