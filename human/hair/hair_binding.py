# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements keeping haircard objects attached to the skin of the body.

Every vertex of a haircard object is attached to a vertex of the body. This is used
to give the hair the same animated shape keys as the body, like expressions, and to
move the hair along when the shape of the body is changed.
"""

import re
from typing import TYPE_CHECKING, Iterable, Optional

import bpy
import numpy as np
from mathutils import Matrix

if TYPE_CHECKING:
    from ..human import Human

# Index of the body vertex every vertex of a haircard object is attached to
BODY_VERTEX_ATTRIBUTE = "hg_body_vertex"
# Position of every vertex relative to the body vertex it is attached to
BODY_OFFSET_ATTRIBUTE = "hg_body_offset"
# Shape keys that move the hair less than this are not added to the hair
MIN_KEY_DISPLACEMENT = 0.0005
EXPRESSION_KEY_PREFIXES = ("e_", "e{", "expr_")


def transform_coords(matrix: Matrix, coords: np.ndarray) -> np.ndarray:
    """Transforms coordinates with a Blender matrix.

    Args:
        matrix (Matrix): 4x4 matrix to transform the coordinates with.
        coords (np.ndarray): (n, 3) coordinates.

    Returns:
        np.ndarray: (n, 3) transformed coordinates.
    """
    matrix_np = np.array(matrix)
    return coords @ matrix_np[:3, :3].T + matrix_np[:3, 3]


def get_coords(data: bpy.types.bpy_prop_collection) -> np.ndarray:
    """Gets the coordinates of mesh vertices or of the data of a shape key.

    Args:
        data (bpy.types.bpy_prop_collection): Collection of items with a co.

    Returns:
        np.ndarray: (n, 3) coordinates.
    """
    coords = np.empty(len(data) * 3, dtype=np.float64)
    data.foreach_get("co", coords)
    return coords.reshape((-1, 3))


def _dynamic_keys(human: "Human") -> list[bpy.types.ShapeKey]:
    """Gets the body shape keys that change while the human is animated.

    These are the expressions and the keys with a driver, like the keys of the
    face rig. The other keys define the shape of the body.
    """
    body_keys = human.objects.body.data.shape_keys
    if not body_keys:
        return []

    driven_names = set()
    if body_keys.animation_data:
        for fcurve in body_keys.animation_data.drivers:
            match = re.match(r'key_blocks\["(.+)"\]\.value$', fcurve.data_path)
            if match:
                driven_names.add(bpy.utils.unescape_identifier(match.group(1)))

    return [
        key
        for key in body_keys.key_blocks
        if key != body_keys.reference_key
        and (key.name in driven_names or key.name.startswith(EXPRESSION_KEY_PREFIXES))
    ]


def dynamic_key_values(human: "Human", context: bpy.types.Context) -> dict[str, float]:
    """Gets the current values of the animated shape keys of the body.

    Args:
        human (Human): Human to get the values of.
        context (bpy.types.Context): Blender context.

    Returns:
        dict[str, float]: Values per shape key name, only of the keys that are not 0.
    """
    body_keys = human.objects.body.data.shape_keys
    if not body_keys:
        return {}

    # The original keys don't have the values that drivers give them
    depsgraph = context.evaluated_depsgraph_get()
    evaluated_blocks = body_keys.evaluated_get(depsgraph).key_blocks
    values = {}
    for key in _dynamic_keys(human):
        evaluated_key = evaluated_blocks.get(key.name) or key
        if not evaluated_key.mute and abs(evaluated_key.value) > 1e-6:
            values[key.name] = evaluated_key.value

    return values


def _key_delta(key: bpy.types.ShapeKey) -> np.ndarray:
    return get_coords(key.data) - get_coords(key.relative_key.data)


def dynamic_displacement(human: "Human", values: dict[str, float]) -> np.ndarray:
    """Gets how far the animated shape keys move every vertex of the body.

    Args:
        human (Human): Human to get the displacement of.
        values (dict[str, float]): Values per shape key name.

    Returns:
        np.ndarray: (n, 3) displacement in the space of the body object.
    """
    body = human.objects.body
    displacement = np.zeros((len(body.data.vertices), 3))
    for name, value in values.items():
        displacement += _key_delta(body.data.shape_keys.key_blocks[name]) * value

    return displacement


def static_body_coords(human: "Human") -> np.ndarray:
    """Gets the shape of the body without its animated shape keys.

    Args:
        human (Human): Human to get the body shape of.

    Returns:
        np.ndarray: (n, 3) coordinates in the space of the body object.
    """
    body = human.objects.body
    body_keys = body.data.shape_keys
    if not body_keys:
        return get_coords(body.data.vertices)

    dynamic_names = {key.name for key in _dynamic_keys(human)}
    coords = get_coords(body_keys.reference_key.data)
    for key in body_keys.key_blocks:
        if key == body_keys.reference_key or key.name in dynamic_names:
            continue
        if key.mute or not key.value:
            continue
        coords += _key_delta(key) * key.value

    return coords


def _body_to_rig(human: "Human") -> Matrix:
    rig = human.objects.rig
    return rig.matrix_world.inverted() @ human.objects.body.matrix_world


def set_attachment(mesh: bpy.types.Mesh, body_vert_idxs: np.ndarray) -> None:
    """Stores the body vertex every vertex of a hair mesh is attached to.

    Args:
        mesh (bpy.types.Mesh): Mesh of a haircard object.
        body_vert_idxs (np.ndarray): (v,) index of a body vertex per mesh vertex.
    """
    attribute = mesh.attributes.get(BODY_VERTEX_ATTRIBUTE)
    if not attribute:
        attribute = mesh.attributes.new(BODY_VERTEX_ATTRIBUTE, "INT", "POINT")
    attribute.data.foreach_set("value", np.asarray(body_vert_idxs, dtype=np.int32))


def get_attachment(human: "Human", mesh: bpy.types.Mesh) -> Optional[np.ndarray]:
    """Gets the body vertex every vertex of a hair mesh is attached to.

    Args:
        human (Human): Human the hair belongs to.
        mesh (bpy.types.Mesh): Mesh of a haircard object.

    Returns:
        Optional[np.ndarray]: (v,) index of a body vertex per mesh vertex. None if the
            mesh has no attachment or the vertices of the body were changed since.
    """
    attribute = mesh.attributes.get(BODY_VERTEX_ATTRIBUTE)
    if not attribute or "lod" in human.objects.rig:
        return None

    body_vert_idxs = np.empty(len(mesh.vertices), dtype=np.int32)
    attribute.data.foreach_get("value", body_vert_idxs)
    if body_vert_idxs.max(initial=0) >= len(human.objects.body.data.vertices):
        return None

    return body_vert_idxs


def _add_driver(
    key: bpy.types.ShapeKey, body_keys: bpy.types.Key, body_key_name: str
) -> None:
    """Makes the value of a hair shape key follow a shape key of the body."""
    key.driver_remove("value")
    driver = key.driver_add("value").driver
    # Not a scripted expression, so it also works with auto run scripts disabled
    driver.type = "AVERAGE"
    variable = driver.variables.new()
    variable.name = "body_value"
    variable.type = "SINGLE_PROP"
    target = variable.targets[0]
    target.id_type = "KEY"
    target.id = body_keys
    name = bpy.utils.escape_identifier(body_key_name)
    target.data_path = f'key_blocks["{name}"].value'


def sync_shape_keys(human: "Human", hair_obj: bpy.types.Object) -> None:
    """Gives a haircard object the same animated shape keys as the body.

    Keys that don't move the hair are left out and keys that were removed from the
    body are removed from the hair. The values of the keys follow the values of the
    body keys.

    Args:
        human (Human): Human the hair belongs to.
        hair_obj (bpy.types.Object): Haircard object, see bind_to_body.
    """
    mesh = hair_obj.data
    body_vert_idxs = get_attachment(human, mesh)
    if body_vert_idxs is None:
        return

    body_keys = human.objects.body.data.shape_keys
    dynamic_keys = _dynamic_keys(human)
    remove_shape_keys(hair_obj, keep={key.name for key in dynamic_keys})

    to_rig_rotation = np.array(_body_to_rig(human))[:3, :3]
    if mesh.shape_keys:
        basis = get_coords(mesh.shape_keys.reference_key.data)
    else:
        basis = get_coords(mesh.vertices)

    for body_key in dynamic_keys:
        if mesh.shape_keys and body_key.name in mesh.shape_keys.key_blocks:
            continue
        delta = _key_delta(body_key)[body_vert_idxs]
        if np.abs(delta).max(initial=0) < MIN_KEY_DISPLACEMENT:
            continue

        if not mesh.shape_keys:
            hair_obj.shape_key_add(name="Basis", from_mix=False)
        hair_key = hair_obj.shape_key_add(name=body_key.name, from_mix=False)
        hair_key.interpolation = "KEY_LINEAR"
        hair_key.slider_min = body_key.slider_min
        hair_key.slider_max = body_key.slider_max
        hair_key.data.foreach_set("co", (basis + delta @ to_rig_rotation.T).ravel())
        hair_key.value = body_key.value
        _add_driver(hair_key, body_keys, body_key.name)


def remove_shape_keys(
    hair_obj: bpy.types.Object,
    names: Optional[Iterable[str]] = None,
    keep: Iterable[str] = (),
) -> None:
    """Removes shape keys from a haircard object, including their drivers.

    Args:
        hair_obj (bpy.types.Object): Haircard object to remove the keys from.
        names (Optional[Iterable[str]]): Names of the keys to remove. All keys are
            removed if not passed.
        keep (Iterable[str]): Names of keys that should not be removed.
    """
    hair_keys = hair_obj.data.shape_keys
    if not hair_keys:
        return

    names = None if names is None else set(names)
    keep = set(keep)
    for key in list(hair_keys.key_blocks):
        if key == hair_keys.reference_key or key.name in keep:
            continue
        if names is not None and key.name not in names:
            continue
        # Removing the key first would leave a driver without a property to drive
        key.driver_remove("value")
        hair_obj.shape_key_remove(key)

    if len(hair_keys.key_blocks) == 1:
        hair_obj.shape_key_clear()


def bind_to_body(
    human: "Human", hair_obj: bpy.types.Object, dynamic_values: dict[str, float]
) -> None:
    """Attaches a newly created haircard object to the body.

    The object needs to have the body vertex of every vertex, see set_attachment.

    Args:
        human (Human): Human the hair belongs to.
        hair_obj (bpy.types.Object): Haircard object, with its mesh in the space of
            the rig.
        dynamic_values (dict[str, float]): Values the animated shape keys of the body
            had when the hair was created, see dynamic_key_values.
    """
    mesh = hair_obj.data
    body_vert_idxs = get_attachment(human, mesh)
    if body_vert_idxs is None:
        return

    mx_to_rig = _body_to_rig(human)
    to_rig_rotation = np.array(mx_to_rig)[:3, :3]
    coords = get_coords(mesh.vertices)
    if dynamic_values:
        # The hair was created on for example a smiling face. Undo this, so the
        # shape keys of the hair can do it again.
        displacement = dynamic_displacement(human, dynamic_values)[body_vert_idxs]
        coords -= displacement @ to_rig_rotation.T
        mesh.vertices.foreach_set("co", coords.ravel())
        mesh.update()

    body_coords = transform_coords(mx_to_rig, static_body_coords(human))
    offset_attribute = mesh.attributes.get(BODY_OFFSET_ATTRIBUTE)
    if not offset_attribute:
        offset_attribute = mesh.attributes.new(
            BODY_OFFSET_ATTRIBUTE, "FLOAT_VECTOR", "POINT"
        )
    offsets = coords - body_coords[body_vert_idxs]
    offset_attribute.data.foreach_set("vector", offsets.ravel())

    sync_shape_keys(human, hair_obj)


def sync_haircards(human: "Human") -> None:
    """Updates the shape keys of all haircard objects of the human.

    Call this after adding animated shape keys to the body or removing them.

    Args:
        human (Human): Human to update the haircard objects of.
    """
    for hair_obj in human.objects.haircards:
        sync_shape_keys(human, hair_obj)


def refit_haircards(human: "Human") -> None:
    """Moves all haircard objects along with a changed shape of the body.

    Args:
        human (Human): Human to move the haircard objects of.
    """
    hair_objs = human.objects.haircards
    if not hair_objs:
        return

    body_coords = transform_coords(_body_to_rig(human), static_body_coords(human))
    for hair_obj in hair_objs:
        mesh = hair_obj.data
        body_vert_idxs = get_attachment(human, mesh)
        offset_attribute = mesh.attributes.get(BODY_OFFSET_ATTRIBUTE)
        if body_vert_idxs is None or not offset_attribute:
            continue

        offsets = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
        offset_attribute.data.foreach_get("vector", offsets)
        new_coords = body_coords[body_vert_idxs] + offsets.reshape((-1, 3))
        if mesh.shape_keys:
            old_coords = get_coords(mesh.shape_keys.reference_key.data)
            for key in mesh.shape_keys.key_blocks:
                key_coords = get_coords(key.data) + new_coords - old_coords
                key.data.foreach_set("co", key_coords.ravel())
        mesh.vertices.foreach_set("co", new_coords.ravel())
        mesh.update()


def retarget_drivers(
    hair_obj: bpy.types.Object,
    old_body_keys: bpy.types.Key,
    new_body_keys: bpy.types.Key,
) -> None:
    """Makes the shape keys of a copied haircard object follow a copied body.

    Args:
        hair_obj (bpy.types.Object): Copy of a haircard object.
        old_body_keys (bpy.types.Key): Shape keys of the body the hair was copied from.
        new_body_keys (bpy.types.Key): Shape keys of the copy of that body.
    """
    hair_keys = hair_obj.data.shape_keys
    if not hair_keys or not hair_keys.animation_data:
        return

    for fcurve in hair_keys.animation_data.drivers:
        for variable in fcurve.driver.variables:
            for target in variable.targets:
                if target.id == old_body_keys:
                    target.id = new_body_keys
