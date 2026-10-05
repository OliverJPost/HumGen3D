# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Numpy version of Blender's armature deformation, and its inverse.

Used to take the pose out of a clothing mesh that was modelled on a posed human.
Supports both linear blending and dual quaternions ("Preserve Volume").
"""

import bpy
import numpy as np


def skin_matrices(rig: bpy.types.Object, bone_names: list[str]) -> np.ndarray:
    """Get the current pose as one deformation matrix per bone.

    Args:
        rig: Armature object.
        bone_names: Names of the bones to get matrices for.

    Returns:
        Array (bones, 4, 4) of matrices in armature space that take a rest
        position to its posed position.
    """
    matrices = np.zeros((len(bone_names), 4, 4))
    for i, name in enumerate(bone_names):
        pose_bone = rig.pose.bones[name]
        rest_inverse = pose_bone.bone.matrix_local.inverted()
        matrices[i] = np.array(pose_bone.matrix @ rest_inverse)
    return matrices


def vertex_transforms(
    weights: np.ndarray, matrices: np.ndarray, dual_quaternion: bool
) -> tuple[np.ndarray, np.ndarray]:
    """Blend the bone matrices into one transform per vertex.

    Args:
        weights: Weight matrix (vertices, bones).
        matrices: Bone matrices from `skin_matrices`.
        dual_quaternion: Blend the way Blender does with Preserve Volume enabled.

    Returns:
        Per vertex a 3x3 matrix and a translation. Vertices without weights get
        the identity, like in Blender.
    """
    total = weights.sum(axis=1, keepdims=True)
    normed = weights / np.maximum(total, 1e-12)
    if dual_quaternion:
        rotation, translation = _blend_dual_quaternions(normed, matrices)
    else:
        blended = np.einsum("vb,bij->vij", normed, matrices)
        rotation, translation = blended[:, :3, :3], blended[:, :3, 3]
    unweighted = total[:, 0] < 1e-8
    rotation[unweighted] = np.eye(3)
    translation[unweighted] = 0.0
    return rotation, translation


def skin(
    co: np.ndarray, weights: np.ndarray, matrices: np.ndarray, dual_quaternion: bool
) -> np.ndarray:
    """Deform rest pose coordinates into the current pose.

    Args:
        co: Rest pose coordinates in armature space.
        weights: Weight matrix (vertices, bones).
        matrices: Bone matrices from `skin_matrices`.
        dual_quaternion: Whether Preserve Volume is enabled.

    Returns:
        Posed coordinates.
    """
    rotation, translation = vertex_transforms(weights, matrices, dual_quaternion)
    return np.einsum("vij,vj->vi", rotation, co) + translation


def unskin(
    co: np.ndarray, weights: np.ndarray, matrices: np.ndarray, dual_quaternion: bool
) -> np.ndarray:
    """Take the current pose out of posed coordinates.

    Args:
        co: Posed coordinates in armature space.
        weights: Weight matrix (vertices, bones).
        matrices: Bone matrices from `skin_matrices`.
        dual_quaternion: Whether Preserve Volume is enabled.

    Returns:
        Rest pose coordinates. Skinning them again with the same weights gives
        back `co`.
    """
    rotation, translation = vertex_transforms(weights, matrices, dual_quaternion)
    return np.einsum("vij,vj->vi", np.linalg.inv(rotation), co - translation)


def _blend_dual_quaternions(
    weights: np.ndarray, matrices: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    real = _quaternions(matrices[:, :3, :3])
    offset = np.concatenate([np.zeros((len(matrices), 1)), matrices[:, :3, 3]], axis=1)
    dual = 0.5 * _multiply(offset, real)
    # Quaternions q and -q are the same rotation, blend on one hemisphere
    pivot = real[np.argmax(weights, axis=1)]
    signed = weights * np.where(pivot @ real.T < 0, -1.0, 1.0)
    blend_real, blend_dual = signed @ real, signed @ dual
    norm = np.maximum(np.linalg.norm(blend_real, axis=1, keepdims=True), 1e-20)
    blend_real, blend_dual = blend_real / norm, blend_dual / norm
    conjugate = blend_real * np.array([1.0, -1.0, -1.0, -1.0])
    translation = 2.0 * _multiply(blend_dual, conjugate)[:, 1:]
    return _rotation_matrices(blend_real), translation


def _quaternions(rotations: np.ndarray) -> np.ndarray:
    quats = np.zeros((len(rotations), 4))
    for i, m in enumerate(rotations):
        trace = m[0, 0] + m[1, 1] + m[2, 2]
        if trace > 0:
            s = np.sqrt(trace + 1.0) * 2
            quats[i] = (
                0.25 * s,
                (m[2, 1] - m[1, 2]) / s,
                (m[0, 2] - m[2, 0]) / s,
                (m[1, 0] - m[0, 1]) / s,
            )
        elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
            s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
            quats[i] = (
                (m[2, 1] - m[1, 2]) / s,
                0.25 * s,
                (m[0, 1] + m[1, 0]) / s,
                (m[0, 2] + m[2, 0]) / s,
            )
        elif m[1, 1] > m[2, 2]:
            s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
            quats[i] = (
                (m[0, 2] - m[2, 0]) / s,
                (m[0, 1] + m[1, 0]) / s,
                0.25 * s,
                (m[1, 2] + m[2, 1]) / s,
            )
        else:
            s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
            quats[i] = (
                (m[1, 0] - m[0, 1]) / s,
                (m[0, 2] + m[2, 0]) / s,
                (m[1, 2] + m[2, 1]) / s,
                0.25 * s,
            )
    return quats


def _multiply(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    aw, ax, ay, az = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    bw, bx, by, bz = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack(
        [
            aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
        ],
        axis=-1,
    )


def _rotation_matrices(quats: np.ndarray) -> np.ndarray:
    w, x, y, z = quats[:, 0], quats[:, 1], quats[:, 2], quats[:, 3]
    rows = [
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ]
    return np.stack([np.stack(row, axis=-1) for row in rows], axis=1)
