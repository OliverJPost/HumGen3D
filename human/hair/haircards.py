# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements generating game engine ready haircards from particle hair systems.

The particle hairs are grouped into clumps of hairs that follow a similar path. Every
clump becomes one card, which follows the average hair of the clump and is as wide as
the clump. The number of clumps and the number of segments of each card are chosen to
fit a triangle budget, so the result has a predictable size for every hairstyle.

Extracting the strands (extract_strands) is separated from building the cards
(build_card_geometry), so cards for multiple budgets can be built from the same
strands.
"""

import contextlib
import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable, Iterator, Literal, Optional

import bpy
import numpy as np
from HumGen3D import get_prefs
from HumGen3D.common.context import context_override
from HumGen3D.common.geometry import world_coords_from_obj
from HumGen3D.common.math import create_kdtree
from HumGen3D.common.memory_management import hg_delete
from HumGen3D.human.hair.compatibility import (
    get_children_percent,
    set_children_percent,
)
from mathutils import Matrix

if TYPE_CHECKING:
    from ..human import Human

HaircapType = Literal["Scalp", "Eyelashes", "Brows", "Beard"]
Rect = tuple[tuple[float, float], tuple[float, float]]
# Names of the vertex groups, their weights per usable vertex and a kdtree of those
SkinData = tuple[list[str], np.ndarray, Any]

# Triangle budgets of the whole scalp hair object, so cards plus haircap
QUALITY_TRIANGLE_BUDGETS = {
    "ultra": 24000,
    "high": 12000,
    "medium": 7000,
    "low": 4500,
}

# Name of the color attribute. On the haircap it contains the hair density, on the
# cards R is the position along the card (0 at the root, 1 at the tip), G is a random
# value per card and B is the layer of the card (0 for the innermost card, 1 for the
# outermost card).
COLOR_ATTRIBUTE = "Color"
UV_NAME = "UVMap"

# Bones the scalp hair is skinned to. Hair that is skinned to the arms would be pulled
# along when the arms are raised.
SCALP_BONES = ("head", "neck", "spine.003", "spine.002", "spine.001", "spine")
MAX_BONE_INFLUENCES = 4

# Number of points every strand is resampled to. Has to be a power of two plus one.
STATIONS = 33
MAX_STRANDS_PER_SYSTEM = 6000
# Particle systems with hairs shorter than this are only represented by the haircap
SHORT_SYSTEM_LENGTH = 0.02
MIN_STRAND_LENGTH = 0.01
# Hairs shorter than this don't count as hair growing on that part of the scalp
MIN_ROOT_LENGTH = 0.002
MIN_STRANDS_PER_CLUMP = 4

MAX_SEGMENT_LENGTH = 0.08
# Segments are added until the cards deviate less than this from the clumps
WANTED_TOLERANCE = 0.002
MIN_TOLERANCE = 0.0004

MIN_HALF_WIDTH = 0.004
MAX_HALF_WIDTH = 0.04
WIDTH_PADDING = 0.003
# Maximum of half the width of a card, relative to its length
MAX_WIDTH_TO_LENGTH = 0.25
# Number of standard deviations of the clump the card extends to each side
SPREAD_FACTOR = 1.6
# Number of standard deviations of the tips of the clump the card is extended with
TIP_SPREAD_FACTOR = 1.0
# Extra weight of the distance to the head when comparing strands, to get clumps that
# are layers on top of each other instead of thick bundles
LAYER_WEIGHT = 1.5

# Part of the hair texture without gaps between the hairs, not in the zones json
SOLID_ZONE: Rect = ((0.0, 0.3), (0.2, 1.0))
LONG_CARD_LENGTH = 0.06
SOLID_CARD_LENGTH = 0.15
# Hairs per cm of card width below which the sparse parts of the texture are used
SPARSE_DENSITY = 12
# Share of the innermost wide cards that get the solid part of the texture
SOLID_SHARE = 0.35


@dataclass
class HairStrands:
    """Hairs of one or more particle systems, resampled to the same point count."""

    #: (n, STATIONS, 3) world space coordinates in the rest pose, root first
    points: np.ndarray
    #: (n,) index of the particle system the strand comes from
    system: np.ndarray
    #: (n,) number of rendered hairs every strand stands for
    weights: np.ndarray
    #: (m, 3) roots of all hairs of systems without a density vertex group, also of
    #: the hairs that are too short to get a card
    density_roots: np.ndarray


@dataclass
class CardGeometry:
    """Mesh data of a set of haircards, ordered from the inner to the outer cards."""

    #: (v, 3) world space coordinates in the rest pose
    vertices: np.ndarray
    #: (f, 4) vertex indices of the quads
    faces: np.ndarray
    #: (v, 2)
    uvs: np.ndarray
    #: (v, 4) see COLOR_ATTRIBUTE
    colors: np.ndarray
    #: (v, 3) normals of the head shape instead of the flat cards
    normals: np.ndarray
    #: (v, 3) point on the middle of the card, to look up the skin weights with
    skin_points: np.ndarray
    card_count: int

    @property
    def triangle_count(self) -> int:
        return len(self.faces) * 2


def _normalized(vectors: np.ndarray) -> np.ndarray:
    length = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.maximum(length, 1e-9)


def _project_perpendicular(vectors: np.ndarray, tangents: np.ndarray) -> np.ndarray:
    """Removes the part of the vectors that is parallel to the unit tangents."""
    parallel = np.einsum("...i,...i->...", vectors, tangents)[..., None]
    return vectors - parallel * tangents


def _smoothstep(edge0: float, edge1: float, values: np.ndarray) -> np.ndarray:
    x = np.clip((values - edge0) / (edge1 - edge0), 0, 1)
    return x * x * (3 - 2 * x)


def _bone_by_original_name(
    rig: bpy.types.Object, original_name: str
) -> Optional[bpy.types.Bone]:
    for pose_bone in rig.pose.bones:
        # Rigify humans store the name on the deformation bones under another key
        name = pose_bone.get("original_name") or pose_bone.get("hg_original_name")
        if name == original_name:
            return pose_bone.bone
    return None


@contextlib.contextmanager
def rest_pose(rig: bpy.types.Object, context: bpy.types.Context) -> Iterator[None]:
    """Temporarily puts the armature in its rest position.

    Haircards are skinned to the rig, so they have to be created on the unposed human.

    Args:
        rig (bpy.types.Object): Armature object of the human.
        context (bpy.types.Context): Blender context.

    Yields:
        None
    """
    old_position = rig.data.pose_position
    rig.data.pose_position = "REST"
    context.view_layer.update()
    try:
        yield
    finally:
        rig.data.pose_position = old_position
        context.view_layer.update()


class HeadProxy:
    """Line from the center of the head down the spine, as stand-in for the head.

    The direction from this line to a point is used as the outward direction of the
    hair at that point. Unlike the normals of the body mesh, this direction changes
    smoothly over the whole hairstyle.
    """

    def __init__(self, axis_points: np.ndarray) -> None:
        """Create a new proxy.

        Args:
            axis_points (np.ndarray): World space points of the line, from the center
                of the head downwards.
        """
        axis_points = np.asarray(axis_points, dtype=np.float64)
        # Hair below the last point should still point sideways, not downwards
        downwards = _normalized(axis_points[-1] - axis_points[-2])
        self.axis = np.concatenate((axis_points, [axis_points[-1] + downwards]))

    @classmethod
    def from_human(cls, human: "Human") -> "HeadProxy":
        """Create a proxy from the head, neck and chest bones of the human.

        Args:
            human (Human): Human to create the proxy for.

        Returns:
            HeadProxy: Proxy for the head of this human in the rest pose.
        """
        rig = human.objects.rig
        mx_world = rig.matrix_world
        head_bone = _bone_by_original_name(rig, "head")
        if not head_bone:
            # Unknown rig, estimate the head from the top of the body
            body_coords = world_coords_from_obj(human.objects.body)
            top = body_coords[np.argmax(body_coords[:, 2])]
            center = top - np.array((0, 0, 0.11))
            return cls(np.array((center, center - np.array((0, 0, 0.3)))))

        skull_base = np.array(mx_world @ head_bone.head_local)
        skull_top = np.array(mx_world @ head_bone.tail_local)
        points = [skull_base + (skull_top - skull_base) * 0.55]
        for name in ("neck", "spine.003"):
            bone = _bone_by_original_name(rig, name)
            if bone:
                points.append(np.array(mx_world @ bone.head_local))
        if len(points) == 1:
            points.append(skull_base)

        return cls(np.array(points))

    def outward(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Get the direction away from the head and the distance to the proxy.

        Args:
            points (np.ndarray): (n, 3) world space coordinates.

        Returns:
            tuple[np.ndarray, np.ndarray]: (n, 3) unit vectors pointing away from the
                proxy and the (n,) distances to the proxy.
        """
        best_distance = np.full(len(points), np.inf)
        best_direction = np.zeros((len(points), 3))
        for start, end in zip(self.axis[:-1], self.axis[1:]):
            segment = end - start
            factor = (points - start) @ segment / max(segment @ segment, 1e-12)
            closest = start + np.clip(factor, 0, 1)[:, None] * segment
            direction = points - closest
            distance = np.linalg.norm(direction, axis=1)
            closer = distance < best_distance
            best_distance[closer] = distance[closer]
            best_direction[closer] = direction[closer]

        return _normalized(best_direction), best_distance


