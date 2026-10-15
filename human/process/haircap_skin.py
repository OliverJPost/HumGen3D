# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Paints the haircaps into the skin textures, see TextureBakeSettings.haircap_in_skin.

A haircap is a blended mesh a fraction of a millimetre above the skin. In an
engine that is a transparent skinned mesh, which sorts and depth-tests badly
against the skin under it (URP needed a dithered shader for it), and it costs
a draw call and a few thousand triangles for what is a texture on the skin.

So the caps of the scalp hair, face hair and eyebrows are baked as usual, then
painted over the skin material before the skin is baked: every corner of the
body gets the UV of the nearest point of the cap as a UV map of its own, and the
baked cap images are mixed over the skin inputs by their alpha through that
map. The skin bake then writes the hair into the skin textures, in the tangent
space of the skin, and the cap meshes are left out of the result. The caps of
the eyelashes are strips off the skin and stay meshes.

Past the border of a cap the nearest point of the cap is on its border, so the
corners there would smear the border row of the cap texture over the skin, up
to a centimetre of stretched hairs next to the eyebrows. Every corner also
gets a weight from its distance to the cap, 1 under the cap and 0 from two
millimetres away, and the cap is mixed in by its alpha times that weight.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import bpy
import numpy as np
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

from HumGen3D.human.hair.haircards import CARDS_KEY, _keep_slot

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

    from .textures import TextureSet

# The hair types whose cap lies on the skin
SKIN_CAP_TAGS = ("hg_main_hair", "hg_face_hair", "hg_eyebrows")
# Body corners further than this from a cap get no cap UV, unless their face
# has a corner closer: the faces at the border of a cap are mapped whole, so
# the cap doesn't end on a jagged line of faces
NEAR_DISTANCE = 0.006
# How far a face at the border of a cap may reach for the nearest point of it
REACH_DISTANCE = 0.05
# UV of the corners away from the caps, their weight mixes no cap in
OUTSIDE_UV = (-1.0, -1.0)
UV_LAYER_PREFIX = "hg_cap_"
# The weight of a corner is 1 up to the first distance from the cap and 0 from
# the second: the skin lies within a millimetre under a cap, a corner further
# away is past its border
FADE_START = 0.001
FADE_END = 0.002
WEIGHT_SUFFIX = "_weight"
# Largest UV extent of a body face that is projected corner by corner; more is
# a face across a seam of the cap, a body face is a few cap texels wide
SEAM_SPAN = 0.1


def is_skin_cap(obj: bpy.types.Object, slot: int) -> bool:
    """Whether a material slot of a hair card object holds a cap on the skin."""
    return (
        slot == 0
        and CARDS_KEY not in obj
        and "hg_haircard" in obj
        and any(tag in obj for tag in SKIN_CAP_TAGS)
    )


def has_skin_caps(texture_set: "TextureSet") -> bool:
    return not texture_set.is_cards and any(is_skin_cap(obj, slot) for obj, slot in texture_set.slots)


def only_skin_caps(texture_set: "TextureSet") -> bool:
    """A set of nothing but skin caps needs no material of its own afterwards."""
    return not texture_set.is_cards and all(is_skin_cap(obj, slot) for obj, slot in texture_set.slots)


def paint_into_skin(
    human: "Human", body_set: "TextureSet", cap_sets: List["TextureSet"]
) -> List[bpy.types.Image]:
    """Mixes the baked caps over the inputs of the skin material.

    The cap sets must be baked, the skin not yet. Adds a UV map per cap set to
    the body, remove them with `remove_uv_layers` after the skin is baked.

    Returns:
        List[bpy.types.Image]: The cap images the skin material now reads.
    """
    body = human.objects.body
    images: List[bpy.types.Image] = []
    for index, cap_set in enumerate(cap_sets):
        slots = [(obj, slot) for obj, slot in cap_set.slots if is_skin_cap(obj, slot)]
        layer = f"{UV_LAYER_PREFIX}{index}"
        if not _project_uvs(body, slots, layer):
            continue
        cap_images = _cap_images(cap_set)
        images.extend(cap_images.values())
        for material in body_set.materials:
            _mix_over_skin(material, layer, cap_images, _constant(cap_set, "metallic"))
    return images


