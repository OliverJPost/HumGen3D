# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Minimal sparse linear algebra on top of numpy (Blender ships without scipy)."""

from typing import Callable

import numpy as np


class Sparse:
    """Square sparse matrix stored as row-sorted coordinates."""

    def __init__(
        self, rows: np.ndarray, cols: np.ndarray, vals: np.ndarray, n: int
    ) -> None:
        key = rows.astype(np.int64) * n + cols.astype(np.int64)
        order = np.argsort(key, kind="stable")
        key, vals = key[order], vals[order]
        uniq, start = np.unique(key, return_index=True)
        self.n = n
        self.rows = (uniq // n).astype(np.int64)
        self.cols = (uniq % n).astype(np.int64)
        self.vals = np.add.reduceat(vals, start)
        counts = np.bincount(self.rows, minlength=n)
        if counts.min() == 0:
            raise ValueError("Every row needs at least one entry")
        self._ptr = np.concatenate(([0], np.cumsum(counts)[:-1]))

    def dot(self, x: np.ndarray) -> np.ndarray:
        if x.ndim == 1:
            return np.add.reduceat(self.vals * x[self.cols], self._ptr)
        return np.add.reduceat(self.vals[:, None] * x[self.cols], self._ptr, axis=0)

    def diagonal(self) -> np.ndarray:
        diag = np.zeros(self.n)
        on_diag = self.rows == self.cols
        diag[self.rows[on_diag]] = self.vals[on_diag]
        return diag


def cot_laplacian(co: np.ndarray, tris: np.ndarray) -> tuple[Sparse, np.ndarray]:
    """Cotangent Laplacian (negative semi-definite) and lumped vertex mass.

    The mass is scaled to a mean of 1 so results do not depend on mesh size.
    """
    n = len(co)
    rows, cols, vals = [], [], []
    area = np.zeros(n)
    a, b, c = co[tris[:, 0]], co[tris[:, 1]], co[tris[:, 2]]
    double_area = np.linalg.norm(np.cross(b - a, c - a), axis=1)
    valid = double_area > 1e-14
    for k in range(3):
        i, j, opp = tris[:, k], tris[:, (k + 1) % 3], tris[:, (k + 2) % 3]
        u, v = co[i] - co[opp], co[j] - co[opp]
        cot = np.einsum("ij,ij->i", u, v) / np.maximum(double_area, 1e-14)
        weight = np.where(valid, np.clip(0.5 * cot, 1e-5, 1e3), 0.0)
        rows += [i, j]
        cols += [j, i]
        vals += [weight, weight]
        area += np.bincount(i, weights=double_area / 6.0, minlength=n)
    row, col, val = np.concatenate(rows), np.concatenate(cols), np.concatenate(vals)
    diag = np.bincount(row, weights=val, minlength=n)
    laplacian = Sparse(
        np.concatenate([row, np.arange(n)]),
        np.concatenate([col, np.arange(n)]),
        np.concatenate([val, -diag - 1e-12]),
        n,
    )
    area = np.maximum(area, 1e-12)
    return laplacian, area / area.mean()


def block_cg(
    apply_a: Callable[[np.ndarray], np.ndarray],
    b: np.ndarray,
    diag: np.ndarray,
    tol: float = 1e-5,
    maxiter: int = 1500,
) -> tuple[np.ndarray, int, bool, float]:
    """Jacobi-preconditioned conjugate gradient for several right-hand sides.

    Returns the solution, the iteration count, whether every column reached
    `tol` and the worst relative residual.
    """
    x = np.zeros_like(b)
    r = b.copy()
    z = r / diag[:, None]
    p = z.copy()
    rz = np.einsum("ij,ij->j", r, z)
    b_norm = np.maximum(np.linalg.norm(b, axis=0), 1e-30)
    iteration, residual = 0, float("inf")
    for iteration in range(maxiter):
        a_p = apply_a(p)
        p_ap = np.einsum("ij,ij->j", p, a_p)
        alpha = rz / np.where(np.abs(p_ap) > 1e-300, p_ap, 1.0)
        x += p * alpha
        r -= a_p * alpha
        residual = float((np.linalg.norm(r, axis=0) / b_norm).max())
        if not np.isfinite(residual) or residual < tol:
            break
        z = r / diag[:, None]
        rz_new = np.einsum("ij,ij->j", r, z)
        beta = rz_new / np.where(np.abs(rz) > 1e-300, rz, 1.0)
        p = z + p * beta
        rz = rz_new
    converged = bool(np.isfinite(residual) and residual < tol)
    return x, iteration + 1, converged, residual
