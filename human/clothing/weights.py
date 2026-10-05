# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Transfer of skin weights from the body to a clothing mesh.

Weights are copied from the closest point on the body surface, but only where
that match can be trusted. Everywhere else (skirt panels between the legs,
armpits, loose hems) they are filled in by minimising a smoothness energy over
the garment, following Abdrashitov et al. 2023, "Robust Skin Weights Transfer
via Weight Inpainting".
"""

from typing import Any, Optional

import numpy as np
from HumGen3D.common.sparse import Sparse, block_cg, cot_laplacian
from HumGen3D.common.surface import (
    closest_points,
    components,
    edges_from_tris,
    interp,
    normalized,
    smooth_field,
    vert_normals,
)
from mathutils import kdtree
from mathutils.bvhtree import BVHTree

SEAM_TOLERANCE = 1e-5
MAX_WELD_TOLERANCE = 5e-4


def weld_tolerance(co: np.ndarray, tris: np.ndarray) -> float:
    """Length below which an edge is collapsed for solving.

    Args:
        co: Vertex coordinates.
        tris: Triangle vertex indices.

    Returns:
        0.5 mm, but never more than 5% of the median edge length.
    """
    edges = edges_from_tris(tris)
    lengths = np.linalg.norm(co[edges[:, 0]] - co[edges[:, 1]], axis=1)
    return min(MAX_WELD_TOLERANCE, 0.05 * float(np.median(lengths)))


def weld(
    co: np.ndarray, tris: np.ndarray, tol: Optional[float] = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Merge near-duplicate vertices on a working copy of the mesh.

    Only two kinds of vertices are merged: vertices at the same position (split
    seams, UV islands) and the two ends of a mesh edge shorter than `tol`.
    Vertices that are close but not connected (a pocket lying on a shirt, a
    lining) are left alone, and a merged group never grows wider than twice the
    tolerance, so a row of tiny edges cannot collapse into one point.

    Args:
        co: Vertex coordinates.
        tris: Triangle vertex indices.
        tol: Edge length below which the two ends are merged. Derived from the
            mesh when not passed.

    Returns:
        Welded coordinates, welded triangles without the degenerate ones, and
        the map from original to welded vertex index.
    """
    tol = weld_tolerance(co, tris) if tol is None else tol
    count = len(co)
    parent = list(range(count))
    low, high = co.copy(), co.copy()

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int, limit: float) -> None:
        root_i, root_j = find(i), find(j)
        if root_i == root_j:
            return
        new_low = np.minimum(low[root_i], low[root_j])
        new_high = np.maximum(high[root_i], high[root_j])
        if np.linalg.norm(new_high - new_low) > limit:
            return
        parent[root_j] = root_i
        low[root_i], high[root_i] = new_low, new_high

    tree = kdtree.KDTree(count)
    for i in range(count):
        tree.insert(co[i], i)
    tree.balance()
    for i in range(count):
        for _, j, _ in tree.find_range(co[i], SEAM_TOLERANCE):
            if j > i:
                union(i, j, 2 * SEAM_TOLERANCE)

    edges = edges_from_tris(tris)
    lengths = np.linalg.norm(co[edges[:, 0]] - co[edges[:, 1]], axis=1)
    short = np.where(lengths < tol)[0]
    for k in short[np.argsort(lengths[short])]:
        union(int(edges[k, 0]), int(edges[k, 1]), 2 * tol)

    roots = np.array([find(i) for i in range(count)])
    welded_index = np.unique(roots, return_inverse=True)[1].reshape(-1)
    welded_count = int(welded_index.max()) + 1
    welded_co = np.zeros((welded_count, 3))
    np.add.at(welded_co, welded_index, co)
    welded_co /= np.bincount(welded_index, minlength=welded_count)[:, None]
    welded_tris = welded_index[tris]
    proper = (
        (welded_tris[:, 0] != welded_tris[:, 1])
        & (welded_tris[:, 1] != welded_tris[:, 2])
        & (welded_tris[:, 2] != welded_tris[:, 0])
    )
    return welded_co, welded_tris[proper], welded_index


def limit_influences(
    weights: np.ndarray, max_influences: int = 4, prune: float = 1e-3
) -> np.ndarray:
    """Keep only the strongest bone influences per vertex and renormalise.

    Args:
        weights: Weight matrix (vertices, bones).
        max_influences: Number of bones a vertex may be weighted to.
        prune: Weights below this are dropped first.

    Returns:
        New weight matrix with rows summing to 1.
    """
    weights = np.where(weights < prune, 0.0, weights)
    if weights.shape[1] > max_influences:
        drop = np.argpartition(-weights, max_influences - 1, axis=1)
        np.put_along_axis(weights, drop[:, max_influences:], 0.0, axis=1)
    return weights / np.maximum(weights.sum(axis=1, keepdims=True), 1e-12)


