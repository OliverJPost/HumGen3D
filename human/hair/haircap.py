# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements creating haircaps, meshes that lie on the skin with a texture of hair.

A haircap shows the hair that is too short for haircards, and hides the skin between
the haircards.
"""

import os
from typing import TYPE_CHECKING, Literal, Optional

import bmesh
import bpy
import numpy as np
from HumGen3D import get_prefs
from HumGen3D.common.math import create_kdtree
from HumGen3D.human.hair import hair_binding
from HumGen3D.human.hair.haircards import (
    STATIONS,
    BodyReference,
    HairStrands,
    reuse_images,
)
from mathutils.bvhtree import BVHTree

if TYPE_CHECKING:
    from ..human import Human

HaircapType = Literal["Scalp", "Eyelashes", "Brows", "Beard"]

# The hair of these haircaps is drawn from the hairs of the particle systems, instead
# of masking out a painted texture. The painted texture has one beard shape with
# long hairs, which doesn't fit most face hair styles.
DRAWN_HAIRCAP_TYPES = ("Beard",)
TEXTURE_SIZE = 1024
# The hairs are drawn on a texture that is this many times bigger and then scaled
# down, to get smooth lines
SUPERSAMPLING = 2
# Number of points of every hair that are drawn
TEXTURE_STATIONS = 5
# How opaque a single hair is. Hairs on top of each other get more opaque.
STROKE_OPACITY = 2.2
# How much more transparent the tip of a hair is than its root
TIP_FADE = 0.6
UV_MARGIN = 0.01
DRAWN_BUMP_STRENGTH = 0.1
# Lines that are this many times longer on the texture than expected from the length
# of the hair, cross a seam of the UV map
MAX_STROKE_STRETCH = 4


def _smoothstep(edge0: float, edge1: float, values: np.ndarray) -> np.ndarray:
    x = np.clip((values - edge0) / (edge1 - edge0), 0, 1)
    return x * x * (3 - 2 * x)


def _loop_verts(mesh: bpy.types.Mesh) -> np.ndarray:
    loop_verts = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", loop_verts)
    return loop_verts


def _polygon_starts(mesh: bpy.types.Mesh) -> np.ndarray:
    loop_starts = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("loop_start", loop_starts)
    return loop_starts


def _polygon_sizes(mesh: bpy.types.Mesh) -> np.ndarray:
    loop_totals = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("loop_total", loop_totals)
    return loop_totals


def _polygons_with_verts(mesh: bpy.types.Mesh, vert_mask: np.ndarray) -> np.ndarray:
    """Gets a mask of the polygons that use at least one of the masked vertices."""
    loop_mask = vert_mask[_loop_verts(mesh)]
    return np.logical_or.reduceat(loop_mask, _polygon_starts(mesh))


def _delete_polygons(mesh: bpy.types.Mesh, keep: np.ndarray) -> None:
    """Removes the polygons that are not in the mask, and the vertices they used."""
    if keep.all() or not keep.any():
        return

    bm = bmesh.new()  # type:ignore[call-arg]
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    unused_faces = [face for face in bm.faces if not keep[face.index]]
    bmesh.ops.delete(bm, geom=unused_faces, context="FACES")
    bm.to_mesh(mesh)
    bm.free()


def _boundary_verts(mesh: bpy.types.Mesh) -> np.ndarray:
    """Gets the indices of the vertices on the open edges of the mesh."""
    loop_edges = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("edge_index", loop_edges)
    face_counts = np.bincount(loop_edges, minlength=len(mesh.edges))
    edge_verts = np.empty(len(mesh.edges) * 2, dtype=np.int32)
    mesh.edges.foreach_get("vertices", edge_verts)
    return np.unique(edge_verts.reshape((-1, 2))[face_counts == 1])


def _islands(mesh: bpy.types.Mesh) -> np.ndarray:
    """Gets a label for every vertex, the same for vertices that are connected."""
    edges = np.empty(len(mesh.edges) * 2, dtype=np.int32)
    mesh.edges.foreach_get("vertices", edges)
    edges = edges.reshape((-1, 2))

    labels = np.arange(len(mesh.vertices))
    while True:
        new_labels = labels.copy()
        np.minimum.at(new_labels, edges[:, 0], labels[edges[:, 1]])
        np.minimum.at(new_labels, edges[:, 1], labels[edges[:, 0]])
        if np.array_equal(new_labels, labels):
            return labels
        labels = new_labels


def _set_density(mesh: bpy.types.Mesh, density: np.ndarray) -> None:
    colors = np.ones((len(density), 4), dtype=np.float32)
    colors[:, :3] = density[:, None]
    mesh.color_attributes[0].data.foreach_set("color", colors.ravel())


def _mask_painted_hair(
    human: "Human",
    mesh: bpy.types.Mesh,
    body_vert_idxs: np.ndarray,
    coords_world: np.ndarray,
    density_vertex_groups: list[tuple[bpy.types.VertexGroup, float]],
    density_points: np.ndarray,
) -> None:
    """Shows the painted hair texture only where the human has hair.

    That is where the density vertex groups of the hair systems have weight, and
    where hairs of systems without such a vertex group are close to the skin. Not
    only at the roots of those hairs: the hair of for example a ponytail only grows
    from the hairline, but covers the whole scalp.

    Polygons without hair are removed from the haircap.
    """
    body_obj = human.objects.body
    factors = {vg.index: factor for vg, factor in density_vertex_groups}
    body_density = np.zeros(len(body_obj.data.vertices), dtype=np.float32)
    for vert in body_obj.data.vertices:
        for group in vert.groups:
            if group.group in factors:
                body_density[vert.index] += group.weight * factors[group.group]
    density = np.clip(np.round(body_density[body_vert_idxs], 4), 0, 1)

    if len(density_points):
        kd_hair = create_kdtree(density_points)
        hair_distance = np.array([kd_hair.find(co)[2] for co in coords_world])
        density = np.maximum(density, 1 - _smoothstep(0.012, 0.025, hair_distance))

    if density.max() < 0.001:
        density[:] = 1
    # Fade out the hair towards the border of the haircap
    density[_boundary_verts(mesh)] = 0

    _set_density(mesh, density)
    _delete_polygons(mesh, _polygons_with_verts(mesh, density > 0))


def _project_on_mesh(
    mesh: bpy.types.Mesh, coords_world: np.ndarray, points: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Finds the nearest place on the surface of a mesh for all points.

    Returns:
        tuple[np.ndarray, np.ndarray]: (n, 2) UV coordinates and (n,) indices of the
            polygons of the nearest places.
    """
    mesh.calc_loop_triangles()
    triangle_count = len(mesh.loop_triangles)
    triangle_verts = np.empty(triangle_count * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get("vertices", triangle_verts)
    triangle_verts = triangle_verts.reshape((-1, 3))
    triangle_loops = np.empty(triangle_count * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get("loops", triangle_loops)
    triangle_loops = triangle_loops.reshape((-1, 3))
    triangle_polygons = np.empty(triangle_count, dtype=np.int32)
    mesh.loop_triangles.foreach_get("polygon_index", triangle_polygons)
    uvs = np.empty(len(mesh.loops) * 2, dtype=np.float64)
    mesh.uv_layers.active.data.foreach_get("uv", uvs)
    uvs = uvs.reshape((-1, 2))

    bvh = BVHTree.FromPolygons(coords_world.tolist(), triangle_verts.tolist())
    nearest = np.empty((len(points), 3))
    triangles = np.empty(len(points), dtype=np.int64)
    for i, point in enumerate(points):
        nearest[i], _, triangles[i], _ = bvh.find_nearest(point)

    # Barycentric coordinates of the nearest places on their triangles
    corner_a, corner_b, corner_c = (
        coords_world[triangle_verts[triangles, corner]] for corner in range(3)
    )
    edge_b, edge_c = corner_b - corner_a, corner_c - corner_a
    relative = nearest - corner_a
    dot_bb = np.einsum("ni,ni->n", edge_b, edge_b)
    dot_bc = np.einsum("ni,ni->n", edge_b, edge_c)
    dot_cc = np.einsum("ni,ni->n", edge_c, edge_c)
    dot_rb = np.einsum("ni,ni->n", relative, edge_b)
    dot_rc = np.einsum("ni,ni->n", relative, edge_c)
    denominator = np.maximum(dot_bb * dot_cc - dot_bc * dot_bc, 1e-20)
    weight_b = (dot_cc * dot_rb - dot_bc * dot_rc) / denominator
    weight_c = (dot_bb * dot_rc - dot_bc * dot_rb) / denominator
    weight_a = 1 - weight_b - weight_c

    point_uvs = (
        uvs[triangle_loops[triangles, 0]] * weight_a[:, None]
        + uvs[triangle_loops[triangles, 1]] * weight_b[:, None]
        + uvs[triangle_loops[triangles, 2]] * weight_c[:, None]
    )
    return point_uvs, triangle_polygons[triangles]


def _fill_uv_space(mesh: bpy.types.Mesh) -> None:
    """Scales the UV map of the mesh to use the whole texture."""
    uv_data = mesh.uv_layers.active.data
    uvs = np.empty(len(mesh.loops) * 2, dtype=np.float64)
    uv_data.foreach_get("uv", uvs)
    uvs = uvs.reshape((-1, 2))

    size = np.maximum(uvs.max(axis=0) - uvs.min(axis=0), 1e-9)
    uvs = (uvs - uvs.min(axis=0)) / size * (1 - 2 * UV_MARGIN) + UV_MARGIN
    uv_data.foreach_set("uv", uvs.ravel())


def _draw_strands(
    uvs: np.ndarray, points: np.ndarray, weights: np.ndarray
) -> np.ndarray:
    """Draws hairs as lines on a texture.

    Args:
        uvs (np.ndarray): (n, TEXTURE_STATIONS, 2) UV coordinates of the hairs.
        points (np.ndarray): (n, TEXTURE_STATIONS, 3) coordinates of the hairs.
        weights (np.ndarray): (n,) number of hairs every line stands for.

    Returns:
        np.ndarray: (TEXTURE_SIZE, TEXTURE_SIZE) share of every pixel that is covered
            by hair, with the row for v = 0 first.
    """
    size = TEXTURE_SIZE * SUPERSAMPLING
    segment_count = uvs.shape[1] - 1
    starts = uvs[:, :-1].reshape((-1, 2)) * size
    ends = uvs[:, 1:].reshape((-1, 2)) * size
    fade = 1 - TIP_FADE * (np.arange(segment_count) + 0.5) / segment_count
    opacity = np.repeat(weights, segment_count) * np.tile(fade, len(uvs))

    lengths = np.linalg.norm(ends - starts, axis=1)
    real_lengths = np.linalg.norm(np.diff(points, axis=1), axis=2).ravel()
    # Hairs that point away from the skin are shorter on the texture, never longer
    pixels_per_meter = np.median(lengths / np.maximum(real_lengths, 1e-9))
    drawable = lengths < real_lengths * pixels_per_meter * MAX_STROKE_STRETCH + 2
    starts, ends, lengths = starts[drawable], ends[drawable], lengths[drawable]
    opacity = opacity[drawable] * STROKE_OPACITY
    if not len(lengths):
        return np.zeros((TEXTURE_SIZE, TEXTURE_SIZE), dtype=np.float32)

    # Enough points on every line to not skip pixels on almost all lines
    step_count = int(np.clip(np.ceil(np.quantile(lengths, 0.99)) + 1, 2, 64))
    factors = np.linspace(0, 1, step_count)[None, :, None]
    points = starts[:, None] * (1 - factors) + ends[:, None] * factors
    pixels = np.clip(points.astype(np.int64), 0, size - 1).reshape((-1, 2))
    # Hairs that point away from the skin are shorter than a pixel, they are drawn
    # as a dot
    per_point = opacity * np.maximum(lengths, 1) / step_count

    drawn = np.zeros((size, size), dtype=np.float32)
    np.add.at(drawn, (pixels[:, 1], pixels[:, 0]), np.repeat(per_point, step_count))
    drawn = drawn.reshape(
        (TEXTURE_SIZE, SUPERSAMPLING, TEXTURE_SIZE, SUPERSAMPLING)
    ).mean(axis=(1, 3))

    return 1 - np.exp(-drawn)


def _set_haircap_image(material: bpy.types.Material, image: bpy.types.Image) -> None:
    """Replaces the painted hair texture of a haircap material."""
    group_node = next(
        node for node in material.node_tree.nodes if node.bl_idname == "ShaderNodeGroup"
    )
    if group_node.node_tree.users > 1:
        group_node.node_tree = group_node.node_tree.copy()
    image_node = next(
        node
        for node in group_node.node_tree.nodes
        if node.bl_idname == "ShaderNodeTexImage"
    )
    image_node.image = image
    # The drawn hairs are much thinner than the painted ones, with the bump strength
    # for the painted hairs they reflect light in all directions and look grey
    for node in group_node.node_tree.nodes:
        if node.bl_idname == "ShaderNodeBump":
            node.inputs["Strength"].default_value = DRAWN_BUMP_STRENGTH


def _draw_hair_texture(
    human: "Human",
    haircap_obj: bpy.types.Object,
    haircap_type: HaircapType,
    strands: HairStrands,
) -> None:
    """Gives the haircap a texture with the hairs of the human drawn on it.

    Polygons without hair are removed from the haircap, and the UV map is scaled to
    use the whole texture for the polygons that are left.
    """
    mesh = haircap_obj.data
    mx_world = human.objects.rig.matrix_world
    stations = np.linspace(0, STATIONS - 1, TEXTURE_STATIONS).astype(int)
    points = strands.points[:, stations].reshape((-1, 3))

    coords_world = hair_binding.transform_coords(
        mx_world, hair_binding.get_coords(mesh.vertices)
    )
    _, polygons = _project_on_mesh(mesh, coords_world, points)
    has_hair = np.zeros(len(mesh.polygons), dtype=bool)
    has_hair[polygons] = True
    # Also keep the neighbours of the polygons with hair, for the hairs that are
    # drawn close to the edge of a polygon
    vert_has_hair = np.zeros(len(mesh.vertices), dtype=bool)
    vert_has_hair[_loop_verts(mesh)[np.repeat(has_hair, _polygon_sizes(mesh))]] = True
    _delete_polygons(mesh, _polygons_with_verts(mesh, vert_has_hair))
    _fill_uv_space(mesh)

    coords_world = hair_binding.transform_coords(
        mx_world, hair_binding.get_coords(mesh.vertices)
    )
    uvs, _ = _project_on_mesh(mesh, coords_world, points)
    coverage = _draw_strands(
        uvs.reshape((-1, TEXTURE_STATIONS, 2)),
        points.reshape((-1, TEXTURE_STATIONS, 3)),
        strands.weights,
    )

    image = bpy.data.images.new(
        f"{human.name}_haircap_{haircap_type.lower()}",
        TEXTURE_SIZE,
        TEXTURE_SIZE,
        alpha=False,
    )
    image.colorspace_settings.name = "Non-Color"
    # Black hairs on a white background, like the painted texture
    pixels = np.ones((TEXTURE_SIZE, TEXTURE_SIZE, 4), dtype=np.float32)
    pixels[:, :, :3] = (1 - coverage)[:, :, None]
    image.pixels.foreach_set(pixels.ravel())
    # The image only exists in this file, so it has to be saved in it
    image.pack()

    _set_haircap_image(mesh.materials[0], image)
    _set_density(mesh, np.ones(len(mesh.vertices), dtype=np.float32))


def _attach_islands(
    mesh: bpy.types.Mesh, coords_world: np.ndarray, body: BodyReference
) -> None:
    """Attaches every separate part of the mesh as a whole to the body.

    Used for eyelashes, which should not be deformed by the eyelid they are on. The
    part is attached to the body vertex nearest to its vertex closest to the body.
    """
    labels = _islands(mesh)
    distances = body.distances(coords_world)
    body_vert_idxs = np.empty(len(labels), dtype=np.int64)
    for label in np.unique(labels):
        island = np.flatnonzero(labels == label)
        root = island[np.argmin(distances[island])]
        body_vert_idxs[island] = body.kd.find(coords_world[root])[1]

    hair_binding.set_attachment(mesh, body_vert_idxs)


def create_haircap(
    human: "Human",
    body: BodyReference,
    haircap_type: HaircapType,
    density_vertex_groups: list[tuple[bpy.types.VertexGroup, float]],
    strands: Optional[HairStrands],
    context: bpy.types.Context,
) -> bpy.types.Object:
    """Creates a haircap object, fitted, skinned and attached to the body.

    The hair is only visible where the human has hair. For face hair the hairs of
    the particle systems are drawn on a texture. For the scalp a painted texture is
    used, masked by the density vertex groups of the hair systems and the hairs of
    systems without such a vertex group.

    Args:
        human (Human): The human to add the haircap to.
        body (BodyReference): Body data of the human.
        haircap_type (HaircapType): Part of the body to add the haircap to.
        density_vertex_groups (list[tuple[bpy.types.VertexGroup, float]]): The density
            vertex groups of the hair systems, with the weight they count with.
        strands (Optional[HairStrands]): Hairs of the particle systems. Not needed
            for eyelashes and eyebrows.
        context (bpy.types.Context): Blender context.

    Returns:
        bpy.types.Object: The haircap object, in the space of the rig.
    """
    body_obj = human.objects.body
    mx_world = human.objects.rig.matrix_world
    blendfile = os.path.join(get_prefs().filepath, "hair", "haircards", "haircap.blend")
    with reuse_images():
        with bpy.data.libraries.load(blendfile, link=False) as (_, data_to):
            data_to.objects = [f"HG_Haircap_{haircap_type}"]

    haircap_obj = data_to.objects[0]
    context.scene.collection.objects.link(haircap_obj)
    mesh = haircap_obj.data

    # The haircap was modelled on the base shape of the body, move every vertex
    # along with the nearest vertex of the body
    cap_coords = hair_binding.get_coords(mesh.vertices)
    kd_base = create_kdtree(body.base_coords_local)
    body_vert_idxs = np.array([kd_base.find(co)[1] for co in cap_coords])
    fitted = (
        body.coords_local[body_vert_idxs]
        + cap_coords
        - body.base_coords_local[body_vert_idxs]
    )
    coords_world = hair_binding.transform_coords(body_obj.matrix_world, fitted)
    coords_rig = hair_binding.transform_coords(mx_world.inverted(), coords_world)
    mesh.vertices.foreach_set("co", coords_rig.ravel())
    hair_binding.set_attachment(mesh, body_vert_idxs)

    has_strands = strands is not None and len(strands.points)
    if haircap_type in DRAWN_HAIRCAP_TYPES and has_strands:
        _draw_hair_texture(human, haircap_obj, haircap_type, strands)
    elif haircap_type in ("Scalp", "Beard"):
        density_points = strands.density_points if strands else np.zeros((0, 3))
        _mask_painted_hair(
            human,
            mesh,
            body_vert_idxs,
            coords_world,
            density_vertex_groups,
            density_points,
        )
    mesh.update()

    # Polygons can have been removed
    coords_world = hair_binding.transform_coords(
        mx_world, hair_binding.get_coords(mesh.vertices)
    )
    if haircap_type == "Eyelashes":
        _attach_islands(mesh, coords_world, body)
    body.add_skin(haircap_obj, coords_world, scalp_only=haircap_type == "Scalp")

    return haircap_obj