def remove_uv_layers(human: "Human") -> None:
    """Removes the UV maps and the weights the caps were projected into."""
    mesh = human.objects.body.data
    for layer in [layer for layer in mesh.uv_layers if layer.name.startswith(UV_LAYER_PREFIX)]:
        mesh.uv_layers.remove(layer)
    for attribute in [a for a in mesh.attributes if a.name.startswith(UV_LAYER_PREFIX)]:
        mesh.attributes.remove(attribute)


def remove_caps(human: "Human") -> None:
    """Deletes the skin caps: the faces of the cap slot, or the whole object
    when it has no cards. An object that keeps its cards is marked as an
    object of cards only, see haircards.separate_caps."""
    for obj in list(human.objects.haircards):
        if not is_skin_cap(obj, 0):
            continue
        mesh = obj.data
        material_index = np.empty(len(mesh.polygons), dtype=np.int32)
        mesh.polygons.foreach_get("material_index", material_index)
        if len(mesh.materials) > 1 and (material_index == 1).any():
            _keep_slot(mesh, 1)
            obj[CARDS_KEY] = True
        else:
            bpy.data.objects.remove(obj)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)


def _evaluated_coords(obj: bpy.types.Object, context: bpy.types.Context) -> Optional[np.ndarray]:
    """World coordinates of the vertices of an object as it is deformed, None
    when its modifiers change the vertex count."""
    masks = [mod for mod in obj.modifiers if mod.type == "MASK" and mod.show_viewport]
    for mod in masks:
        mod.show_viewport = False
    try:
        depsgraph = context.evaluated_depsgraph_get()
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            if len(mesh.vertices) != len(obj.data.vertices):
                return None
            coords = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
            mesh.vertices.foreach_get("co", coords)
        finally:
            evaluated.to_mesh_clear()
    finally:
        for mod in masks:
            mod.show_viewport = True
    coords = coords.reshape(-1, 3)
    matrix = np.array(obj.matrix_world)
    return coords @ matrix[:3, :3].T + matrix[:3, 3]


def _cap_triangles(
    slots: List[Tuple[bpy.types.Object, int]], context: bpy.types.Context
) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]], List[np.ndarray]]:
    """The triangles of the caps in world space, with the UV of each corner."""
    vertices: List[Tuple[float, float, float]] = []
    triangles: List[Tuple[int, int, int]] = []
    uvs: List[np.ndarray] = []
    for obj, slot in slots:
        mesh = obj.data
        uv_layer = mesh.uv_layers.active
        coords = _evaluated_coords(obj, context)
        if uv_layer is None or coords is None:
            continue
        mesh.calc_loop_triangles()
        loop_uvs = np.empty(len(mesh.loops) * 2, dtype=np.float32)
        uv_layer.data.foreach_get("uv", loop_uvs)
        loop_uvs = loop_uvs.reshape(-1, 2)
        offset = len(vertices)
        vertices.extend(map(tuple, coords))
        for tri in mesh.loop_triangles:
            if tri.material_index != slot:
                continue
            triangles.append(tuple(offset + v for v in tri.vertices))  # type:ignore[arg-type]
            uvs.append(loop_uvs[list(tri.loops)])
    return vertices, triangles, uvs


