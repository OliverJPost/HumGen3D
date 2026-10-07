"""Module implementing functions to add objects a clothing to human."""

import contextlib
import json
import os
from typing import TYPE_CHECKING, Callable, Iterable, Optional, cast

import bpy
import numpy as np

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.backend.preferences.preference_func import get_addon_root
from HumGen3D.common.exceptions import HumGenException  # type:ignore
from HumGen3D.common.geometry import world_coords_from_obj
from HumGen3D.common.math import centroid
from HumGen3D.common.progress import Steps, phase, run
from HumGen3D.human.clothing.garment_fit import (
    convert_worn_steps,
    corrective_deltas,
    triangles,
    write_weights,
)
from mathutils import Matrix


def convert_obj_to_clothing(
    human: "Human",
    cloth_obj: bpy.types.Object,
    cloth_type: str,
    recalculate_weights: bool,
    context: bpy.types.Context,
    progress: Optional[Callable[[float], None]] = None,
) -> str:
    """Turn a mesh that sits on this human into a clothing object.

    See `convert_obj_to_clothing_steps`. `progress` is called with a fraction
    from 0 to 1 as the conversion advances.
    """
    return run(
        convert_obj_to_clothing_steps(
            human, cloth_obj, cloth_type, recalculate_weights, context
        ),
        progress,
    )


def convert_obj_to_clothing_steps(
    human: "Human",
    cloth_obj: bpy.types.Object,
    cloth_type: str,
    recalculate_weights: bool,
    context: bpy.types.Context,
) -> Steps[str]:
    """Turn a mesh that sits on this human into a clothing object, in steps.

    The object is taken the way it currently looks on the human, in any pose
    and with any body shape. Afterwards its base shape fits the unmodified body,
    a "Body Proportions" shape key holds the shape for this human, it has
    corrective shape keys and is weighted to the deform bones of the rig. On
    this human, in this pose, it looks the same as before.

    The steps yield the fraction of the work that is done. The object is only
    modified after the last step, so stopping early leaves it as it was.

    Args:
        human: Human the object sits on.
        cloth_obj: Mesh object to convert.
        cloth_type: "torso", "pants", "full" or "footwear". Decides which
            corrective shape keys are added.
        recalculate_weights: Transfer weights from the body. If False the
            existing vertex groups are kept.
        context: Blender context.

    Returns:
        How the weights were computed: "kept", "none", "bilaplacian" or
        "harmonic". "closest_point" means the solver failed and the weights are
        of lower quality.
    """
    rig, body_obj = human.objects.rig, human.objects.body
    context.view_layer.update()
    conversion = yield from phase(
        convert_worn_steps(human, cloth_obj, context, recalculate_weights), 0.0, 0.8
    )
    tris = triangles(cloth_obj)

    json_path = os.path.join(
        get_addon_root(), "human", "clothing", "corrective_sk_names_v2.json"
    )
    with open(json_path, "r") as f:
        names = json.load(f)["torso" if cloth_type == "top" else cloth_type]
    deltas = corrective_deltas(human, conversion.base, tris, names)
    yield 0.95

    # From here on the local space of the object is that of the rig, which is
    # what clothing loaded from the library expects.
    cloth_obj.parent = rig
    cloth_obj.matrix_parent_inverse = Matrix.Identity(4)
    cloth_obj.matrix_basis = Matrix.Identity(4)

    if cloth_obj.data.shape_keys:
        cloth_obj.shape_key_clear()
    cloth_obj.data.vertices.foreach_set("co", conversion.base.ravel())
    _add_key(cloth_obj, "Basis", conversion.base)
    for name, delta in deltas.items():
        _add_key(cloth_obj, name, conversion.base + delta)
    _set_cloth_corrective_drivers(
        body_obj, cloth_obj, cloth_obj.data.shape_keys.key_blocks
    )

    # Correctives driven by the current pose are part of how the object looks
    # now, and will be added again by the drivers.
    body_keys = body_obj.evaluated_get(
        context.evaluated_depsgraph_get()
    ).data.shape_keys.key_blocks
    fitted = conversion.rest.copy()
    for name, delta in deltas.items():
        fitted -= delta * body_keys[name].value
    _add_key(cloth_obj, "Body Proportions", fitted).value = 1

    if recalculate_weights:
        write_weights(
            cloth_obj,
            conversion.bones,
            conversion.weights,
            remove=[group.name for group in body_obj.vertex_groups],
        )
    cloth_obj.data.update()
    return conversion.solver


def _add_key(
    cloth_obj: bpy.types.Object, name: str, co: np.ndarray
) -> bpy.types.ShapeKey:
    key = cloth_obj.shape_key_add(name=name)
    key.interpolation = "KEY_LINEAR"
    key.data.foreach_set("co", co.ravel())
    return key


def _set_cloth_corrective_drivers(
    hg_body: bpy.types.Object,
    hg_cloth: bpy.types.Object,
    sk: Iterable[bpy.types.ShapeKey],
) -> None:
    """Sets up the drivers of the corrective shapekeys on the clothes.

    Args:
        hg_body (Object): HumGen body object
        hg_cloth (Object): HumGen cloth object
        sk (list): List of cloth object shapekeys #CHECK
    """
    with contextlib.suppress(AttributeError):
        for driver in hg_cloth.data.shape_keys.animation_data.drivers[:]:
            hg_cloth.data.shape_keys.animation_data.drivers.remove(driver)

    for driver in hg_body.data.shape_keys.animation_data.drivers:
        target_sk = driver.data_path.replace('key_blocks["', "").replace(
            '"].value', ""
        )  # TODO this is horrible

        if target_sk not in [shapekey.name for shapekey in sk]:
            continue

        new_driver = sk[target_sk].driver_add("value")  # type:ignore[index]
        new_var = new_driver.driver.variables.new()
        new_var.type = "TRANSFORMS"
        new_target = new_var.targets[0]
        old_var = driver.driver.variables[0]
        old_target = old_var.targets[0]
        new_target.id = hg_body.parent

        new_driver.driver.expression = driver.driver.expression
        new_target.bone_target = old_target.bone_target
        new_target.transform_type = old_target.transform_type
        new_target.transform_space = old_target.transform_space


def get_human_from_distance(cloth_obj: bpy.types.Object) -> "Human":
    """Find the closest human to this object based on centroid distance.

    Args:
        cloth_obj (Object): The object to find the closest human to.

    Returns:
        Human: The closest human to the object.

    Raises:
        HumGenException: If there is no human in the file or the nearest human is
            more than 2 meters away.
    """
    world_coords_cloth_obj = world_coords_from_obj(cloth_obj)
    centroid_cloth = centroid(world_coords_cloth_obj)

    human_rig_objs = (
        obj for obj in bpy.data.objects if obj.HG.ishuman and obj.HG.body_obj
    )

    human_distances = {}
    for rig_obj in human_rig_objs:
        world_body_coords = world_coords_from_obj(rig_obj.HG.body_obj)
        human_distances[rig_obj] = abs(
            (centroid(world_body_coords) - centroid_cloth).length
        )
    if not human_distances:
        raise HumGenException("There is no Human Generator human in this file.")

    closest_human_rig = min(human_distances, key=human_distances.get)  # type:ignore

    if human_distances[closest_human_rig] > 2.0:
        raise HumGenException("Clothing does not seem to be on a HG body object.")

    from HumGen3D.human.human import Human

    return cast(Human, Human.from_existing(closest_human_rig))
