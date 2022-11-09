# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Contains functions encapsulating commonly used math operations."""

from typing import Any, Iterable, Union, cast

import numpy as np
from mathutils import Vector, kdtree  # type:ignore

TuplePoint = tuple[float, float, float]


def round_vector_to_tuple(vec: Vector, precision: int = 2) -> TuplePoint:
    """Converts a Blender vector to a tuple of floats with a given precision.

    Args:
        vec (Vector): The vector to convert.
        precision (int, optional): The number of decimals to round to. Defaults to 2.

    Returns:
        TuplePoint: The vector as a tuple of floats.
    """
    # Add 0 for accounting for negative 0's
    return cast(
        tuple[float, float, float], tuple(round(co, precision) + 0 for co in vec)
    )


Coordinates = Union[Iterable[tuple[float, float, float]], np.ndarray[Any, Any]]


def centroid(coordinates: Coordinates) -> Vector:
    """Calculate the centroid of a set of coordinates.

    Args:
        coordinates (Coordinates): Set of coordinates as list or numpy array.


    Returns:
        Vector: Vector coordinate of centroid
    """
    x = [c[0] for c in coordinates]
    y = [c[1] for c in coordinates]
    z = [c[2] for c in coordinates]

    mx = sum(x) / len(x)
    my = sum(y) / len(y)
    mz = sum(z) / len(z)

    return Vector((mx, my, mz))


def create_kdtree(coordinates: Coordinates) -> kdtree:
    """Create a new mathutils kdtree from a set of coordinates:

    Args:
        coordinates (Coordinates): Set of coordinates as list or numpy array.

    Returns:
        kdtree: The kdtree, already balanced
    """
    size = len(coordinates)  # type:ignore[arg-type]
    kd = kdtree.KDTree(size)  # type:ignore
    for i, v in enumerate(coordinates):
        kd.insert(v, i)
    kd.balance()
    return kd


def normalize(
    vector_array: np.ndarray[Any, Any], axis: int = -1, order: int = 2
) -> np.ndarray[Any, Any]:
    """Normalize all vectors in a numpy array.

    Args:
        vector_array (np.ndarray[Any, Any]): Array of vectors to normalize
        axis (int, optional): Axis the vectors can be found at. Defaults to -1.
        order (int, optional): Order of the normal. Defaults to 2.

    Returns:
        np.ndarray[Any, Any]: Normalized array of vectors
    """
    l2 = np.atleast_1d(np.linalg.norm(vector_array, order, axis))
    l2[l2 == 0] = 1
    return vector_array / np.expand_dims(l2, axis)
