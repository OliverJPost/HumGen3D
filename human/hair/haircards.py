# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements generating game engine ready haircards from particle hair systems.

The particle hairs are grouped into clumps of hairs that follow a similar path. Every
clump becomes one card, which follows the average hair of the clump and is as wide as
the clump. The number of clumps and the number of segments of each card are chosen to
fit a triangle budget, so the result has a predictable size for every hairstyle.

Extracting the strands (extract_strands) is separated from building the cards
(build_card_geometry), so cards for multiple budgets can be built from the same
strands.

The haircap that goes under the cards is implemented in haircap.py, keeping the hair
attached to the skin in hair_binding.py.
"""

import contextlib
import json
import os
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Iterable, Iterator, Optional, Union

import bpy
import numpy as np
from HumGen3D import get_prefs
from HumGen3D.common.context import context_override
from HumGen3D.common.geometry import world_coords_from_obj
from HumGen3D.common.math import create_kdtree
from HumGen3D.common.memory_management import hg_delete
from HumGen3D.common.shadernode import COLOR1_INPUT_NAME, COLOR2_INPUT_NAME
from HumGen3D.human.hair import hair_binding
from HumGen3D.human.hair.compatibility import (
    SPECULAR_INPUT_NAME,
    get_children_percent,
    set_children_percent,
)
from mathutils import Matrix

if TYPE_CHECKING:
    from ..human import Human

Rect = tuple[tuple[float, float], tuple[float, float]]
# Names of the vertex groups, their weights per usable vertex and a kdtree of those
SkinData = tuple[list[str], np.ndarray, Any]



@dataclass(frozen=True)
class ColorMatch:
    """Corrections that make a material look like particle hair of the same color.

    Measured by comparing renders of particle hair with renders of the material,
    for several values of the lightness and redness of the hair.
    """

    #: Factor for the brightness of the hair color
    value: float
    #: Factors for the saturation of the hair color, for a redness of 0.3 and 0.8
    saturations: tuple[float, float]
    #: Specular of the material, or the factor for its specular texture if it has
    #: one. None to leave it as it is.
    specular: Optional[float] = None
    #: Roughness of the material, None to leave it as it is
    roughness: Optional[float] = None

    def saturation(self, redness: float) -> float:
        """Get the saturation factor for hair with the passed redness.

        Args:
            redness (float): Redness of the hair.

        Returns:
            float: Factor to multiply the saturation of the hair color with.
        """
        low, high = self.saturations
        factor = low + (high - low) * (redness - 0.3) / 0.5
        return float(np.clip(factor, min(low, high) * 0.8, max(low, high) * 1.2))


# The haircap material is as shiny as skin, which makes dark hair look grey
HAIRCAP_COLOR_MATCH = ColorMatch(
    value=0.95, saturations=(1.3, 0.88), specular=0.15, roughness=0.7
)


@dataclass(frozen=True)
class CardSettings:
    """Sizes of haircards, which differ between the hair on the scalp and the face."""

    #: Maximum triangle count of the whole hair object, so cards plus haircap, for
    #: every quality
    triangle_budgets: dict[str, int]
    #: Particle systems with hairs shorter than this only show on the haircap
    short_system_length: float
    #: Hairs shorter than this don't get a card
    min_strand_length: float
    #: Hairs shorter than this don't count as hair growing on that part of the skin
    min_root_length: float
    max_segment_length: float
    #: Segments are added until the cards deviate less than this from the clumps
    wanted_tolerance: float
    min_tolerance: float
    min_half_width: float
    max_half_width: float
    width_padding: float
    #: Maximum of half the width of a card, relative to its length
    max_width_to_length: float
    #: Only skin the cards to the bones of the head, neck and spine
    scalp_only_skin: bool
    #: Use the normals of the skin as outward direction, instead of the head proxy
    skin_normals: bool
    #: Corrections for the color of the card material
    color_match: ColorMatch


SCALP_SETTINGS = CardSettings(
    triangle_budgets={"ultra": 24000, "high": 12000, "medium": 7000, "low": 4500},
    short_system_length=0.02,
    min_strand_length=0.01,
    min_root_length=0.002,
    max_segment_length=0.08,
    wanted_tolerance=0.002,
    min_tolerance=0.0004,
    min_half_width=0.004,
    max_half_width=0.04,
    width_padding=0.003,
    max_width_to_length=0.25,
    scalp_only_skin=True,
    skin_normals=False,
    color_match=ColorMatch(value=0.26, saturations=(0.97, 0.89)),
)
# Face hair is a lot shorter and its skin moves with the expressions of the face
FACE_SETTINGS = CardSettings(
    triangle_budgets={"ultra": 10000, "high": 7000, "medium": 5000, "low": 3500},
    short_system_length=0.003,
    min_strand_length=0.002,
    min_root_length=0.0001,
    max_segment_length=0.03,
    wanted_tolerance=0.0007,
    min_tolerance=0.0002,
    min_half_width=0.0015,
    max_half_width=0.012,
    width_padding=0.001,
    max_width_to_length=0.5,
    scalp_only_skin=False,
    skin_normals=True,
    # Darker than the cards on the scalp: face hair cards stand apart on the skin,
    # without other cards casting shadows on them
    color_match=ColorMatch(value=0.36, saturations=(1.1, 1.0)),
)
QUALITY_TRIANGLE_BUDGETS = SCALP_SETTINGS.triangle_budgets

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
MIN_STRANDS_PER_CLUMP = 4
# Every this many stations of a strand is used to find out where hair covers the skin
DENSITY_STATION_STEP = 4

# Number of standard deviations of the clump the card extends to each side
SPREAD_FACTOR = 1.6
# Number of standard deviations of the tips of the clump the card is extended with
TIP_SPREAD_FACTOR = 1.0
# Extra weight of the distance to the head when comparing strands, to get clumps that
# are layers on top of each other instead of thick bundles
LAYER_WEIGHT = 1.5


# How far the hair color is mixed with white for the maximum amount of grey hairs,
# measured in the same way
GREY_HAIR_SHARE = 0.09
COLOR_MATCH_NODE_NAME = "HG_Color_Match"
SPECULAR_MATCH_NODE_NAME = "HG_Specular_Match"
GREY_HAIR_NODE_NAME = "HG_Grey_Hair"

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
    #: (n,) mask of the strands that are long enough to get a card
    for_cards: np.ndarray
    #: (m, 3) points on the hairs of systems without a density vertex group, to
    #: find out where those systems cover the skin
    density_points: np.ndarray

    def card_strands(self) -> "HairStrands":
        """Get the strands that are long enough to get a card.

        Returns:
            HairStrands: Strands to build cards for with build_card_geometry.
        """
        return replace(
            self,
            points=self.points[self.for_cards],
            system=self.system[self.for_cards],
            weights=self.weights[self.for_cards],
            for_cards=self.for_cards[self.for_cards],
        )


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
    #: (v, 3) root of the card of every vertex
    root_points: np.ndarray
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

    def __init__(self, human: "Human", context: bpy.types.Context) -> None:
        """Gather the data of the body of this human, in its current pose.

        The human is expected to be in its rest pose, see rest_pose().

        Args:
            human (Human): Human to get the body data of.
            context (bpy.types.Context): Blender context.
        """
        self._human = human
        body = human.objects.body
        self.base_coords_local = hair_binding.base_body_coords(body)
        #: Values of the animated shape keys, like expressions, the body has now
        self.dynamic_values = hair_binding.dynamic_key_values(human, context)
        self.coords_local = hair_binding.static_body_coords(
            human
        ) + hair_binding.dynamic_displacement(human, self.dynamic_values)
        self.coords_world = hair_binding.transform_coords(
            body.matrix_world, self.coords_local
        )
        self.kd = create_kdtree(self.coords_world)
        self._skin_cache: dict[bool, SkinData] = {}

    def nearest_verts(self, points: np.ndarray) -> np.ndarray:
        """Get the index of the nearest body vertex for all points.

        Args:
            points (np.ndarray): (n, 3) world space coordinates.

        Returns:
            np.ndarray: (n,) indices of body vertices.
        """
        return np.array([self.kd.find(point)[1] for point in points], dtype=np.int64)

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


class SkinProxy:
    """Uses the normals of the skin as outward direction of the hair.

    For short hair on the face, where the skin under the chin and on the neck does
    not face away from the center of the head.
    """

    def __init__(self, human: "Human", body: BodyReference) -> None:
        """Create a new proxy.

        Args:
            human (Human): Human to create the proxy for.
            body (BodyReference): Body data of the human.
        """
        self._body = body
        body_obj = human.objects.body
        mesh = body_obj.data
        normals = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
        mesh.vertices.foreach_get("normal", normals)
        rotation = np.array(body_obj.matrix_world)[:3, :3]
        normals = _normalized(normals.reshape((-1, 3)) @ rotation.T)

        # Smooth the normals, so neighbouring cards face the same way
        edges = np.empty(len(mesh.edges) * 2, dtype=np.int32)
        mesh.edges.foreach_get("vertices", edges)
        edges = edges.reshape((-1, 2))
        for _ in range(3):
            summed = normals.copy()
            np.add.at(summed, edges[:, 0], normals[edges[:, 1]])
            np.add.at(summed, edges[:, 1], normals[edges[:, 0]])
            normals = _normalized(summed)
        self._normals = normals

    def outward(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Get the direction away from the skin and the distance to the skin.

        Args:
            points (np.ndarray): (n, 3) world space coordinates.

        Returns:
            tuple[np.ndarray, np.ndarray]: (n, 3) normals of the nearest body
                vertices and the (n,) distances to those vertices.
        """
        vert_idxs = np.empty(len(points), dtype=np.int64)
        distances = np.empty(len(points))
        for i, point in enumerate(points):
            _, vert_idxs[i], distances[i] = self._body.kd.find(point)

        return self._normals[vert_idxs], distances


