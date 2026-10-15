# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""The node setup of baked materials, as the file exporters read it.

Blender's glTF exporter writes a material as alphaMode MASK only when the alpha
runs through a Math Round node, and the FBX and glTF exporters only find a
normal map whose image is linked straight to the Normal Map node. Both are
checked here without baking anything.
"""

import bpy
import numpy as np
import pytest

from HumGen3D.human.process.export import direct_normal_maps
from HumGen3D.human.process.textures import (
    DIRECTX_FLIP_NODE,
    HAIR_ALPHA_CUTOFF,
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


def test_alpha_of_cards_is_cut_out():
    material, nodes, links, image, principled = _material("cards")
    _link_alpha(nodes, links, image.outputs["Alpha"], principled, clip=True)
    link = principled.inputs["Alpha"].links[0]
    assert link.from_node.type == "MATH" and link.from_node.operation == "GREATER_THAN"
    assert abs(link.from_node.inputs[1].default_value - HAIR_ALPHA_CUTOFF) < 1e-6
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


def _uv_box_alpha(obj, image):
    """The alpha of an image inside the UV bounding box of an object."""
    import numpy as np

    width, height = image.size
    pixels = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(pixels)
    pixels = pixels.reshape(height, width, 4)
    uvs = np.array([d.uv[:] for d in obj.data.uv_layers.active.data])
    x0, y0 = (uvs.min(axis=0) * (width, height)).astype(int)
    x1, y1 = (uvs.max(axis=0) * (width, height)).astype(int) + 1
    return pixels[y0:y1, x0:x1, 3]


def test_shared_cap_texture_holds_eyebrows_and_eyelashes(male_human):
    """The eyebrows and eyelashes are baked into the cap image they share with
    the scalp cap, and survive the later passes."""
    from HumGen3D.human.process.settings import TextureBakeSettings

    copy = male_human.duplicate(bpy.context)
    try:
        copy.process.convert_to_haircards("low", context=bpy.context)
        settings = TextureBakeSettings()
        settings.resolution = {key: 64 for key in settings.resolution}
        settings.resolution["hair"] = 256
        settings.haircap_in_skin = False
        copy.process.bake_textures(settings, folder=None, context=bpy.context)
        caps = {
            obj.name: obj for obj in copy.objects.haircards if "Brows" in obj.name or "Eyelashes" in obj.name
        }
        assert len(caps) == 2, caps
        for name, obj in caps.items():
            material = obj.material_slots[0].material
            image = next(
                n.image for n in material.node_tree.nodes if n.type == "TEX_IMAGE" and "BaseColor" in n.image.name
            )
            alpha = _uv_box_alpha(obj, image)
            # The alpha is the strand texture averaged down from 4096 to the
            # 256 of this test, so even the densest eyelash texel is well below one
            assert alpha.max() > 0.2, f"{name}: no alpha in its part of {image.name}, max {alpha.max():.3f}"
    finally:
        copy.delete()


def test_haircap_in_skin(male_human):
    """The caps of the hair and eyebrows go into the skin texture and their
    meshes are left out; the eyelashes and the cards stay."""
    from HumGen3D.human.process.haircap_skin import UV_LAYER_PREFIX
    from HumGen3D.human.process.settings import TextureBakeSettings

    copy = male_human.duplicate(bpy.context)
    try:
        copy.process.convert_to_haircards("low", context=bpy.context)
        body = copy.objects.body
        uv_layers = [layer.name for layer in body.data.uv_layers]
        settings = TextureBakeSettings()
        settings.resolution = {key: 64 for key in settings.resolution}
        settings.resolution["hair"] = 256
        copy.process.bake_textures(settings, folder=None, context=bpy.context)

        assert [layer.name for layer in body.data.uv_layers] == uv_layers
        assert not any(layer.startswith(UV_LAYER_PREFIX) for layer in uv_layers)
        names = [obj.name for obj in copy.objects.haircards]
        assert not any("Brows" in name for name in names), names
        assert any("Eyelashes" in name for name in names), names
        for obj in copy.objects.haircards:
            if "hg_main_hair" in obj:
                # Only the cards are left, as an object of cards
                assert len(obj.data.materials) == 1
                assert "hg_haircard_cards" in obj
        skin = body.material_slots[0].material
        assert not any(
            n.type == "TEX_IMAGE" and n.image and n.image.name.startswith("hg_capskin")
            for n in skin.node_tree.nodes
        )
    finally:
        copy.delete()


def test_haircap_projection_fades_out_past_the_border(male_human):
    """Corners of the body under a cap show it, corners past its border don't:
    without the weight the border row of the cap texture was smeared over the
    skin next to the eyebrows."""
    from mathutils.bvhtree import BVHTree

    from HumGen3D.human.process import haircap_skin

    copy = male_human.duplicate(bpy.context)
    try:
        copy.process.convert_to_haircards("low", context=bpy.context)
        body = copy.objects.body
        brows = next(obj for obj in copy.objects.haircards if "hg_eyebrows" in obj)
        assert haircap_skin._project_uvs(body, [(brows, 0)], "hg_cap_test")
        mesh = body.data
        attribute = mesh.color_attributes["hg_cap_test_weight"]
        colors = np.empty(len(mesh.loops) * 4, dtype=np.float32)
        attribute.data.foreach_get("color", colors)
        weights = colors.reshape(-1, 4)[:, 0]
        uvs = np.empty(len(mesh.loops) * 2, dtype=np.float32)
        mesh.uv_layers["hg_cap_test"].data.foreach_get("uv", uvs)
        mapped = uvs.reshape(-1, 2)[:, 1] > -0.5

        vertices, triangles, _ = haircap_skin._cap_triangles([(brows, 0)], bpy.context)
        tree = BVHTree.FromPolygons(vertices, triangles)
        coords = haircap_skin._evaluated_coords(body, bpy.context)
        loop_verts = np.empty(len(mesh.loops), dtype=np.int32)
        mesh.loops.foreach_get("vertex_index", loop_verts)
        distances = np.array(
            [tree.find_nearest(coords[v], 1.0)[3] for v in loop_verts[mapped]]
        )
        under = distances < haircap_skin.FADE_START
        past = distances > haircap_skin.FADE_END
        assert under.sum() > 20 and past.sum() > 20
        assert (weights[mapped][under] == 1.0).all()
        assert (weights[mapped][past] == 0.0).all()
        assert (weights[~mapped] == 0.0).all()

        haircap_skin.remove_uv_layers(copy)
        assert "hg_cap_test" not in mesh.uv_layers
        assert not any(a.name.startswith("hg_cap_") for a in mesh.attributes)
    finally:
        copy.delete()
