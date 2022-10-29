# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from typing import Any, Iterable, Union, cast

import numpy as np
from mathutils import Vector, kdtree  # type:ignore


def round_vector_to_tuple(
    vec: Vector, precision: int = 2
) -> tuple[float, float, float]:
    # Add 0 for accounting for negative 0's
    return cast(
        tuple[float, float, float], tuple(round(co, precision) + 0 for co in vec)
    )


TuplePoint = tuple[float, float, float]


def centroid(coordinates: Union[list[TuplePoint], np.ndarray[Any, Any]]) -> Vector:
    x = [c[0] for c in coordinates]
    y = [c[1] for c in coordinates]
    z = [c[2] for c in coordinates]

    mx = sum(x) / len(x)
    my = sum(y) / len(y)
    mz = sum(z) / len(z)

    return Vector((mx, my, mz))


Coordinates = Union[Iterable[tuple[float, float, float]], np.ndarray[Any, Any]]


def create_kdtree(coordinates: Coordinates) -> kdtree:
    size = len(coordinates)  # type:ignore[arg-type]
    kd = kdtree.KDTree(size)  # type:ignore
    for i, v in enumerate(coordinates):
        kd.insert(v, i)
    kd.balance()
    return kd


def normalize(
    vector_array: np.ndarray[Any, Any], axis: int = -1, order: int = 2
) -> np.ndarray[Any, Any]:
    l2 = np.atleast_1d(np.linalg.norm(vector_array, order, axis))
    l2[l2 == 0] = 1
    return vector_array / np.expand_dims(l2, axis)
