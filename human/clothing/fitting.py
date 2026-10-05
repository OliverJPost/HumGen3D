# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Geometry for moving a clothing mesh from one body shape to another.

Everything in here works on plain numpy arrays. Both body shapes share the same
topology and are expected in the rest pose, standing upright along +Z.
"""

from typing import Optional

import numpy as np
from HumGen3D.common.surface import (
    closest_points,
    edges_from_tris,
    interp,
    make_bvh,
    normalized,
    smooth_field,
    vert_normals,
)
from HumGen3D.human.clothing.weights import weld
from mathutils.bvhtree import BVHTree


class BodyBinding:
    """Clothing mesh bound to the closest points on a body surface.

    Attributes:
        face: Body triangle index per garment vertex.
        bary: Barycentric coordinates inside that triangle.
        pos: The closest point itself.
        dist: Distance to it.
        gap: Signed distance along the body normal, negative when inside.
        reliable: False where the closest point is far away or faces another
            way. Those vertices follow their neighbours instead of the body.
    """

    def __init__(
        self,
        g_co: np.ndarray,
        g_tris: np.ndarray,
        b_co: np.ndarray,
        b_tris: np.ndarray,
        bvh: Optional[BVHTree] = None,
        dist_thresh: float = 0.05,
        angle_deg: float = 50.0,
    ) -> None:
        self.b_tris = b_tris
        self.pos, self.face, self.bary, self.dist = closest_points(
            g_co, b_co, b_tris, bvh
        )
        normal = normalized(self.interp(vert_normals(b_co, b_tris)))
        self.gap = np.einsum("ij,ij->i", g_co - self.pos, normal)
        dots = np.einsum("ij,ij->i", vert_normals(g_co, g_tris), normal)
        if np.median(dots) < 0:
            dots = -dots
        self.reliable = (self.dist < dist_thresh) & (
            dots > np.cos(np.radians(angle_deg))
        )
        welded_co, welded_tris, self.welded_index = weld(g_co, g_tris)
        self.welded_count = len(welded_co)
        self.welded_edges = edges_from_tris(welded_tris)

    def interp(self, body_values: np.ndarray) -> np.ndarray:
        """Per body vertex values at the points the garment is bound to.

        Args:
            body_values: Array with one row per body vertex.

        Returns:
            Array with one row per garment vertex.
        """
        return interp(body_values, self.b_tris, self.face, self.bary)

    def to_welded(self, values: np.ndarray) -> np.ndarray:
        """Average garment vertex values per group of merged vertices.

        Args:
            values: Array with one row per garment vertex.

        Returns:
            Array with one row per welded vertex.
        """
        total = np.zeros((self.welded_count,) + values.shape[1:])
        np.add.at(total, self.welded_index, values)
        members = np.bincount(self.welded_index, minlength=self.welded_count)
        return total / members.reshape((-1,) + (1,) * (values.ndim - 1))


def vertex_covariance(
    body_a: np.ndarray, body_b: np.ndarray, edges: np.ndarray, smooth: int = 2
) -> np.ndarray:
    """Describe how the surroundings of each body vertex turn from shape A to B.

    Args:
        body_a: Body coordinates of the shape the garment currently fits.
        body_b: Body coordinates of the shape it should fit.
        edges: Body edges.
        smooth: Smoothing passes over the result.

    Returns:
        Array (vertices, 3, 3). The rotation is its polar decomposition, which
        is taken after interpolating to the garment, see `fit_shape`.
    """
    edge_a = body_a[edges[:, 1]] - body_a[edges[:, 0]]
    edge_b = body_b[edges[:, 1]] - body_b[edges[:, 0]]
    outer = np.einsum("ei,ej->eij", edge_b, edge_a).reshape(-1, 9)
    covariance = np.empty((len(body_a), 9))
    for column in range(9):
        # Every edge counts for both of its vertices
        covariance[:, column] = np.bincount(
            edges.ravel(), weights=np.repeat(outer[:, column], 2), minlength=len(body_a)
        )
    return smooth_field(covariance.reshape(-1, 3, 3), edges, smooth)


def _rotations(covariance: np.ndarray) -> np.ndarray:
    u, _, vt = np.linalg.svd(covariance)
    flipped = np.linalg.det(u @ vt) < 0
    u[flipped, :, 2] *= -1.0
    return u @ vt


def fit_shape(
    g_co: np.ndarray,
    bind: BodyBinding,
    body_a: np.ndarray,
    body_b: np.ndarray,
    covariance: np.ndarray,
    loose_field: Optional[np.ndarray] = None,
    looseness: Optional[np.ndarray] = None,
    envelope_b: Optional[np.ndarray] = None,
    iron_mask: Optional[np.ndarray] = None,
    iron_weight: Optional[np.ndarray] = None,
    min_gap: float = 0.002,
    smooth: int = 3,
    keep_outside: bool = True,
) -> np.ndarray:
    """Move a garment that fits body shape A so it fits body shape B.

    Args:
        g_co: Garment coordinates on shape A.
        bind: Binding of the garment to shape A.
        body_a: Body coordinates of shape A.
        body_b: Body coordinates of shape B.
        covariance: Result of `vertex_covariance` for A and B.
        loose_field: Per body vertex the displacement loose cloth follows
            instead of the exact body displacement, see `loose_displacement`.
        looseness: Per garment vertex, 0 follows the body exactly and 1 follows
            `loose_field`. All loose when not passed.
        envelope_b: Drape envelope of shape B, needed for ironing.
        iron_mask: Per body vertex strength with which cloth is pushed out to
            `envelope_b`, even if it was modelled inside of it.
        iron_weight: Optional per garment vertex factor for the ironing.
        min_gap: Smallest distance to the skin that is restored.
        smooth: Smoothing passes over the garment displacement.
        keep_outside: Keep each vertex on the outside of the body point it is
            bound to.

    Returns:
        Garment coordinates on shape B.
    """
    offset = g_co - bind.pos
    rotated = np.einsum("vij,vj->vi", _rotations(bind.interp(covariance)), offset)
    follow = bind.interp(body_b - body_a)
    if loose_field is not None:
        loose = bind.interp(loose_field)
        blend = 1.0 if looseness is None else looseness[:, None]
        follow = follow * (1 - blend) + loose * blend
    displacement = bind.to_welded(follow + rotated - offset)

    # Vertices without a trustworthy binding take their movement from the rest
    reliable = bind.to_welded(bind.reliable.astype(np.float64)) > 0
    if reliable.any() and not reliable.all():
        displacement = _fill_in(displacement, reliable, bind.welded_edges)
    if smooth:
        displacement = smooth_field(displacement, bind.welded_edges, smooth)
    fitted = g_co + displacement[bind.welded_index]

    normal_b = normalized(bind.interp(vert_normals(body_b, bind.b_tris)))
    pos_b = bind.interp(body_b)
    wanted_gap = np.clip(bind.gap, min_gap, 0.02)

    if envelope_b is not None and iron_mask is not None:
        pos_env = bind.interp(envelope_b)
        direction = pos_env - pos_b
        length = np.linalg.norm(direction, axis=1)
        pushed = length > 1e-3
        direction = np.where(
            pushed[:, None], direction / np.maximum(length, 1e-9)[:, None], normal_b
        )
        short = wanted_gap - np.einsum("ij,ij->i", fitted - pos_env, direction)
        short = np.maximum(short, 0.0) * bind.interp(iron_mask[:, None])[:, 0]
        short = np.where(bind.reliable & pushed, short, 0.0)
        if iron_weight is not None:
            short = short * iron_weight
        push = bind.to_welded(direction * short[:, None])
        push = smooth_field(push, bind.welded_edges, 4)
        fitted = fitted + push[bind.welded_index]

    if keep_outside:
        gap = np.einsum("ij,ij->i", fitted - pos_b, normal_b)
        short = np.where(bind.reliable, np.maximum(wanted_gap - gap, 0.0), 0.0)
        fitted = fitted + normal_b * short[:, None]
    return fitted


def _fill_in(
    displacement: np.ndarray, reliable: np.ndarray, edges: np.ndarray
) -> np.ndarray:
    filled = np.where(reliable[:, None], displacement, 0.0)
    known = reliable.astype(np.float64)[:, None]
    for _ in range(60):  # grow outwards from the reliable area
        if known.min() > 0:
            break
        total = smooth_field(filled * known, edges, 1)
        weight = smooth_field(known, edges, 1)
        new = (known[:, 0] == 0) & (weight[:, 0] > 0)
        filled[new] = total[new] / weight[new]
        known[new] = 1.0
    return smooth_field(filled, edges, 40, keep=reliable)


def resolve_collisions(
    g_co: np.ndarray,
    b_co: np.ndarray,
    b_tris: np.ndarray,
    bvh: Optional[BVHTree] = None,
    b_normals: Optional[np.ndarray] = None,
    min_gap: float = 0.002,
    iterations: int = 2,
) -> np.ndarray:
    """Push garment vertices that ended up inside the body back out.

    Unlike the check inside `fit_shape` this looks at the whole body, so it also
    catches an arm that grew into a sleeve bound to the torso.

    Args:
        g_co: Garment coordinates.
        b_co: Body coordinates.
        b_tris: Body triangles.
        bvh: Optional prebuilt BVH tree of the body.
        b_normals: Optional precomputed body vertex normals.
        min_gap: Distance from the skin vertices are moved to.
        iterations: Number of passes.

    Returns:
        Corrected garment coordinates.
    """
    bvh = bvh or make_bvh(b_co, b_tris)
    normals = vert_normals(b_co, b_tris) if b_normals is None else b_normals
    fixed = g_co.copy()
    for _ in range(iterations):
        pos, face, bary, dist = closest_points(fixed, b_co, b_tris, bvh)
        normal = normalized(interp(normals, b_tris, face, bary))
        signed = np.einsum("ij,ij->i", fixed - pos, normal)
        inside = (signed < min_gap) & (dist < 0.05)
        if not inside.any():
            break
        fixed[inside] = pos[inside] + normal[inside] * min_gap
    return fixed


def drape_envelope(
    co: np.ndarray,
    mask: np.ndarray,
    slope: float = 0.6,
    n_theta: int = 96,
    dz: float = 0.01,
    max_push: float = 0.2,
) -> np.ndarray:
    """Fill the hollows of a body the way hanging cloth bridges them.

    Per horizontal slice the body is replaced by its convex hull, since cloth
    under tension spans hollows like the spine or between the breasts. Above the
    widest point cloth runs straight from the shoulders to the protrusion.
    Scanning down from there the hull may only shrink by `slope` per unit of
    height, so cloth hangs from a belly or bust instead of tucking in under it.

    Args:
        co: Body coordinates in the rest pose, upright along +Z.
        mask: Vertices that carry cloth this way: the torso, plus the legs for
            skirts and dresses. Only these are moved.
        slope: How fast cloth returns to the body below a protrusion. Around
            0.1 gives a boxy fit, 0.6 a regular one.
        n_theta: Angular resolution.
        dz: Slice height.
        max_push: Largest distance a vertex is moved.

    Returns:
        Copy of `co` with the masked vertices pushed out to the envelope.
    """
    points = co[mask]
    z_min, z_max = points[:, 2].min(), points[:, 2].max()
    axis = np.array([0.0, np.median(points[:, 1])])
    n_z = int(np.ceil((z_max - z_min) / dz)) + 1
    theta = np.linspace(-np.pi, np.pi, n_theta, endpoint=False)
    rays = np.stack([np.cos(theta), np.sin(theta)], axis=1)
    radius = np.zeros((n_z, n_theta))
    level = np.clip(((points[:, 2] - z_min) / dz).round().astype(int), 0, n_z - 1)
    for k in range(n_z):
        radius[k] = _hull_radius(points[np.abs(level - k) <= 1][:, :2] - axis, rays)

    for j in range(n_theta):
        widest = int(np.argmax(radius[:, j]))
        if widest < n_z - 2:
            radius[widest:, j] = _concave_majorant(radius[widest:, j])
    for k in range(n_z - 2, -1, -1):
        radius[k] = np.maximum(radius[k], radius[k + 1] - slope * dz)

    index = np.where(mask)[0]
    planar = co[index, :2] - axis
    distance = np.linalg.norm(planar, axis=1)
    angle = np.arctan2(planar[:, 1], planar[:, 0])
    f_z = np.clip((co[index, 2] - z_min) / dz, 0, n_z - 1.001)
    f_t = ((angle + np.pi) / (2 * np.pi) * n_theta) % n_theta
    z0, t0 = f_z.astype(int), f_t.astype(int) % n_theta
    w_z, w_t = f_z - z0, f_t - np.floor(f_t)
    t1 = (t0 + 1) % n_theta
    envelope = (1 - w_z) * ((1 - w_t) * radius[z0, t0] + w_t * radius[z0, t1]) + w_z * (
        (1 - w_t) * radius[z0 + 1, t0] + w_t * radius[z0 + 1, t1]
    )
    push = np.clip(envelope - distance, 0.0, max_push)
    # Right next to the axis (crotch) the outward direction means nothing
    push = np.where(distance > 0.03, push, 0.0)
    result = co.copy()
    result[index, :2] += planar / np.maximum(distance, 1e-9)[:, None] * push[:, None]
    return result


def loose_displacement(
    envelope_a: np.ndarray,
    envelope_b: np.ndarray,
    edges: np.ndarray,
    smooth: int = 20,
) -> np.ndarray:
    """Displacement field that loose cloth follows from body shape A to B.

    It is the change of the drape envelope, smoothed so cloth does not pick up
    small body detail like muscle definition. Following the change rather than
    the envelope itself keeps a garment the way it was designed on shape A.

    Args:
        envelope_a: Drape envelope of shape A.
        envelope_b: Drape envelope of shape B.
        edges: Body edges.
        smooth: Smoothing passes.

    Returns:
        Displacement per body vertex.
    """
    return smooth_field(envelope_b - envelope_a, edges, smooth)


def _hull_radius(points: np.ndarray, rays: np.ndarray) -> np.ndarray:
    """Distance from the origin to the convex hull of 2D points along rays."""
    if len(points) < 3:
        return np.zeros(len(rays))
    hull = _convex_hull(points)
    if len(hull) < 3:
        return np.zeros(len(rays))
    edge = np.roll(hull, -1, axis=0) - hull
    normal = normalized(np.stack([edge[:, 1], -edge[:, 0]], axis=1))
    distance = np.einsum("ij,ij->i", normal, hull)
    if (distance < 0).any():  # origin outside of the hull
        return np.zeros(len(rays))
    facing = rays @ normal.T
    hit = np.where(
        facing > 1e-6, distance[None, :] / np.where(facing > 1e-6, facing, 1.0), np.inf
    )
    return hit.min(axis=1)


def _convex_hull(points: np.ndarray) -> np.ndarray:
    points = points[np.lexsort((points[:, 1], points[:, 0]))]

    def half(ordered: np.ndarray) -> list[np.ndarray]:
        chain: list[np.ndarray] = []
        for p in ordered:
            while len(chain) >= 2 and _turn(chain[-2], chain[-1], p) <= 0:
                chain.pop()
            chain.append(p)
        return chain

    lower, upper = half(points), half(points[::-1])
    return np.array(lower[:-1] + upper[:-1])


def _turn(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    return float((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def _concave_majorant(values: np.ndarray) -> np.ndarray:
    """Smallest concave curve that lies on or above regularly spaced values."""
    chain: list[int] = []
    for i in range(len(values)):
        while len(chain) >= 2 and (chain[-1] - chain[-2]) * (
            values[i] - values[chain[-2]]
        ) - (values[chain[-1]] - values[chain[-2]]) * (i - chain[-2]) >= 0:
            chain.pop()
        chain.append(i)
    return np.interp(np.arange(len(values)), chain, values[chain])
