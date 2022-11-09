# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Functions used for """

from typing import Any, Iterable, Optional, Union, cast

import bpy
import numpy as np
from bpy.types import Object, bpy_prop_collection
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import DistanceDict  # type:ignore
from HumGen3D.common.type_aliases import C
from HumGen3D.human.keys.keys import ShapeKeyItem
from mathutils import Matrix, Vector, kdtree

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
    """Create a new Blender mesh object based on the passed data.

    Args:
        obj_name (str): Name of the new object.
        vertices (NDArrayOrList): List of vertice coordinates.
        edges (list or np.ndarray, optional): List of edges. Defaults to None.
        faces (list or np.ndarray, optional): List of faces, as list of vertex indices.
            Defaults to None.
        use_smooth (bool): Whether to use smooth shading. Defaults to True.
        context (C): Blender context. Defaults to None.

    Returns:
        bpy.types.Object: The newly created object.
    """
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


def world_coords_from_obj(
    obj: Object, data: Union[None, bpy_prop_collection, Iterable[ShapeKeyItem]] = None
) -> np.ndarray[Any, Any]:
    """Get a ndarray of the coordinates of this object's vertices in world space.

    By default the meshes base form coordinates are used (mesh.vertices[].co), but
    custom data can be passed.

    Args:
        obj: The object to get the coordinates from.
        data: The data to use. If None, the base form coordinates are used. You can
            pass a collection of ShapeKeyItems to use the coordinates of a shapkeys or
            a bpy_prop_collection like vertex coordinates.

    Returns:
        A ndarray of the coordinates of this object's vertices in world space.

    Raises:
        ValueError: If the data is not a ShapeKeyItem or a bpy_prop_collection.
    """
    iterate_data = False
    if not data:
        data = obj.data.vertices
    elif hasattr(data, "__iter__") and not isinstance(data, bpy_prop_collection):
        if data and not isinstance(data[0], ShapeKeyItem):  # type:ignore[index]
            raise ValueError(
                "Data argument is iterable but does not contain ShapeKeyItem."
            )
        iterate_data = True

    if not iterate_data:
        world_coords = _get_world_co(obj, data)  # type:ignore[arg-type]
    else:
        base_coords = _get_world_co(obj, obj.data.vertices)
        world_coords = base_coords.copy()
        for keyitem in data:
            if not keyitem.value:
                continue

            sk_data = keyitem.as_bpy().data
            sk_world_co = _get_world_co(obj, sk_data)
            world_coords += (sk_world_co - base_coords) * keyitem.value

    return world_coords


def _get_world_co(
    obj: bpy.types.Object, data: bpy_prop_collection
) -> np.ndarray[Any, Any]:
    vert_count = len(data)  # type:ignore[arg-type]
    local_coords = np.empty(vert_count * 3, dtype=np.float64)
    data.foreach_get("co", local_coords)

    mx: Matrix = obj.matrix_world  # type:ignore[assignment]
    world_coords = matrix_multiplication(mx, local_coords.reshape((-1, 3)))
    return world_coords


def build_distance_dict(
    body_coordinates_world: np.ndarray[Any, Any],
    target_coordinates_world: np.ndarray[Any, Any],
) -> DistanceDict:
    kd = kdtree.KDTree(len(body_coordinates_world))  # type:ignore[call-arg]

    for i, co in enumerate(body_coordinates_world):
        kd.insert(co, i)

    kd.balance()

    distance_dict = {}
    for idx_target, co_target in enumerate(target_coordinates_world):
        co_body, idx_body, _ = kd.find_n(co_target, 1)[0]

        distance_dict[idx_target] = (idx_body, co_body - Vector(co_target))

    return distance_dict


def matrix_multiplication(
    matrix: Matrix, coordinates: np.ndarray[Any, Any]
) -> np.ndarray[Any, Any]:
    vert_count = coordinates.shape[0]
    coords_4d = np.ones((vert_count, 4), "f")
    coords_4d[:, :-1] = coordinates

    coords = np.einsum("ij,aj->ai", matrix, coords_4d)[  # type:ignore[call-overload]
        :, :-1
    ]

    return cast(np.ndarray[Any, Any], coords)


def deform_obj_from_difference(
    name: str,
    distance_dict: DistanceDict,
    body_eval_coords_woorld: np.ndarray[Any, Any],
    deform_obj: bpy.types.Object,
    as_shapekey: bool = False,
) -> None:

    if as_shapekey:
        sk = deform_obj.data.shape_keys.key_blocks.get(name)
        if not sk:
            sk = deform_obj.shape_key_add(name=name)
            sk.interpolation = "KEY_LINEAR"
            sk.value = 1

    # TODO fully numpy
    for vertex_index in distance_dict:
        source_new_vert_loc = Vector(
            body_eval_coords_woorld[distance_dict[vertex_index][0]]
        )
        distance_to_vert = distance_dict[vertex_index][1]
        world_new_loc = source_new_vert_loc - distance_to_vert

        if as_shapekey:
            sk.data[vertex_index].co = (
                deform_obj.matrix_world.inverted() @ world_new_loc
            )
        else:
            deform_obj.data.vertices[vertex_index].co = (
                deform_obj.matrix_world.inverted() @ world_new_loc
            )
