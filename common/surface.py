# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Numpy helpers for triangle meshes: normals, closest points, smoothing."""

from typing import Optional

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def normalized(vectors: np.ndarray) -> np.ndarray:
    length = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(length, 1e-20)


def vert_normals(co: np.ndarray, tris: np.ndarray) -> np.ndarray:
    """Area-weighted vertex normals."""
    face = np.cross(co[tris[:, 1]] - co[tris[:, 0]], co[tris[:, 2]] - co[tris[:, 0]])
    normals = np.zeros_like(co)
    for corner in range(3):
        for axis in range(3):
            normals[:, axis] += np.bincount(
                tris[:, corner], weights=face[:, axis], minlength=len(co)
            )
    return normalized(normals)


def edges_from_tris(tris: np.ndarray) -> np.ndarray:
    edges = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    return np.unique(np.sort(edges, axis=1), axis=0)


def make_bvh(co: np.ndarray, tris: np.ndarray) -> BVHTree:
    return BVHTree.FromPolygons(co.tolist(), tris.tolist())


def closest_points(
    points: np.ndarray,
    co: np.ndarray,
    tris: np.ndarray,
    bvh: Optional[BVHTree] = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Closest point on a triangle mesh for every query point.

    Returns position, triangle index, barycentric coordinates and distance.
    """
    bvh = bvh or make_bvh(co, tris)
    count = len(points)
    pos = np.zeros((count, 3))
    face = np.zeros(count, dtype=np.int64)
    dist = np.zeros(count)
    for i in range(count):
        location, _, index, distance = bvh.find_nearest(Vector(points[i]))
        pos[i] = location
        face[i] = index
        dist[i] = distance
    tri = tris[face]
    a, b, c = co[tri[:, 0]], co[tri[:, 1]], co[tri[:, 2]]
    v0, v1, v2 = b - a, c - a, pos - a
    d00 = np.einsum("ij,ij->i", v0, v0)
    d01 = np.einsum("ij,ij->i", v0, v1)
    d11 = np.einsum("ij,ij->i", v1, v1)
    d20 = np.einsum("ij,ij->i", v2, v0)
    d21 = np.einsum("ij,ij->i", v2, v1)
    det = d00 * d11 - d01 * d01
    det = np.where(np.abs(det) < 1e-20, 1.0, det)
    v = (d11 * d20 - d01 * d21) / det
    w = (d00 * d21 - d01 * d20) / det
    bary = np.clip(np.stack([1 - v - w, v, w], axis=1), 0, 1)
    bary /= bary.sum(axis=1, keepdims=True)
    return pos, face, bary, dist


def interp(
    values: np.ndarray, tris: np.ndarray, face: np.ndarray, bary: np.ndarray
) -> np.ndarray:
    """Barycentric interpolation of per-vertex values at surface points."""
    tri = tris[face]
    weight = bary.reshape(bary.shape + (1,) * (values.ndim - 2))
    return (
        values[tri[:, 0]] * weight[:, 0:1]
        + values[tri[:, 1]] * weight[:, 1:2]
        + values[tri[:, 2]] * weight[:, 2:3]
    )


def neighbour_sum(flat: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Sum of a per-vertex field (n, k) over each vertex' edge neighbours."""
    count = len(flat)
    total = np.empty_like(flat)
    for column in range(flat.shape[1]):
        total[:, column] = np.bincount(
            edges[:, 0], weights=flat[edges[:, 1], column], minlength=count
        ) + np.bincount(
            edges[:, 1], weights=flat[edges[:, 0], column], minlength=count
        )
    return total


def smooth_field(
    field: np.ndarray,
    edges: np.ndarray,
    iterations: int,
    keep: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Laplacian smoothing of a per-vertex field over the mesh.

    Rows flagged in `keep` stay fixed and act as boundary values.
    """
    count = len(field)
    flat = field.reshape(count, -1).astype(np.float64)
    degree = np.bincount(edges.ravel(), minlength=count).astype(np.float64)
    degree = np.maximum(degree, 1.0)[:, None]
    for _ in range(iterations):
        new = 0.5 * flat + 0.5 * neighbour_sum(flat, edges) / degree
        if keep is not None:
            new[keep] = flat[keep]
        flat = new
    return flat.reshape(field.shape)


def components(count: int, tris: np.ndarray) -> np.ndarray:
    """Connected component index for each of `count` vertices."""
    label = np.arange(count)
    edges = edges_from_tris(tris)
    for _ in range(count):
        low = np.minimum(label[edges[:, 0]], label[edges[:, 1]])
        new = label.copy()
        np.minimum.at(new, edges[:, 0], low)
        np.minimum.at(new, edges[:, 1], low)
        new = new[new]
        if np.array_equal(new, label):
            break
        label = new
    return np.unique(label, return_inverse=True)[1].reshape(-1)