def transfer_weights(
    g_co: np.ndarray,
    g_tris: np.ndarray,
    b_co: np.ndarray,
    b_tris: np.ndarray,
    b_weights: np.ndarray,
    bvh: Optional[BVHTree] = None,
    dist_thresh: float = 0.04,
    angle_deg: float = 35.0,
    smooth_iters: int = 2,
    maxiter: int = 1500,
    draft: bool = False,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Transfer skin weights from the body to a garment.

    Both meshes have to be in the same space: same body shape, same pose.

    Args:
        g_co: Garment vertex coordinates.
        g_tris: Garment triangles.
        b_co: Body vertex coordinates.
        b_tris: Body triangles.
        b_weights: Body weight matrix (vertices, bones), rows summing to 1.
        bvh: Optional prebuilt BVH tree of the body.
        dist_thresh: A closest-point match further away than this is not trusted.
        angle_deg: Neither is one whose surface normal differs more than this.
        smooth_iters: Smoothing passes over the filled-in area.
        maxiter: Iteration cap of the solver.
        draft: Go straight to the faster, slightly less smooth "harmonic"
            solve. For intermediate results that get recomputed anyway.

    Returns:
        The garment weight matrix (vertices, bones) with rows summing to 1, and
        a dict with `solver` ("none", "bilaplacian", "harmonic" or
        "closest_point"), `iterations`, `residual` and `matched` (fraction of
        vertices with a trusted match). "closest_point" means the solve failed
        and the weights are of lower quality.
    """
    _, face, bary, dist = closest_points(g_co, b_co, b_tris, bvh)
    closest = interp(b_weights, b_tris, face, bary)
    closest /= np.maximum(closest.sum(axis=1, keepdims=True), 1e-12)

    body_normals = normalized(interp(vert_normals(b_co, b_tris), b_tris, face, bary))
    dots = np.einsum("ij,ij->i", vert_normals(g_co, g_tris), body_normals)
    if np.median(dots) < 0:  # garment modelled with flipped normals
        dots = -dots
    matched = (dist < dist_thresh) & (dots > np.cos(np.radians(angle_deg)))

    # Solve on a welded copy so split seams and tiny edges do not hurt
    w_co, w_tris, w_index = weld(g_co, g_tris)
    count = len(w_co)
    members = np.bincount(w_index, minlength=count).astype(np.float64)
    weights = np.zeros((count, b_weights.shape[1]))
    np.add.at(weights, w_index, closest * matched[:, None])
    trusted = np.bincount(w_index, weights=matched.astype(np.float64), minlength=count)
    known = trusted > 0
    weights[known] /= trusted[known, None]

    all_closest = np.zeros_like(weights)
    np.add.at(all_closest, w_index, closest)
    all_closest /= members[:, None]

    # Parts without a single trusted vertex cannot be filled in from anywhere
    part = components(count, w_tris)
    part_known = np.bincount(part, weights=known.astype(np.float64)) > 0
    orphan = ~part_known[part]
    in_triangle = np.zeros(count, dtype=bool)
    in_triangle[w_tris.ravel()] = True
    orphan |= ~in_triangle
    weights[orphan] = all_closest[orphan]
    known |= orphan

    info: dict[str, Any] = {
        "solver": "none",
        "iterations": 0,
        "residual": 0.0,
        "matched": float(matched.mean()),
    }
    if not known.all():
        weights = _inpaint(
            weights,
            known,
            all_closest,
            w_co,
            w_tris,
            smooth_iters,
            maxiter,
            draft,
            info,
        )
    return weights[w_index], info


def _sane(solution: np.ndarray) -> bool:
    return bool(
        np.isfinite(solution).all() and solution.min() > -0.25 and solution.max() < 1.25
    )


def _inpaint(
    weights: np.ndarray,
    known: np.ndarray,
    all_closest: np.ndarray,
    co: np.ndarray,
    tris: np.ndarray,
    smooth_iters: int,
    maxiter: int,
    draft: bool,
    info: dict[str, Any],
) -> np.ndarray:
    count = len(co)
    laplacian, mass = cot_laplacian(co, tris)
    mass_inv = 1.0 / mass
    unknown = np.where(~known)[0]
    bones = np.where(weights[known].max(axis=0) > 1e-4)[0]

    def energy(x: np.ndarray) -> np.ndarray:
        lx = laplacian.dot(x)
        return -lx + laplacian.dot(lx * mass_inv[:, None])

    def expand(x_unknown: np.ndarray) -> np.ndarray:
        full = np.zeros((count, x_unknown.shape[1]))
        full[unknown] = x_unknown
        return full

    fixed = np.zeros((count, len(bones)))
    fixed[known] = weights[np.ix_(known, bones)]

    diag = -laplacian.diagonal() + np.bincount(
        laplacian.rows,
        weights=laplacian.vals**2 * mass_inv[laplacian.cols],
        minlength=count,
    )
    solver, iterations, converged = "bilaplacian", 0, False
    if not draft:
        solution, iterations, converged, residual = block_cg(
            lambda x: energy(expand(x))[unknown],
            -energy(fixed)[unknown],
            diag[unknown],
            maxiter=maxiter,
        )
        converged = converged and _sane(solution)
    if not converged:
        # First-order smoothness is far better conditioned
        solution, extra, converged, residual = block_cg(
            lambda x: -laplacian.dot(expand(x))[unknown],
            laplacian.dot(fixed)[unknown],
            -laplacian.diagonal()[unknown],
            maxiter=maxiter,
        )
        iterations += extra
        solver = "harmonic"
    if not (converged and _sane(solution)):
        solution = all_closest[np.ix_(unknown, bones)]
        solver = "closest_point"
        smooth_iters = max(smooth_iters, 10)
    info.update(solver=solver, iterations=iterations, residual=residual)

    weights[np.ix_(unknown, bones)] = solution
    weights = np.clip(weights, 0, 1)
    weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-12)

    if smooth_iters:
        # Relax the filled-in area together with the ring around it
        edges = edges_from_tris(tris)
        adjacency = Sparse(
            np.concatenate([edges[:, 0], edges[:, 1], np.arange(count)]),
            np.concatenate([edges[:, 1], edges[:, 0], np.arange(count)]),
            np.concatenate([np.ones(2 * len(edges)), np.zeros(count)]),
            count,
        )
        region = (adjacency.dot((~known).astype(np.float64)) > 0) | ~known
        smoothed = smooth_field(weights, edges, smooth_iters, keep=~region)
        weights = smoothed / np.maximum(smoothed.sum(axis=1, keepdims=True), 1e-12)
    return weights