class BodyReference:
    """Rest pose shape and skin weights of the body, to fit hair objects to."""

    def __init__(self, human: "Human") -> None:
        """Gather the data of the body of this human.

        Args:
            human (Human): Human to get the body data of.
        """
        self._human = human
        body = human.objects.body
        self.base_coords_local = world_coords_from_obj(body, local=True)
        self.coords_local = world_coords_from_obj(
            body, data=human.keys.all_deformation_shapekeys, local=True
        )
        self.coords_world = world_coords_from_obj(
            body, data=human.keys.all_deformation_shapekeys, local=False
        )
        self.kd = create_kdtree(self.coords_world)
        self._skin_cache: dict[bool, SkinData] = {}

    def distances(self, points: np.ndarray) -> np.ndarray:
        """Get the distance to the nearest body vertex for all points.

        Args:
            points (np.ndarray): (n, 3) world space coordinates.

        Returns:
            np.ndarray: (n,) distances.
        """
        return np.array([self.kd.find(point)[2] for point in points])

    def _skin_data(self, scalp_only: bool) -> SkinData:
        if scalp_only in self._skin_cache:
            return self._skin_cache[scalp_only]

        body = self._human.objects.body
        rig = self._human.objects.rig
        deform_bones = {bone.name for bone in rig.data.bones if bone.use_deform}
        allowed_bones = deform_bones
        if scalp_only:
            scalp_bones = {
                bone.name
                for bone in (_bone_by_original_name(rig, n) for n in SCALP_BONES)
                if bone
            }
            # Unknown rig, better to follow all bones than to follow none
            allowed_bones = (scalp_bones & deform_bones) or deform_bones

        vertex_groups = [vg for vg in body.vertex_groups if vg.name in allowed_bones]
        columns = {vg.index: i for i, vg in enumerate(vertex_groups)}
        deform_idxs = {vg.index for vg in body.vertex_groups if vg.name in deform_bones}

        vert_count = len(body.data.vertices)
        weights = np.zeros((vert_count, len(vertex_groups)), dtype=np.float32)
        totals = np.zeros(vert_count, dtype=np.float32)
        for vert in body.data.vertices:
            for group in vert.groups:
                if group.group in deform_idxs:
                    totals[vert.index] += group.weight
                column = columns.get(group.group)
                if column is not None:
                    weights[vert.index, column] = group.weight

        # Only use vertices that mainly follow the allowed bones, so hair on the
        # shoulders gets the weights of the chest instead of weights of the arms
        allowed_totals = weights.sum(axis=1)
        usable = np.flatnonzero((allowed_totals > 0.5 * totals) & (allowed_totals > 0))
        weights = weights[usable] / allowed_totals[usable, None]
        kd = create_kdtree(self.coords_world[usable])

        data = ([vg.name for vg in vertex_groups], weights, kd)
        self._skin_cache[scalp_only] = data
        return data

    def add_skin(
        self,
        obj: bpy.types.Object,
        points: np.ndarray,
        scalp_only: bool,
    ) -> None:
        """Add vertex groups with the weights of the nearest part of the body.

        Args:
            obj (bpy.types.Object): Mesh object to add the vertex groups to.
            points (np.ndarray): (n, 3) world space rest pose coordinates to look up
                the weights of every vertex of the object with.
            scalp_only (bool): Only use the bones of the head, neck and spine.
        """
        names, body_weights, kd = self._skin_data(scalp_only)
        if not names:
            return

        weights = np.zeros((len(points), len(names)), dtype=np.float32)
        for i, point in enumerate(points):
            for _, body_idx, distance in kd.find_n(point, 3):
                weights[i] += body_weights[body_idx] / (distance + 1e-4)

        if weights.shape[1] > MAX_BONE_INFLUENCES:
            cutoff = -np.sort(-weights, axis=1)[:, MAX_BONE_INFLUENCES - 1]
            weights[weights < cutoff[:, None]] = 0
        # Negligible influences still count for the influence limit of engines
        weights[weights < 0.01 * weights.max(axis=1, keepdims=True)] = 0
        weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-9)

        for column, name in enumerate(names):
            vert_idxs = np.flatnonzero(weights[:, column])
            if not len(vert_idxs):
                continue
            vertex_group = obj.vertex_groups.new(name=name)
            for vert_idx in vert_idxs:
                vertex_group.add(
                    [int(vert_idx)], float(weights[vert_idx, column]), "REPLACE"
                )


