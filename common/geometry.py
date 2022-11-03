from typing import Any, Optional, Union

import bpy
import numpy as np
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C

NDArrayOrList = Union[list, np.ndarray[Any, Any]]


@injected_context
def obj_from_pydata(
    obj_name: str,
    vertices: NDArrayOrList,
    edges: Optional[NDArrayOrList] = None,
    faces: Optional[NDArrayOrList] = None,
    use_smooth: bool = True,
    context: C = None,
) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name="hair")
    all_verts_as_tuples = [tuple(co) for co in vertices]
    all_edges_as_tuples = [tuple(idxs) for idxs in edges] if edges is not None else []
    all_faces_as_tuples = [tuple(idxs) for idxs in faces] if faces is not None else []

    mesh.from_pydata(all_verts_as_tuples, all_edges_as_tuples, all_faces_as_tuples)
    mesh.update()

    for f in mesh.polygons:
        f.use_smooth = use_smooth

    obj = bpy.data.objects.new(obj_name, mesh)  # type:ignore[arg-type]

    context.scene.collection.objects.link(obj)
    return obj