def _project_uvs(  # noqa: CCR001
    body: bpy.types.Object, slots: List[Tuple[bpy.types.Object, int]], layer: str
) -> bool:
    """Gives every corner of the body near a cap the UV of the nearest point of
    the cap, in a new UV map, and a weight for how much of the cap it shows,
    in a color attribute of the same name with WEIGHT_SUFFIX. False when there
    is nothing to project on.

    A face whose corners land on both sides of a seam of the cap would reach
    from one side of its texture to the other: its corners get the UVs of the
    cap triangle nearest to the middle of the face instead, extended past the
    edges of that triangle.

    The weight of a corner falls from 1 to 0 between FADE_START and FADE_END
    from the cap, see the module docstring; the weight of a corner away from
    the caps is 0.
    """
    context = bpy.context
    vertices, triangles, tri_uvs = _cap_triangles(slots, context)
    if not triangles:
        return False
    tree = BVHTree.FromPolygons(vertices, triangles)
    mesh = body.data
    coords = _evaluated_coords(body, context)
    if coords is None:
        matrix = np.array(body.matrix_world)
        coords = np.empty(len(mesh.vertices) * 3)
        mesh.vertices.foreach_get("co", coords)
        coords = coords.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]

    def uv_on(tri: int, point: object) -> Tuple[float, float]:
        a, b, c = (vertices[i] for i in triangles[tri])
        uv = tri_uvs[tri]
        mapped = barycentric_transform(point, a, b, c, (*uv[0], 0.0), (*uv[1], 0.0), (*uv[2], 0.0))
        return mapped[0], mapped[1]

    near = np.zeros(len(coords), dtype=bool)
    for index, co in enumerate(coords):
        near[index] = tree.find_nearest(co, NEAR_DISTANCE)[0] is not None

    loop_verts = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", loop_verts)
    loop_total = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("loop_total", loop_total)
    loop_start = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("loop_start", loop_start)
    polygon_of_loop = np.repeat(np.arange(len(mesh.polygons)), loop_total)
    near_polygon = np.zeros(len(mesh.polygons), dtype=bool)
    np.logical_or.at(near_polygon, polygon_of_loop, near[loop_verts])

    uvs = np.empty((len(mesh.loops), 2), dtype=np.float32)
    uvs[:] = OUTSIDE_UV
    weights = np.zeros(len(mesh.loops), dtype=np.float32)
    vert_uv: Dict[int, Optional[Tuple[float, float]]] = {}
    vert_weight: Dict[int, float] = {}
    for polygon in np.flatnonzero(near_polygon):
        start, total = int(loop_start[polygon]), int(loop_total[polygon])
        verts = loop_verts[start : start + total]
        corner_uvs = []
        for vert in verts:
            vert = int(vert)
            if vert not in vert_uv:
                location, _, tri, distance = tree.find_nearest(coords[vert], REACH_DISTANCE)
                vert_uv[vert] = None if location is None else uv_on(tri, location)
                vert_weight[vert] = 0.0 if location is None else _weight(distance)
            corner_uvs.append(vert_uv[vert])
        if any(uv is None for uv in corner_uvs):
            continue
        span = np.ptp(np.array(corner_uvs), axis=0).max()
        if span > SEAM_SPAN:
            location, _, tri, _ = tree.find_nearest(coords[verts].mean(axis=0), REACH_DISTANCE)
            if location is None:
                continue
            corner_uvs = [uv_on(tri, coords[vert]) for vert in verts]
        uvs[start : start + total] = corner_uvs
        weights[start : start + total] = [vert_weight[int(vert)] for vert in verts]

    active = mesh.uv_layers.active_index
    uv_layer = mesh.uv_layers.new(name=layer, do_init=False)
    uv_layer.data.foreach_set("uv", uvs.ravel())
    mesh.uv_layers.active_index = active
    attribute = mesh.color_attributes.new(name=layer + WEIGHT_SUFFIX, type="FLOAT_COLOR", domain="CORNER")
    colors = np.ones((len(mesh.loops), 4), dtype=np.float32)
    colors[:, :3] = weights[:, None]
    attribute.data.foreach_set("color", colors.ravel())
    return True


def _weight(distance: float) -> float:
    """How much of the cap a corner at a distance from it shows, 1 to 0."""
    return float(1.0 - min(max((distance - FADE_START) / (FADE_END - FADE_START), 0.0), 1.0))


def _constant(texture_set: "TextureSet", pass_id: str) -> Optional[float]:
    value = texture_set.baked.get(pass_id)
    return None if value is None or isinstance(value, bpy.types.Image) else float(value)  # type:ignore[arg-type]


