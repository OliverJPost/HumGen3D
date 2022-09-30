# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from mathutils import Vector


def centroid(coordinates) -> Vector:
    x = [c[0] for c in coordinates]
    y = [c[1] for c in coordinates]
    z = [c[2] for c in coordinates]

    mx = sum(x) / len(x)
    my = sum(y) / len(y)
    mz = sum(z) / len(z)

    return Vector((mx, my, mz))