Proxy = Union[HeadProxy, SkinProxy]


def outward_proxy(human: "Human", body: BodyReference, settings: CardSettings) -> Proxy:
    """Get the proxy for the outward direction of hair with the passed settings.

    Args:
        human (Human): Human to get the proxy for.
        body (BodyReference): Body data of the human.
        settings (CardSettings): Settings of the hair type.

    Returns:
        Proxy: Proxy to build cards with.
    """
    if settings.skin_normals:
        return SkinProxy(human, body)
    return HeadProxy.from_human(human)


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
    settings: CardSettings = SCALP_SETTINGS,
) -> HairStrands:
    """Gets the hairs of the passed particle systems as resampled strands.

    The human is expected to be in its rest pose, see rest_pose().

    Args:
        human (Human): Human the particle systems belong to.
        modifiers (Iterable[bpy.types.ParticleSystemModifier]): Modifiers of the
            particle systems to get the hairs of.
        context (bpy.types.Context): Blender context.
        settings (CardSettings): Settings of the hair type.

    Returns:
        HairStrands: Strands of all the particle systems.
    """
    body_obj = human.objects.body
    all_points, all_systems, all_weights, all_for_cards = [], [], [], []
    density_points = []
    for system_idx, modifier in enumerate(modifiers):
        particle_system = modifier.particle_system
        with _limited_children(particle_system) as hairs_per_strand:
            coords, starts, ends = _strands_from_modifier(body_obj, modifier, context)
        if not len(starts):
            continue

        points, lengths = _resample(coords, starts, ends)
        # Hairs can have no length because of a length vertex group
        has_length = lengths > settings.min_root_length
        if not has_length.any():
            continue
        points, lengths = points[has_length], lengths[has_length]
        if not particle_system.vertex_group_density:
            density_points.append(points[:, ::DENSITY_STATION_STEP].reshape((-1, 3)))

        is_long_system = np.quantile(lengths, 0.9) >= settings.short_system_length
        all_points.append(points)
        all_systems.append(np.full(len(points), system_idx))
        all_weights.append(np.full(len(points), hairs_per_strand))
        all_for_cards.append(is_long_system & (lengths > settings.min_strand_length))

    if not all_points:
        return HairStrands(
            points=np.zeros((0, STATIONS, 3)),
            system=np.zeros(0, dtype=int),
            weights=np.zeros(0),
            for_cards=np.zeros(0, dtype=bool),
            density_points=np.zeros((0, 3)),
        )

    return HairStrands(
        points=np.concatenate(all_points),
        system=np.concatenate(all_systems),
        weights=np.concatenate(all_weights),
        for_cards=np.concatenate(all_for_cards),
        density_points=(
            np.concatenate(density_points) if density_points else np.zeros((0, 3))
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
    strands: HairStrands, proxy: Proxy, clump_count: int
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


def _significance(
    centers: np.ndarray, arc: np.ndarray, settings: CardSettings
) -> np.ndarray:
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
        span = arc[:, mids + step] - arc[:, mids - step]
        too_long = span > settings.max_segment_length
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
    strands: HairStrands,
    labels: np.ndarray,
    proxy: Proxy,
    body: BodyReference,
    settings: CardSettings,
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
            deviation * SPREAD_FACTOR + settings.width_padding,
            settings.min_half_width,
            settings.max_half_width,
        )
        return _smooth_along_card(widths)

    arc = np.zeros((clump_count, STATIONS))
    arc[:, 1:] = np.cumsum(np.linalg.norm(np.diff(centers, axis=1), axis=2), axis=1)
    # Clumps of hairs that point in different directions are short and wide, the
    # hairs of the texture would be stretched sideways on a card of that shape
    max_widths = np.maximum(
        arc[:, -1:] * settings.max_width_to_length, settings.min_half_width
    )
    side_widths = np.minimum(half_widths(sides), max_widths)
    front_widths = np.maximum(half_widths(fronts), side_widths * 0.6)
    front_widths = np.minimum(front_widths, max_widths)

    depth_stations = centers[:, STATIONS // 4 :: STATIONS // 4]  # noqa
    depths = body.distances(depth_stations.reshape((-1, 3)))
    depths = depths.reshape((clump_count, -1)).mean(axis=1)
    hair_counts = np.bincount(labels, weights=strands.weights, minlength=clump_count)
    significance = _significance(centers, arc, settings)

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


def _select_stations(
    cards: _Cards, triangle_budget: int, settings: CardSettings
) -> np.ndarray:
    """Chooses the stations that become the segments of the cards.

    Returns:
        np.ndarray: (c, STATIONS) mask of the stations to use.
    """
    selected = np.zeros(cards.significance.shape, dtype=bool)
    selected[:, (0, -1)] = True

    inner = cards.significance[:, 1:-1]
    order = np.argsort(-inner, axis=None, kind="stable")
    affordable = max((triangle_budget - 2 * len(cards)) // 2, 0)
    useful = int((inner >= settings.min_tolerance).sum())
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
    proxy: Proxy,
    body: BodyReference,
    triangle_budget: int,
    settings: CardSettings = SCALP_SETTINGS,
    seed: int = 0,
) -> Optional[CardGeometry]:
    """Builds haircards for the strands that fit within the triangle budget.

    Args:
        strands (HairStrands): Strands to build cards for, see
            HairStrands.card_strands.
        proxy (Proxy): Proxy for the outward direction of the hair.
        body (BodyReference): Body data of the human.
        triangle_budget (int): Maximum number of triangles of the cards.
        settings (CardSettings): Settings of the hair type.
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
        cards = _fit_cards(strands, labels, proxy, body, settings)
        if attempt == 3:
            break
        # Change the number of clumps until the cards with the segments they need
        # fill the budget
        is_wanted = cards.significance[:, 1:-1] >= settings.wanted_tolerance
        wanted_triangles = 2 * len(cards) + 2 * int(is_wanted.sum())
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
    selected = _select_stations(cards, triangle_budget, settings)

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
        root_points=cards.centers[np.repeat(card_idxs, 2), 0],
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
    settings: CardSettings = SCALP_SETTINGS,
) -> bpy.types.Object:
    """Creates a skinned mesh object from the geometry of haircards.

    Args:
        geometry (CardGeometry): Mesh data of the cards.
        human (Human): Human the cards belong to.
        body (BodyReference): Body data of the human.
        context (bpy.types.Context): Blender context.
        settings (CardSettings): Settings of the hair type.

    Returns:
        bpy.types.Object: Object with the cards, in the space of the rig.
    """
    mx_to_rig = human.objects.rig.matrix_world.inverted()
    vertices = hair_binding.transform_coords(mx_to_rig, geometry.vertices)
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
    # Every card moves as a whole with the skin under its root. The vertices of a
    # card share the same root, so only look up every second root of every card.
    root_verts = body.nearest_verts(geometry.root_points[::2])
    hair_binding.set_attachment(mesh, np.repeat(root_verts, 2))
    mesh.update()

    obj = bpy.data.objects.new("Haircards", mesh)
    context.scene.collection.objects.link(obj)
    body.add_skin(obj, geometry.skin_points, scalp_only=settings.scalp_only_skin)

    return obj


@contextlib.contextmanager
def reuse_images() -> Iterator[None]:
    """Replaces images that get loaded by images of the same file that already exist.

    Only the images that are loaded within this context are replaced and removed.
    Images that existed before can already be in use by the viewport, removing those
    crashes Blender the next time the viewport is drawn.

    Yields:
        None
    """

    def key(image: bpy.types.Image) -> tuple[str, str, str]:
        path = bpy.path.abspath(image.filepath, library=image.library)
        return path, image.colorspace_settings.name, image.alpha_mode

    images_before = list(bpy.data.images)
    yield
    originals: dict[tuple[str, str, str], bpy.types.Image] = {}
    for image in images_before:
        if image.filepath:
            originals.setdefault(key(image), image)

    loaded_images = [img for img in bpy.data.images if img not in images_before]
    for image in loaded_images:
        if not image.filepath:
            continue
        original = originals.setdefault(key(image), image)
        if original != image:
            image.user_remap(original)
            bpy.data.images.remove(image)


def _keep_color_between_hairs(material: bpy.types.Material) -> None:
    """Stops the cards from getting darker when they are small on screen.

    The occlusion texture that darkens the hair color is black between the hairs.
    When a card is small on screen the hairs and the black between them are
    averaged, which made the hair a lot darker. Dividing by the alpha texture, which
    is averaged the same way, gives the occlusion of only the hairs.
    """
    group_node = next(
        node for node in material.node_tree.nodes if node.bl_idname == "ShaderNodeGroup"
    )
    tree = group_node.node_tree
    if tree.get("hg_occlusion_divided"):
        return

    def image_node(name_part: str) -> Optional[bpy.types.Node]:
        return next(
            (
                node
                for node in tree.nodes
                if node.bl_idname == "ShaderNodeTexImage"
                and node.image
                and name_part in node.image.name
            ),
            None,
        )

    occlusion_node, alpha_node = image_node("_AO"), image_node("_ALPHA")
    occlusion_links = [
        link for link in tree.links if link.from_node == occlusion_node
    ]
    if not occlusion_node or not alpha_node or len(occlusion_links) != 1:
        return

    target_socket = occlusion_links[0].to_socket
    tree.links.remove(occlusion_links[0])
    alpha = tree.nodes.new("ShaderNodeMath")
    alpha.operation = "MAXIMUM"
    alpha.inputs[1].default_value = 0.02
    divide = tree.nodes.new("ShaderNodeMath")
    divide.operation = "DIVIDE"
    divide.use_clamp = True
    tree.links.new(alpha_node.outputs["Color"], alpha.inputs[0])
    tree.links.new(occlusion_node.outputs["Color"], divide.inputs[0])
    tree.links.new(alpha.outputs[0], divide.inputs[1])
    tree.links.new(divide.outputs[0], target_socket)
    tree["hg_occlusion_divided"] = True


def match_particle_color(
    material: bpy.types.Material,
    color_match: ColorMatch,
    redness: float,
    grey_hair: float,
) -> None:
    """Makes the color of a haircard or haircap material look like particle hair.

    The materials calculate the hair color in another way than the material of the
    particle hair, and have no input for grey hairs.

    Args:
        material (bpy.types.Material): Material of haircards or of a haircap.
        color_match (ColorMatch): Corrections for this kind of material.
        redness (float): Value of the Redness input of the particle hair.
        grey_hair (float): Value of the Pepper & Salt input of the particle hair.
    """
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    principled = next(
        (node for node in nodes if node.bl_idname == "ShaderNodeBsdfPrincipled"), None
    )
    if not principled or not principled.inputs["Base Color"].links:
        return

    adjust = nodes.get(COLOR_MATCH_NODE_NAME)
    whiten = nodes.get(GREY_HAIR_NODE_NAME)
    if not adjust or not whiten:
        color_socket = principled.inputs["Base Color"].links[0].from_socket
        adjust = nodes.new("ShaderNodeHueSaturation")
        adjust.name = COLOR_MATCH_NODE_NAME
        is_legacy_mix = bpy.app.version < (3, 4, 0)
        whiten = nodes.new("ShaderNodeMixRGB" if is_legacy_mix else "ShaderNodeMix")
        whiten.name = GREY_HAIR_NODE_NAME
        if not is_legacy_mix:
            whiten.data_type = "RGBA"
        whiten.inputs[COLOR2_INPUT_NAME].default_value = (1, 1, 1, 1)
        links.new(color_socket, adjust.inputs["Color"])
        links.new(adjust.outputs[0], whiten.inputs[COLOR1_INPUT_NAME])
        links.new(
            whiten.outputs[0 if is_legacy_mix else 2], principled.inputs["Base Color"]
        )

    adjust.inputs["Value"].default_value = color_match.value
    adjust.inputs["Saturation"].default_value = color_match.saturation(redness)
    whiten.inputs[0].default_value = float(np.clip(grey_hair, 0, 1)) * GREY_HAIR_SHARE
    specular_input = principled.inputs[SPECULAR_INPUT_NAME]
    if color_match.specular is not None and not specular_input.links:
        specular_input.default_value = color_match.specular
    elif color_match.specular is not None:
        dim = nodes.get(SPECULAR_MATCH_NODE_NAME)
        if not dim:
            dim = nodes.new("ShaderNodeMath")
            dim.name = SPECULAR_MATCH_NODE_NAME
            dim.operation = "MULTIPLY"
            links.new(specular_input.links[0].from_socket, dim.inputs[0])
            links.new(dim.outputs[0], specular_input)
        dim.inputs[1].default_value = color_match.specular
    if color_match.roughness is not None:
        principled.inputs["Roughness"].default_value = color_match.roughness


def load_card_material() -> bpy.types.Material:
    """Gets a new material for haircards.

    Returns:
        bpy.types.Material: Material for all cards of one human.
    """
    mat = bpy.data.materials.get("HG_Haircards")
    if mat:
        mat = mat.copy()
        _keep_color_between_hairs(mat)
        return mat

    blendpath = os.path.join(
        get_prefs().filepath, "hair", "haircards", "haircards_material.blend"
    )
    with reuse_images():
        with bpy.data.libraries.load(blendpath, link=False) as (_, data_to):
            data_to.materials = ["HG_Haircards"]

    _keep_color_between_hairs(data_to.materials[0])
    return data_to.materials[0]