def _cap_images(texture_set: "TextureSet") -> Dict[str, bpy.types.Image]:
    """The baked passes of a cap set as images the skin material can read: the
    color with the alpha in it, the normal and the roughness."""
    from .textures import _alpha_channel, _channel, _fill_uncovered, _new_image, _normal_pixels, _pixels

    size = texture_set.resolution
    baked = texture_set.baked
    images: Dict[str, bpy.types.Image] = {}
    base = baked.get("base_color")
    if isinstance(base, bpy.types.Image):
        pixels = _pixels(base)
    else:
        pixels = np.ones((size * size, 4), dtype=np.float32)
        pixels[:, :3] = float(base or 0.0)  # type:ignore[arg-type]
    if "alpha" in baked:
        pixels[:, 3] = _alpha_channel(texture_set, size)
    else:
        pixels[:, 3] = 1.0
    # The gaps between the strands are black, which bilinear filtering would
    # mix into the skin at every strand edge
    _fill_uncovered(pixels, size)
    images["color"] = _new_image(f"hg_capskin_{texture_set.part}_color", size, pixels, True, True)
    alpha = pixels[:, 3].copy()

    def filled(values: np.ndarray) -> np.ndarray:
        """The texels without hair get the values of the nearest hair: outside
        the islands of the cap they are empty, a roughness of 0 and no normal,
        which filtering mixed into the skin along every seam of the cap."""
        out = np.ones((size * size, 4), dtype=np.float32)
        out[:, :3] = values
        out[:, 3] = alpha
        _fill_uncovered(out, size)
        out[:, 3] = 1.0
        return out

    if isinstance(baked.get("normal"), bpy.types.Image):
        images["normal"] = _new_image(
            f"hg_capskin_{texture_set.part}_normal",
            size,
            filled(_normal_pixels(texture_set, size)[:, :3]),
            False,
            False,
        )
    roughness = baked.get("roughness")
    if roughness is not None:
        images["roughness"] = _new_image(
            f"hg_capskin_{texture_set.part}_roughness",
            size,
            filled(_channel(roughness, size)[:, None]),
            False,
            False,
        )
    return images


def _socket(sockets: bpy.types.bpy_prop_collection, identifier: str) -> bpy.types.NodeSocket:
    return next(socket for socket in sockets if socket.identifier == identifier)


def _mix_over_skin(
    material: bpy.types.Material,
    layer: str,
    images: Dict[str, bpy.types.Image],
    metallic: Optional[float],
) -> None:
    """Mixes the cap images over the Principled inputs of the skin material."""
    from .textures import _principled

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    principled = _principled(material)
    uv_node = nodes.new("ShaderNodeUVMap")
    uv_node.uv_map = layer

    def texture(image: bpy.types.Image) -> bpy.types.ShaderNode:
        node = nodes.new("ShaderNodeTexImage")
        node.image = image
        # The caps are wrapped around the head, their UVs run over the edges
        node.extension = "REPEAT"
        links.new(uv_node.outputs["UV"], node.inputs["Vector"])
        return node

    color = texture(images["color"])
    # The weight of the corners away from the caps and past their borders is
    # 0, see _project_uvs; it is stored in every channel of the color
    weight = nodes.new("ShaderNodeVertexColor")
    weight.layer_name = layer + WEIGHT_SUFFIX
    masked = nodes.new("ShaderNodeMath")
    masked.operation = "MULTIPLY"
    links.new(color.outputs["Alpha"], masked.inputs[0])
    links.new(weight.outputs["Color"], masked.inputs[1])
    alpha = masked.outputs[0]

    def mix(input_name: str, data_type: str, cap_socket: Optional[bpy.types.NodeSocket], cap_value: object = None) -> None:
        target = principled.inputs[input_name]
        kind = {"RGBA": "Color", "FLOAT": "Float", "VECTOR": "Vector"}[data_type]
        node = nodes.new("ShaderNodeMix")
        node.data_type = data_type
        links.new(alpha, _socket(node.inputs, "Factor_Float"))
        a = _socket(node.inputs, f"A_{kind}")
        b = _socket(node.inputs, f"B_{kind}")
        if target.links:
            links.new(target.links[0].from_socket, a)
        elif data_type == "VECTOR":
            links.new(nodes.new("ShaderNodeNewGeometry").outputs["Normal"], a)
        else:
            a.default_value = target.default_value
        if cap_socket is not None:
            links.new(cap_socket, b)
        else:
            b.default_value = cap_value
        result = _socket(node.outputs, f"Result_{kind}")
        if data_type == "VECTOR":
            normalize = nodes.new("ShaderNodeVectorMath")
            normalize.operation = "NORMALIZE"
            links.new(result, normalize.inputs[0])
            result = normalize.outputs["Vector"]
        links.new(result, target)

    mix("Base Color", "RGBA", color.outputs["Color"])
    if "roughness" in images:
        mix("Roughness", "FLOAT", texture(images["roughness"]).outputs["Color"])
    mix("Metallic", "FLOAT", None, metallic or 0.0)
    if "normal" in images:
        normal_map = nodes.new("ShaderNodeNormalMap")
        normal_map.space = "TANGENT"
        normal_map.uv_map = layer
        links.new(texture(images["normal"]).outputs["Color"], normal_map.inputs["Color"])
        mix("Normal", "VECTOR", normal_map.outputs["Normal"])
