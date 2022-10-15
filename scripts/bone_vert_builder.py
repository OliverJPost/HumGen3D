# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy
from mathutils import Vector


def centroid(coordinates) -> Vector:
    x = [c[0] for c in coordinates]
    y = [c[1] for c in coordinates]
    z = [c[2] for c in coordinates]

    mx = sum(x) / len(x)
    my = sum(y) / len(y)
    mz = sum(z) / len(z)

    return Vector((mx, my, mz))


def main():
    context = bpy.context
    obj = bpy.data.objects["HG_Body"]

    selected_bone = context.selected_bones[0]

    selected_verts = [v for v in obj.data.vertices if v.select]

    head_co = selected_bone.head
    head_v_sorted = selected_verts.copy()
    head_v_sorted.sort(key=lambda v: abs((v.co - head_co).length))

    half = len(selected_verts) // 2
    if half == 0:
        half = 1

    selected_bone["head_verts"] = [v.index for v in head_v_sorted[:half]]
    centroid_co = centroid([v.co for v in head_v_sorted[:half]])
    selected_bone["head_relative_co"] = selected_bone.head - centroid_co

    tail_co = selected_bone.tail
    tail_v_sorted = selected_verts.copy()
    tail_v_sorted.sort(key=lambda v: abs((v.co - tail_co).length))

    selected_bone["tail_verts"] = [v.index for v in tail_v_sorted[:half]]
    centroid_co = centroid([v.co for v in tail_v_sorted[:half]])
    selected_bone["tail_relative_co"] = selected_bone.tail - centroid_co


# main()
