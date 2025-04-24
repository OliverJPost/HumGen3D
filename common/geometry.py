# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Functions used for analysing, manipulating, or creating raw geometry."""

import hashlib
from typing import Any, Iterable, Optional, Union, cast

import bpy
import numpy as np
from bpy.types import Object, bpy_prop_collection
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import DistanceDict  # type:ignore
from HumGen3D.common.type_aliases import C
from HumGen3D.human.keys.keys import ShapeKeyItem
from mathutils import Matrix, Vector, kdtree

NDArrayOrList = Union[list, np.ndarray]


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
    obj: Object,
    data: Union[None, bpy_prop_collection, Iterable[ShapeKeyItem]] = None,
    local=False,
) -> np.ndarray:
    """Get a ndarray of the coordinates of this object's vertices in world space.

    By default the meshes base form coordinates are used (mesh.vertices[].co), but
    custom data can be passed.

    Args:
        obj: The object to get the coordinates from.
        data: The data to use. If None, the base form coordinates are used. You can
            pass a collection of ShapeKeyItems to use the coordinates of a shapkeys or
            a bpy_prop_collection like vertex coordinates.
        local: If True, the coordinates are returned in local space.

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
        world_coords = _get_world_co(obj, data, local)  # type:ignore[arg-type]
    else:
        base_coords = _get_world_co(obj, obj.data.vertices, local)
        world_coords = base_coords.copy()
        for keyitem in data:
            if not keyitem.value:
                continue

            sk_data = keyitem.as_bpy().data
            sk_world_co = _get_world_co(obj, sk_data, local)
            world_coords += (sk_world_co - base_coords) * keyitem.value

    return world_coords


def _get_world_co(
    obj: bpy.types.Object, data: bpy_prop_collection, local=False
) -> np.ndarray:
    vert_count = len(data)  # type:ignore[arg-type]
    coords = np.empty(vert_count * 3, dtype=np.float64)
    data.foreach_get("co", coords)

    if not local:
        mx: Matrix = obj.matrix_world  # type:ignore[assignment]
        coords = matrix_multiplication(mx, coords.reshape((-1, 3)))
    else:
        coords = coords.reshape((-1, 3))
    return coords


def build_distance_dict(
    body_coordinates_world: np.ndarray,
    target_coordinates_world: np.ndarray,
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


def matrix_multiplication(matrix: Matrix, coordinates: np.ndarray) -> np.ndarray:
    vert_count = coordinates.shape[0]
    coords_4d = np.ones((vert_count, 4), "f")
    coords_4d[:, :-1] = coordinates

    coords = np.einsum("ij,aj->ai", matrix, coords_4d)[  # type:ignore[call-overload]
        :, :-1
    ]

    return cast(np.ndarray, coords)


def deform_obj_from_difference(
    name: str,
    distance_dict: DistanceDict,
    body_eval_coords_woorld: np.ndarray,
    deform_obj: bpy.types.Object,
    as_shapekey: bool = False,
) -> None:

    if as_shapekey:
        key_blocks = deform_obj.data.shape_keys
        if not key_blocks:
            sk = deform_obj.shape_key_add(name="BASIS")
            sk.interpolation = "KEY_LINEAR"
            sk.value = 1
            key_blocks = deform_obj.data.shape_keys

        sk = key_blocks.key_blocks.get(name)
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

def build_distance_dict_SMOOTH(
    body_coordinates_world: np.ndarray,
    target_coordinates_world: np.ndarray,
    k_neighbors: int = 5,
    falloff_power: float = 2.0,
) -> DistanceDict:
    """
    Build a distance dictionary using k nearest neighbors instead of just one.

    Args:
        body_coordinates_world: Source body coordinates in world space
        target_coordinates_world: Target coordinates in world space
        k_neighbors: Number of nearest neighbors to consider
        falloff_power: Power for distance weighting (higher values give more weight to closer points)

    Returns:
        A dictionary mapping target indices to a list of (source_idx, distance_vector, weight) tuples
    """
    kd = kdtree.KDTree(len(body_coordinates_world))  # type:ignore[call-arg]

    for i, co in enumerate(body_coordinates_world):
        kd.insert(co, i)

    kd.balance()

    distance_dict = {}
    for idx_target, co_target in enumerate(target_coordinates_world):
        # Find k nearest neighbors
        nearest_points = kd.find_n(co_target, k_neighbors)

        # Calculate distances for weighting
        distances = [Vector(result[0]).length for result in nearest_points]

        # Handle edge case when some points are at exact same position (distance = 0)
        if any(d < 1e-7 for d in distances):
            # If any point is extremely close, just use the closest one
            co_body, idx_body, _ = nearest_points[0]
            distance_dict[idx_target] = [(idx_body, co_body - Vector(co_target), 1.0)]
        else:
            # Calculate weights based on inverse distance
            weights_raw = [1.0 / (d**falloff_power) for d in distances]
            weight_sum = sum(weights_raw)
            weights = [
                w / weight_sum for w in weights_raw
            ]  # Normalize weights to sum to 1

            # Store all neighbors with their weights
            neighbors_data = []
            for i, (co_body, idx_body, _) in enumerate(nearest_points):
                neighbors_data.append(
                    (idx_body, co_body - Vector(co_target), weights[i])
                )

            distance_dict[idx_target] = neighbors_data

    return distance_dict



def deform_obj_from_difference_SMOOTH(
    name: str,
    distance_dict: DistanceDict,
    body_eval_coords_world: np.ndarray,
    deform_obj: bpy.types.Object,
    as_shapekey: bool = False,
) -> None:
    """
    Deform an object using multiple nearest neighbors for smoother results.
    """
    if as_shapekey:
        key_blocks = deform_obj.data.shape_keys
        if not key_blocks:
            sk = deform_obj.shape_key_add(name="BASIS")
            sk.interpolation = "KEY_LINEAR"
            sk.value = 1
            key_blocks = deform_obj.data.shape_keys

        sk = key_blocks.key_blocks.get(name)
        if not sk:
            sk = deform_obj.shape_key_add(name=name)
            sk.interpolation = "KEY_LINEAR"
            sk.value = 1

    # Process each vertex using the weighted average of multiple nearest neighbors
    for vertex_index in distance_dict:
        neighbors = distance_dict[vertex_index]

        # Initialize the new world position as a zero vector
        world_new_loc = Vector((0, 0, 0))

        # Calculate the weighted average position
        for idx_body, distance_to_vert, weight in neighbors:
            source_new_vert_loc = Vector(body_eval_coords_world[idx_body])
            # Add the weighted contribution of this neighbor
            world_new_loc += (source_new_vert_loc - distance_to_vert) * weight

        # Apply the result
        if as_shapekey:
            sk.data[vertex_index].co = (
                deform_obj.matrix_world.inverted() @ world_new_loc
            )
        else:
            deform_obj.data.vertices[vertex_index].co = (
                deform_obj.matrix_world.inverted() @ world_new_loc
            )


def hash_mesh_object(obj: bpy.types.Object) -> int:
    """Hash an object.

    Args:
        obj: The object to hash.

    Returns:
        The hash of the object.
    """
    if obj.data.shape_keys:
        keys = obj.data.shape_keys.key_blocks
        coordinates = np.empty(
            (len(keys), len(obj.data.vertices) * 3), dtype=np.float64
        )
        for key in keys:
            key.data.foreach_get("data", coordinates[key.index])
    else:
        coordinates = world_coords_from_obj(obj)

    np.round(coordinates, 3, out=coordinates)
    return hash(tuple(coordinates))