@contextlib.contextmanager
def _limited_children(particle_system: bpy.types.ParticleSystem) -> Iterator[float]:
    """Temporarily shows a workable number of child hairs in the viewport.

    Yields:
        float: Number of rendered hairs every shown hair stands for.
    """
    settings = particle_system.settings
    if settings.child_type == "NONE":
        yield 1.0
        return

    old_amount = get_children_percent(settings)
    rendered = max(settings.rendered_child_count, 1)
    parent_count = max(len(particle_system.particles), 1)
    amount = max(1, min(rendered, MAX_STRANDS_PER_SYSTEM // parent_count))
    set_children_percent(settings, amount)
    try:
        yield rendered / amount
    finally:
        set_children_percent(settings, old_amount)


def _strands_from_modifier(
    body_obj: bpy.types.Object,
    modifier: bpy.types.ParticleSystemModifier,
    context: bpy.types.Context,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Converts the hairs of a particle system to coordinates.

    Returns:
        tuple[np.ndarray, np.ndarray, np.ndarray]: (n, 3) world space coordinates of
            all hair keys, with for every hair the index of its first key and the
            index after its last key.
    """
    empty = np.zeros((0, 3)), np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)

    existing_objs = set(bpy.data.objects)
    with context_override(context, body_obj, [body_obj]):
        bpy.ops.object.modifier_convert(modifier=modifier.name)
    new_objs = [obj for obj in bpy.data.objects if obj not in existing_objs]
    if not new_objs:
        return empty

    hair_obj = new_objs[0]
    mesh = hair_obj.data
    coords = world_coords_from_obj(hair_obj)
    edges = np.empty(len(mesh.edges) * 2, dtype=np.int32)
    mesh.edges.foreach_get("vertices", edges)
    edges = edges.reshape((-1, 2))
    for obj in new_objs:
        hg_delete(obj)

    # The keys of a hair are consecutive vertices, connected by edges
    if not len(edges) or np.any(np.abs(edges[:, 1] - edges[:, 0]) != 1):
        return empty
    connected_to_next = np.zeros(len(coords), dtype=bool)
    connected_to_next[edges.min(axis=1)] = True
    starts = np.flatnonzero(~np.concatenate(([False], connected_to_next[:-1])))
    ends = np.concatenate((starts[1:], [len(coords)]))
    has_length = ends - starts > 1

    return coords, starts[has_length], ends[has_length]


def _resample(
    coords: np.ndarray, starts: np.ndarray, ends: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Resamples every hair to STATIONS points, spread evenly along its length.

    Returns:
        tuple[np.ndarray, np.ndarray]: (n, STATIONS, 3) points and (n,) lengths.
    """
    segment_lengths = np.linalg.norm(np.diff(coords, axis=0), axis=1)
    # Vertices of different hairs are not connected
    segment_lengths[ends[:-1] - 1] = 0
    cumulative = np.concatenate(([0], np.cumsum(segment_lengths)))
    lengths = cumulative[ends - 1] - cumulative[starts]

    fractions = np.linspace(0, 1, STATIONS)
    targets = cumulative[starts, None] + lengths[:, None] * fractions
    idxs = np.searchsorted(cumulative, targets, side="right") - 1
    idxs = np.clip(idxs, starts[:, None], ends[:, None] - 2)
    segment = np.maximum(segment_lengths[idxs], 1e-12)
    factor = np.clip((targets - cumulative[idxs]) / segment, 0, 1)[..., None]
    points = coords[idxs] * (1 - factor) + coords[idxs + 1] * factor

    return points, lengths


def extract_strands(
    human: "Human",
    modifiers: Iterable[bpy.types.ParticleSystemModifier],
    context: bpy.types.Context,
) -> HairStrands:
    """Gets the hairs of the passed particle systems as resampled strands.

    The human is expected to be in its rest pose, see rest_pose().

    Args:
        human (Human): Human the particle systems belong to.
        modifiers (Iterable[bpy.types.ParticleSystemModifier]): Modifiers of the
            particle systems to get the hairs of.
        context (bpy.types.Context): Blender context.

    Returns:
        HairStrands: Strands of all the particle systems.
    """
    body_obj = human.objects.body
    all_points, all_systems, all_weights = [], [], []
    density_roots = []
    for system_idx, modifier in enumerate(modifiers):
        particle_system = modifier.particle_system
        with _limited_children(particle_system) as hairs_per_strand:
            coords, starts, ends = _strands_from_modifier(body_obj, modifier, context)
        if not len(starts):
            continue

        points, lengths = _resample(coords, starts, ends)
        if not particle_system.vertex_group_density:
            # Hairs can have no length because of a length vertex group
            density_roots.append(coords[starts[lengths > MIN_ROOT_LENGTH]])
        if np.quantile(lengths, 0.9) < SHORT_SYSTEM_LENGTH:
            continue
        long_enough = lengths > MIN_STRAND_LENGTH
        all_points.append(points[long_enough])
        strand_count = int(long_enough.sum())
        all_systems.append(np.full(strand_count, system_idx))
        all_weights.append(np.full(strand_count, hairs_per_strand))

    return HairStrands(
        points=np.concatenate(all_points) if all_points else np.zeros((0, STATIONS, 3)),
        system=np.concatenate(all_systems) if all_systems else np.zeros(0, dtype=int),
        weights=np.concatenate(all_weights) if all_weights else np.zeros(0),
        density_roots=(
            np.concatenate(density_roots) if density_roots else np.zeros((0, 3))
        ),
    )


def _kmeans(
    features: np.ndarray, cluster_count: int, iterations: int = 8
) -> np.ndarray:
    """Groups the rows of the features into clusters of similar rows.

    Deterministic, the same features always give the same clusters.

    Returns:
        np.ndarray: (n,) index of the cluster of every row.
    """
    row_count = len(features)
    if cluster_count >= row_count:
        return np.arange(row_count)

    # Start with centers that are as far away from each other as possible
    center_idxs = [0]
    distance = np.full(row_count, np.inf)
    for _ in range(cluster_count - 1):
        to_last = ((features - features[center_idxs[-1]]) ** 2).sum(axis=1)
        distance = np.minimum(distance, to_last)
        center_idxs.append(int(np.argmax(distance)))
    centers = features[center_idxs].copy()

    squared = (features**2).sum(axis=1)[:, None]
    labels = np.zeros(row_count, dtype=np.int64)
    for _ in range(iterations):
        distances = squared - 2 * features @ centers.T + (centers**2).sum(axis=1)
        labels = np.argmin(distances, axis=1)
        counts = np.bincount(labels, minlength=cluster_count)
        sums = np.zeros_like(centers)
        np.add.at(sums, labels, features)
        filled = counts > 0
        centers[filled] = sums[filled] / counts[filled, None]

    return labels


def _cluster_strands(
    strands: HairStrands, proxy: HeadProxy, clump_count: int
) -> np.ndarray:
    """Divides the strands into clumps of strands that follow a similar path.

    Every particle system gets its own clumps, so the systems with only a few hairs
    that break up the silhouette of the hairstyle are kept.

    Returns:
        np.ndarray: (n,) index of the clump of every strand.
    """
    feature_stations = np.linspace(0, STATIONS - 1, 6).astype(int)
    feature_points = strands.points[:, feature_stations]
    _, distance = proxy.outward(feature_points.reshape((-1, 3)))
    features = np.concatenate(
        (
            feature_points.reshape((len(feature_points), -1)),
            distance.reshape((len(feature_points), -1)) * LAYER_WEIGHT,
        ),
        axis=1,
    )

    systems = np.unique(strands.system)
    shares = np.array(
        [np.sqrt(strands.weights[strands.system == system].sum()) for system in systems]
    )
    shares /= shares.sum()

    labels = np.zeros(len(strands.points), dtype=np.int64)
    label_offset = 0
    for system, share in zip(systems, shares):
        in_system = np.flatnonzero(strands.system == system)
        system_clumps = int(np.clip(round(clump_count * share), 1, len(in_system)))
        system_labels = _kmeans(features[in_system], system_clumps)
        # Some clusters can be empty, make the labels consecutive
        _, system_labels = np.unique(system_labels, return_inverse=True)
        labels[in_system] = system_labels + label_offset
        label_offset += system_labels.max() + 1

    return labels


def _significance(centers: np.ndarray, arc: np.ndarray) -> np.ndarray:
    """Calculates how much every station matters for the shape of its card.

    Stations are judged from coarse to fine: the middle station by its distance to
    the line between the ends of the card, the stations at a quarter by their
    distance to the line between the middle and an end, and so on.

    Returns:
        np.ndarray: (k, STATIONS) error in meters that leaving out the station would
            cause, infinite for stations that are needed to keep the segments short.
    """
    significance = np.zeros(centers.shape[:2])
    step = (STATIONS - 1) // 2
    while step >= 1:
        mids = np.arange(step, STATIONS - 1, 2 * step)
        chord = centers[:, mids + step] - centers[:, mids - step]
        relative = centers[:, mids] - centers[:, mids - step]
        chord_length = np.maximum(np.linalg.norm(chord, axis=2), 1e-9)
        error = np.linalg.norm(np.cross(chord, relative), axis=2) / chord_length
        too_long = arc[:, mids + step] - arc[:, mids - step] > MAX_SEGMENT_LENGTH
        significance[:, mids] = np.where(too_long, np.inf, error)
        step //= 2

    # A station is at least as significant as the finer stations next to it
    step = 1
    while step < (STATIONS - 1) // 2:
        parents = np.arange(2 * step, STATIONS - 1, 4 * step)
        significance[:, parents] = np.maximum.reduce(
            (
                significance[:, parents],
                significance[:, parents - step],
                significance[:, parents + step],
            )
        )
        step *= 2

    return significance


@dataclass
class _Cards:
    """Cards fitted to clumps of strands, before choosing their segments."""

    #: (c, STATIONS, 3) middle line of the cards
    centers: np.ndarray
    #: (c, STATIONS, 3) unit vectors from the middle to the side of the cards
    sides: np.ndarray
    #: (c, STATIONS)
    half_widths: np.ndarray
    #: (c, STATIONS) distance from the root along the card
    arc: np.ndarray
    #: (c, STATIONS) see _significance
    significance: np.ndarray
    #: (c,) average distance to the body
    depths: np.ndarray
    #: (c,) number of rendered hairs the card stands for
    hair_counts: np.ndarray

    def __len__(self) -> int:
        return len(self.centers)


def _card_frames(
    centers: np.ndarray,
    tangents: np.ndarray,
    outward: np.ndarray,
    fallback_sides: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Calculates the direction of the width of the cards at every station.

    Cards lie flat against the head where possible. Where the hair points straight
    away from the head there is no such direction, there the direction is carried
    over from the neighbouring station to prevent the card from twisting.

    Returns:
        tuple[np.ndarray, np.ndarray]: (k, STATIONS, 3) unit vectors and a (k,) mask
            of the clumps that mostly point away from the head.
    """
    clump_count = len(centers)
    rows = np.arange(clump_count)
    flat = np.cross(outward, tangents)
    lying = np.linalg.norm(flat, axis=2)
    flat /= np.maximum(lying, 1e-6)[..., None]
    blend = _smoothstep(0.2, 0.5, lying)

    anchored = lying > 0.5
    has_anchor = anchored.any(axis=1)
    anchor = np.where(has_anchor, anchored.argmax(axis=1), 0)
    fallback = _normalized(_project_perpendicular(fallback_sides, tangents[:, 0]))

    sides = np.zeros_like(centers)
    sides[rows, anchor] = np.where(has_anchor[:, None], flat[rows, anchor], fallback)

    def carry_over(station: int, from_station: int) -> np.ndarray:
        carried = _normalized(
            _project_perpendicular(sides[:, from_station], tangents[:, station])
        )
        same_side = np.einsum("ki,ki->k", flat[:, station], carried) >= 0
        wanted = flat[:, station] * np.where(same_side, 1, -1)[:, None]
        return _normalized(carried + (wanted - carried) * blend[:, station, None])

    for station in range(1, STATIONS):
        todo = station > anchor
        sides[todo, station] = carry_over(station, station - 1)[todo]
    for station in range(STATIONS - 2, -1, -1):
        todo = station < anchor
        sides[todo, station] = carry_over(station, station + 1)[todo]

    # Make the front of all cards face away from the head
    facing = np.einsum("kmi,kmi->k", np.cross(tangents, sides), outward)
    sides[facing < 0] *= -1

    standing = lying.mean(axis=1) < 0.5
    return sides, standing


def _smooth_along_card(values: np.ndarray) -> np.ndarray:
    kernel = np.array((1, 2, 3, 2, 1)) / 9
    padded = np.pad(values, ((0, 0), (2, 2)), mode="edge")
    return sum(  # type:ignore[return-value]
        padded[:, i : i + values.shape[1]] * weight  # noqa
        for i, weight in enumerate(kernel)
    )


def _fit_cards(
    strands: HairStrands, labels: np.ndarray, proxy: HeadProxy, body: BodyReference
) -> _Cards:
    """Fits a card to every clump, and a second crossing card to standing clumps."""
    points = strands.points
    clump_count = int(labels.max()) + 1
    strand_counts = np.bincount(labels, minlength=clump_count)

    centers = np.zeros((clump_count, STATIONS, 3))
    np.add.at(centers, labels, points)
    centers /= strand_counts[:, None, None]
    offsets = points - centers[labels]
    tangents = _normalized(np.gradient(centers, axis=1))

    # The average hair ends where the average tip is, extend the cards to cover the
    # hairs that reach further. Matters most for frizzy hair.
    tip_distance = np.einsum("ni,ni->n", offsets[:, -1], tangents[labels, -1])
    tip_variance = np.bincount(labels, weights=tip_distance**2) / strand_counts
    extension = np.sqrt(tip_variance) * TIP_SPREAD_FACTOR
    along = np.linspace(0, 1, STATIONS)[None, :, None] ** 2
    extended = centers + tangents[:, -1:] * extension[:, None, None] * along
    offsets += centers[labels] - extended[labels]
    centers = extended
    tangents = _normalized(np.gradient(centers, axis=1))
    outward, _ = proxy.outward(centers.reshape((-1, 3)))
    outward = outward.reshape(centers.shape)

    # Direction the strands of the clump are spread out the most
    covariance = np.zeros((clump_count, 3, 3))
    np.add.at(covariance, labels, np.einsum("nmi,nmj->nij", offsets, offsets))
    _, eigenvectors = np.linalg.eigh(covariance)
    spread = eigenvectors[:, :, 2]
    along_hair = np.abs(np.einsum("ki,ki->k", spread, tangents[:, 0])) > 0.9
    spread[along_hair] = eigenvectors[along_hair, :, 1]

    sides, standing = _card_frames(centers, tangents, outward, spread)
    fronts = np.cross(tangents, sides)

    def half_widths(directions: np.ndarray) -> np.ndarray:
        distance = np.einsum("nmi,nmi->nm", offsets, directions[labels])
        variance = np.zeros((clump_count, STATIONS))
        np.add.at(variance, labels, distance**2)
        deviation = np.sqrt(variance / strand_counts[:, None])
        widths = np.clip(
            deviation * SPREAD_FACTOR + WIDTH_PADDING, MIN_HALF_WIDTH, MAX_HALF_WIDTH
        )
        return _smooth_along_card(widths)

    arc = np.zeros((clump_count, STATIONS))
    arc[:, 1:] = np.cumsum(np.linalg.norm(np.diff(centers, axis=1), axis=2), axis=1)
    # Clumps of hairs that point in different directions are short and wide, the
    # hairs of the texture would be stretched sideways on a card of that shape
    max_widths = np.maximum(arc[:, -1:] * MAX_WIDTH_TO_LENGTH, MIN_HALF_WIDTH)
    side_widths = np.minimum(half_widths(sides), max_widths)
    front_widths = np.maximum(half_widths(fronts), side_widths * 0.6)
    front_widths = np.minimum(front_widths, max_widths)

    depth_stations = centers[:, STATIONS // 4 :: STATIONS // 4]  # noqa
    depths = body.distances(depth_stations.reshape((-1, 3)))
    depths = depths.reshape((clump_count, -1)).mean(axis=1)
    hair_counts = np.bincount(labels, weights=strands.weights, minlength=clump_count)
    significance = _significance(centers, arc)

    def with_crossing(
        values: np.ndarray, crossing: Optional[np.ndarray] = None
    ) -> np.ndarray:
        crossing = values if crossing is None else crossing
        return np.concatenate((values, crossing[standing]))

    return _Cards(
        centers=with_crossing(centers),
        sides=with_crossing(sides, fronts),
        half_widths=with_crossing(side_widths, front_widths),
        arc=with_crossing(arc),
        significance=with_crossing(significance),
        depths=with_crossing(depths),
        hair_counts=with_crossing(hair_counts),
    )


def _select_stations(cards: _Cards, triangle_budget: int) -> np.ndarray:
    """Chooses the stations that become the segments of the cards.

    Returns:
        np.ndarray: (c, STATIONS) mask of the stations to use.
    """
    selected = np.zeros(cards.significance.shape, dtype=bool)
    selected[:, (0, -1)] = True

    inner = cards.significance[:, 1:-1]
    order = np.argsort(-inner, axis=None, kind="stable")
    affordable = max((triangle_budget - 2 * len(cards)) // 2, 0)
    useful = int((inner >= MIN_TOLERANCE).sum())
    chosen = order[: min(affordable, useful)]
    selected[:, 1:-1].flat[chosen] = True

    return selected


class HairAtlas:
    """Parts of the hair texture that can be used for cards."""

    def __init__(self) -> None:
        json_path = os.path.join(
            get_prefs().filepath, "hair", "haircards", "HairMediumLength_zones.json"
        )
        with open(json_path, "r") as f:
            zone_dict = json.load(f)

        self._zones: dict[tuple[str, str, str], list[Rect]] = {}
        for length, densities in zone_dict.items():
            for density, widths in densities.items():
                for width, rects in widths.items():
                    # Some zones in the json are lines instead of rectangles
                    zones = self._zones.setdefault((length, density, width), [])
                    zones.extend(
                        self._sorted_rect(rect)
                        for rect in rects
                        if self._has_area(rect)
                    )

    @staticmethod
    def _has_area(rect: Rect) -> bool:
        (x1, y1), (x2, y2) = rect
        return abs(x2 - x1) > 0.001 and abs(y2 - y1) > 0.001

    @staticmethod
    def _sorted_rect(rect: Rect) -> Rect:
        (x1, y1), (x2, y2) = rect
        return (min(x1, x2), min(y1, y2)), (max(x1, x2), max(y1, y2))

    def pick(
        self,
        length: float,
        width: float,
        hairs_per_cm: float,
        solid: bool,
        rng: np.random.Generator,
    ) -> Rect:
        """Choose a part of the texture that fits a card.

        Args:
            length (float): Length of the card in meters.
            width (float): Average width of the card in meters.
            hairs_per_cm (float): Number of hairs per cm of card width.
            solid (bool): Use the part of the texture without gaps for wide cards.
            rng (np.random.Generator): Generator to choose between alternatives.

        Returns:
            Rect: Bottom left and top right UV coordinates of the part.
        """
        is_long = length > LONG_CARD_LENGTH
        is_wide = width > (0.02 if is_long else 0.01)
        # The roots of the solid part are a hard line, which shows on short cards
        # as those are often not covered by other cards
        if solid and is_wide and length > SOLID_CARD_LENGTH:
            return SOLID_ZONE

        length_key = "long" if is_long else "short"
        density_key = "sparse" if hairs_per_cm < SPARSE_DENSITY else "dense"
        width_key = "wide" if is_wide else "narrow"
        other_density = "dense" if density_key == "sparse" else "sparse"
        other_width = "narrow" if is_wide else "wide"
        for key in (
            (length_key, density_key, width_key),
            (length_key, other_density, width_key),
            (length_key, density_key, other_width),
            (length_key, other_density, other_width),
        ):
            rects = self._zones.get(key)
            if rects:
                return rects[int(rng.integers(len(rects)))]

        return SOLID_ZONE


def build_card_geometry(
    strands: HairStrands,
    proxy: HeadProxy,
    body: BodyReference,
    triangle_budget: int,
    seed: int = 0,
) -> Optional[CardGeometry]:
    """Builds haircards for the strands that fit within the triangle budget.

    Args:
        strands (HairStrands): Strands to build cards for.
        proxy (HeadProxy): Proxy of the head of the human.
        body (BodyReference): Body data of the human.
        triangle_budget (int): Maximum number of triangles of the cards.
        seed (int): Seed for the random choices, the same seed gives the same cards.

    Returns:
        Optional[CardGeometry]: Mesh data of the cards, None if there are no strands
            or the budget is too small for any cards.
    """
    strand_count = len(strands.points)
    if not strand_count or triangle_budget < 2:
        return None

    system_count = len(np.unique(strands.system))
    max_clumps = max(system_count, strand_count // MIN_STRANDS_PER_CLUMP)
    clump_count = min(max_clumps, max(1, triangle_budget // 8))
    for attempt in range(4):
        labels = _cluster_strands(strands, proxy, clump_count)
        cards = _fit_cards(strands, labels, proxy, body)
        if attempt == 3:
            break
        # Change the number of clumps until the cards with the segments they need
        # fill the budget
        wanted_stations = (cards.significance[:, 1:-1] >= WANTED_TOLERANCE).sum()
        wanted_triangles = 2 * len(cards) + 2 * int(wanted_stations)
        fits = 0.8 * triangle_budget <= wanted_triangles <= triangle_budget
        new_count = int(clump_count * 0.95 * triangle_budget / wanted_triangles)
        new_count = int(np.clip(new_count, 1, max_clumps))
        if fits or new_count == clump_count:
            break
        clump_count = new_count

    if 2 * len(cards) > triangle_budget:
        # Every particle system gets at least one card, which is too much for a
        # tiny budget
        return None

    # From the inner to the outer cards, the order engines should draw them in
    order = np.argsort(cards.depths, kind="stable")
    cards = _Cards(**{name: value[order] for name, value in vars(cards).items()})
    selected = _select_stations(cards, triangle_budget)

    card_count = len(cards)
    rng = np.random.default_rng(seed)
    atlas = HairAtlas()
    lengths = cards.arc[:, -1]
    widths = 2 * cards.half_widths.mean(axis=1)
    hairs_per_cm = cards.hair_counts / (widths * 100)
    layers = np.linspace(0, 1, card_count) if card_count > 1 else np.zeros(1)

    card_idxs, station_idxs = np.nonzero(selected)
    centers = cards.centers[card_idxs, station_idxs]
    to_side = (
        cards.sides[card_idxs, station_idxs]
        * cards.half_widths[card_idxs, station_idxs, None]
    )
    along = cards.arc[card_idxs, station_idxs] / np.maximum(lengths[card_idxs], 1e-9)

    uv_rects = np.empty((card_count, 4))
    for card_idx in range(card_count):
        (u_min, v_min), (u_max, v_max) = atlas.pick(
            lengths[card_idx],
            widths[card_idx],
            hairs_per_cm[card_idx],
            layers[card_idx] < SOLID_SHARE,
            rng,
        )
        if rng.random() < 0.5:
            u_min, u_max = u_max, u_min
        uv_rects[card_idx] = (u_min, v_min, u_max, v_max)
    u_min, v_min, u_max, v_max = uv_rects[card_idxs].T
    # The roots are at the top of the texture
    v = v_max - (v_max - v_min) * along

    station_count = len(card_idxs)
    random_per_card = rng.random(card_count)

    def per_side(right: np.ndarray, left: np.ndarray) -> np.ndarray:
        """Interleaves values for the vertices at the right and left of the cards."""
        return np.stack((right, left), axis=1).reshape((station_count * 2, -1))

    vertices = per_side(centers + to_side, centers - to_side)
    uvs = per_side(np.stack((u_max, v), axis=1), np.stack((u_min, v), axis=1))
    color = np.stack(
        (along, random_per_card[card_idxs], layers[card_idxs], np.ones(station_count)),
        axis=1,
    )
    normals, _ = proxy.outward(vertices)

    same_card = np.flatnonzero(card_idxs[:-1] == card_idxs[1:])
    faces = np.stack(
        (same_card * 2, same_card * 2 + 1, same_card * 2 + 3, same_card * 2 + 2),
        axis=1,
    )

    return CardGeometry(
        vertices=vertices,
        faces=faces,
        uvs=uvs,
        colors=per_side(color, color),
        normals=normals,
        skin_points=per_side(centers, centers),
        card_count=card_count,
    )


def set_custom_normals(mesh: bpy.types.Mesh, normals: np.ndarray) -> None:
    """Sets custom normals for all vertices of the mesh.

    Args:
        mesh (bpy.types.Mesh): Mesh to set the normals of.
        normals (np.ndarray): (v, 3) unit vectors.
    """
    if hasattr(mesh, "use_auto_smooth"):
        mesh.use_auto_smooth = True
    mesh.normals_split_custom_set_from_vertices(normals.tolist())


def _transform(matrix: Matrix, coords: np.ndarray) -> np.ndarray:
    matrix_np = np.array(matrix)
    return coords @ matrix_np[:3, :3].T + matrix_np[:3, 3]


def parent_to_rig(obj: bpy.types.Object, rig: bpy.types.Object) -> None:
    """Parents the object to the rig and makes the rig deform it.

    The mesh of the object is expected to be in the space of the rig.

    Args:
        obj (bpy.types.Object): Object to parent.
        rig (bpy.types.Object): Armature object of the human.
    """
    obj.parent = rig
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_basis = Matrix.Identity(4)
    modifier = obj.modifiers.new("Armature", "ARMATURE")
    modifier.object = rig


def create_card_object(
    geometry: CardGeometry,
    human: "Human",
    body: BodyReference,
    context: bpy.types.Context,
) -> bpy.types.Object:
    """Creates a skinned mesh object from the geometry of haircards.

    Args:
        geometry (CardGeometry): Mesh data of the cards.
        human (Human): Human the cards belong to.
        body (BodyReference): Body data of the human.
        context (bpy.types.Context): Blender context.

    Returns:
        bpy.types.Object: Object with the cards, in the space of the rig.
    """
    mx_to_rig = human.objects.rig.matrix_world.inverted()
    vertices = _transform(mx_to_rig, geometry.vertices)
    normals = _normalized(geometry.normals @ np.array(mx_to_rig)[:3, :3].T)

    mesh = bpy.data.meshes.new("Haircards")
    mesh.from_pydata(vertices.tolist(), [], geometry.faces.tolist())
    mesh.polygons.foreach_set("use_smooth", np.ones(len(mesh.polygons), dtype=bool))

    loop_verts = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", loop_verts)
    uv_layer = mesh.uv_layers.new(name=UV_NAME)
    uv_layer.data.foreach_set("uv", geometry.uvs[loop_verts].ravel())
    color_attribute = mesh.color_attributes.new(COLOR_ATTRIBUTE, "FLOAT_COLOR", "POINT")
    color_attribute.data.foreach_set("color", geometry.colors.ravel())
    set_custom_normals(mesh, normals)
    mesh.update()

    obj = bpy.data.objects.new("Haircards", mesh)
    context.scene.collection.objects.link(obj)
    body.add_skin(obj, geometry.skin_points, scalp_only=True)

    return obj


@contextlib.contextmanager
def _reuse_images() -> Iterator[None]:
    """Replaces images that get loaded by images of the same file that already exist.

    Yields:
        None
    """

    def key(image: bpy.types.Image) -> tuple[str, str, str]:
        path = bpy.path.abspath(image.filepath, library=image.library)
        return path, image.colorspace_settings.name, image.alpha_mode

    existing = {key(image): image for image in bpy.data.images if image.filepath}
    yield
    new_images = [img for img in bpy.data.images if img not in existing.values()]
    for image in new_images:
        original = existing.get(key(image)) if image.filepath else None
        if original:
            image.user_remap(original)
            bpy.data.images.remove(image)
        elif image.filepath:
            existing[key(image)] = image


def load_card_material() -> bpy.types.Material:
    """Gets a new material for haircards.

    Returns:
        bpy.types.Material: Material for all cards of one human.
    """
    mat = bpy.data.materials.get("HG_Haircards")
    if mat:
        return mat.copy()

    blendpath = os.path.join(
        get_prefs().filepath, "hair", "haircards", "haircards_material.blend"
    )
    with _reuse_images():
        with bpy.data.libraries.load(blendpath, link=False) as (_, data_to):
            data_to.materials = ["HG_Haircards"]

    return data_to.materials[0]


def _boundary_verts(mesh: bpy.types.Mesh) -> np.ndarray:
    """Gets the indices of the vertices on the open edges of the mesh."""
    loop_edges = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("edge_index", loop_edges)
    face_counts = np.bincount(loop_edges, minlength=len(mesh.edges))
    edge_verts = np.empty(len(mesh.edges) * 2, dtype=np.int32)
    mesh.edges.foreach_get("vertices", edge_verts)
    return np.unique(edge_verts.reshape((-1, 2))[face_counts == 1])


def create_haircap(
    human: "Human",
    body: BodyReference,
    haircap_type: HaircapType,
    density_vertex_groups: list[tuple[bpy.types.VertexGroup, float]],
    density_roots: np.ndarray,
    context: bpy.types.Context,
) -> bpy.types.Object:
    """Creates a haircap object, fitted and skinned to the body of the human.

    The haircap is a mesh that lies on the skin, with a texture of hair. The hair is
    only visible where the human has hair, based on the density vertex groups of the
    hair systems and the roots of the hairs of systems without such a vertex group.

    Args:
        human (Human): The human to add the haircap to.
        body (BodyReference): Body data of the human.
        haircap_type (HaircapType): Part of the body to add the haircap to.
        density_vertex_groups (list[tuple[bpy.types.VertexGroup, float]]): The density
            vertex groups of the hair systems, with the weight they count with.
        density_roots (np.ndarray): (n, 3) world space coordinates of the roots of
            the hairs of the systems without a density vertex group.
        context (bpy.types.Context): Blender context.

    Returns:
        bpy.types.Object: The haircap object, in the space of the rig.
    """
    body_obj = human.objects.body
    blendfile = os.path.join(get_prefs().filepath, "hair", "haircards", "haircap.blend")
    with _reuse_images():
        with bpy.data.libraries.load(blendfile, link=False) as (_, data_to):
            data_to.objects = [f"HG_Haircap_{haircap_type}"]

    haircap_obj = data_to.objects[0]
    context.scene.collection.objects.link(haircap_obj)
    mesh = haircap_obj.data

    # The haircap was modelled on the base shape of the body, move every vertex
    # along with the nearest vertex of the body
    cap_coords = world_coords_from_obj(haircap_obj, local=True)
    kd_base = create_kdtree(body.base_coords_local)
    nearest = np.array([kd_base.find(co)[1] for co in cap_coords])
    fitted = body.coords_local[nearest] + cap_coords - body.base_coords_local[nearest]
    fitted_world = _transform(body_obj.matrix_world, fitted)
    fitted_rig = _transform(human.objects.rig.matrix_world.inverted(), fitted_world)
    mesh.vertices.foreach_set("co", fitted_rig.ravel())

    if haircap_type in ("Scalp", "Beard"):
        factors = {vg.index: factor for vg, factor in density_vertex_groups}
        body_density = np.zeros(len(body_obj.data.vertices), dtype=np.float32)
        for vert in body_obj.data.vertices:
            for group in vert.groups:
                if group.group in factors:
                    body_density[vert.index] += group.weight * factors[group.group]
        density = np.clip(np.round(body_density[nearest], 4), 0, 1)

        if len(density_roots):
            kd_roots = create_kdtree(density_roots)
            root_distance = np.array([kd_roots.find(co)[2] for co in fitted_world])
            density = np.maximum(density, 1 - _smoothstep(0.01, 0.022, root_distance))

        if density.max() < 0.001:
            density[:] = 1
        # Fade out the hair towards the border of the haircap
        density[_boundary_verts(mesh)] = 0

        colors = np.ones((len(density), 4), dtype=np.float32)
        colors[:, :3] = density[:, None]
        mesh.color_attributes[0].data.foreach_set("color", colors.ravel())

    mesh.update()
    body.add_skin(haircap_obj, fitted_world, scalp_only=haircap_type == "Scalp")

    return haircap_obj
