# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements baking the T-pose into the rest pose of a human."""

import json
import math
import os
from typing import TYPE_CHECKING, Any

import bpy
import numpy as np
from HumGen3D.backend.preferences.preference_func import get_addon_root
from HumGen3D.common import is_legacy
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.human.expression.expression import FACE_RIG_BONE_NAMES
from mathutils import Matrix, Quaternion, Vector

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

# Forward bend of the elbows, so IK solvers know which way the arm bends
ELBOW_BEND = math.radians(2)
ARM_BONES = ("upper_arm", "forearm", "hand")
SIDE_RAISE_PREFIX = "cor_ShoulderSideRaise"


def set_t_pose_as_rest(human: "Human", context: bpy.types.Context) -> None:
    """Bakes the T-pose into the meshes and the armature of this human.

    The current pose of the body is discarded, the pose of the face rig is kept.
    The shoulder side raise corrective shape keys are removed, as they would be
    fully active in the new rest pose. The drivers of the other corrective shape
    keys are offset, so they give the same result as with the A-pose rest pose.

    Args:
        human (Human): Human to change the rest pose of.
        context (bpy.types.Context): Blender context.

    Raises:
        HumGenException: If the human is a Rigify or legacy human.
    """
    rig = human.objects.rig
    if human.pose.rigify.is_rigify:
        raise HumGenException("Can't change the rest pose of a Rigify human.")
    if is_legacy(rig):
        raise HumGenException("Can't change the rest pose of a legacy human.")

    old_active = context.view_layer.objects.active
    old_selected = context.selected_objects
    for obj in old_selected:
        obj.select_set(False)
    rig.hide_viewport = False
    rig.hide_set(False)
    rig.select_set(True)
    context.view_layer.objects.active = rig

    # The keys of an animation are relative to the rest pose, so it is retargeted
    # again after the rest pose changed
    animation = human.animation.as_dict()
    animation_loop = human.animation.loop
    human.animation.remove()

    _remove_side_raise_shapekeys(human)
    face_rig_pose = _reset_pose(rig)
    # Constraints would otherwise be baked into the rest pose of the eye and jaw bones
    muted_constraints = _mute_constraints(rig)
    _set_t_pose(rig, context)
    corrective_driver_values = _get_corrective_driver_values(human, context)

    for obj in human.objects:
        if obj.type != "MESH":
            continue
        if not [m for m in obj.modifiers if m.type == "ARMATURE" and m.object == rig]:
            continue
        rotations, offsets = _get_skin_transforms(obj, rig, context)
        _transform_mesh(obj, rotations, offsets)

    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    # The drivers use the rotation of a bone relative to its rest pose, which is now
    # zero in the T-pose. Adding the value they had in the T-pose corrects for this.
    for driver, value in corrective_driver_values:
        if abs(value) > 0.001:
            driver.driver.expression = f"({driver.driver.expression}) {value:+.6f}"

    for bone_name, constraint_name in muted_constraints:
        rig.pose.bones[bone_name].constraints[constraint_name].mute = False
    for bone_name, matrix_basis in face_rig_pose.items():
        rig.pose.bones[bone_name].matrix_basis = matrix_basis

    rig["t_pose_rest"] = True

    if animation["set"]:
        human.animation.set(
            animation["set"], context, loop=animation_loop, set_frame_range=False
        )

    rig.select_set(False)
    for obj in old_selected:
        obj.select_set(True)
    context.view_layer.objects.active = old_active


def _remove_side_raise_shapekeys(human: "Human") -> None:
    for obj in human.objects:
        if obj.type != "MESH" or not obj.data.shape_keys:
            continue

        key = obj.data.shape_keys
        if key.animation_data:
            for driver in key.animation_data.drivers[:]:
                if driver.data_path.startswith(f'key_blocks["{SIDE_RAISE_PREFIX}'):
                    key.animation_data.drivers.remove(driver)

        for sk in key.key_blocks[:]:
            if sk.name.startswith(SIDE_RAISE_PREFIX):
                obj.shape_key_remove(sk)


def _get_corrective_driver_values(
    human: "Human", context: bpy.types.Context
) -> list[tuple[bpy.types.FCurve, float]]:
    """Gets the drivers of the corrective shape keys and their unclamped values."""
    drivers = []
    for obj in human.objects:
        if obj.type != "MESH" or not obj.data.shape_keys:
            continue
        key = obj.data.shape_keys
        if not key.animation_data:
            continue
        for driver in key.animation_data.drivers:
            if driver.data_path.startswith('key_blocks["cor_'):
                drivers.append((obj, driver))

    # The value of a shape key is clamped to its slider range
    slider_ranges = []
    for obj, driver in drivers:
        sk = obj.data.shape_keys.path_resolve(driver.data_path.rsplit(".", 1)[0])
        slider_ranges.append((sk, sk.slider_min, sk.slider_max))
        sk.slider_min = -10
        sk.slider_max = 10

    depsgraph = context.evaluated_depsgraph_get()
    depsgraph.update()
    driver_values = []
    for obj, driver in drivers:
        key_eval = obj.evaluated_get(depsgraph).data.shape_keys
        driver_values.append((driver, key_eval.path_resolve(driver.data_path)))

    for sk, slider_min, slider_max in slider_ranges:
        sk.slider_min = slider_min
        sk.slider_max = slider_max

    return driver_values


def _reset_pose(rig: bpy.types.Object) -> dict[str, Matrix]:
    """Resets all bones, returns the pose of the face rig and eye target bones."""
    face_rig_pose = {}
    for pose_bone in rig.pose.bones:
        original_name = pose_bone.get("original_name", pose_bone.name)
        if original_name in FACE_RIG_BONE_NAMES or original_name.startswith(
            "eyeball_lookat"
        ):
            face_rig_pose[pose_bone.name] = pose_bone.matrix_basis.copy()
        pose_bone.matrix_basis = Matrix.Identity(4)

    return face_rig_pose


def _mute_constraints(rig: bpy.types.Object) -> list[tuple[str, str]]:
    muted_constraints = []
    for pose_bone in rig.pose.bones:
        for constraint in pose_bone.constraints:
            if not constraint.mute:
                constraint.mute = True
                muted_constraints.append((pose_bone.name, constraint.name))

    return muted_constraints


def load_t_pose() -> dict[str, dict[str, Any]]:
    """Loads the T-pose definition, per original bone name.

    Returns:
        dict[str, dict[str, Any]]: Per bone the edit bone roll the rotation is
            relative to, the rotation as quaternion and optionally a location
            relative to the length of the bone.
    """
    path = os.path.join(get_addon_root(), "human", "process", "t_pose.json")
    with open(path, "r") as f:
        return json.load(f)  # type:ignore[no-any-return]


def _set_t_pose(rig: bpy.types.Object, context: bpy.types.Context) -> None:
    t_pose = load_t_pose()

    bone_names = {
        pose_bone.get("original_name", pose_bone.name): pose_bone.name
        for pose_bone in rig.pose.bones
    }

    # The rotations in the json are relative to these bone rolls. The rolls of the
    # rig differ based on if a pose from the library was applied to it before.
    bpy.ops.object.mode_set(mode="EDIT")
    for original_name, bone_data in t_pose.items():
        rig.data.edit_bones[bone_names[original_name]].roll = bone_data["roll"]
    bpy.ops.object.mode_set(mode="OBJECT")

    for original_name, bone_data in t_pose.items():
        pose_bone = rig.pose.bones[bone_names[original_name]]
        # Locations are stored relative to the length of the bone
        location = Vector(bone_data.get("location", (0, 0, 0))) * pose_bone.bone.length
        rotation = Quaternion(bone_data["rotation"])
        pose_bone.matrix_basis = Matrix.LocRotScale(location, rotation, None)

    # The same rotations give slightly different results per body type, so point
    # the arm bones exactly along the X axis. Humans face the -Y direction.
    for suffix, side in ((".L", 1), (".R", -1)):
        forearm_direction = (side * math.cos(ELBOW_BEND), -math.sin(ELBOW_BEND), 0)
        directions = ((side, 0, 0), forearm_direction, (side, 0, 0))
        for bone_name, direction in zip(ARM_BONES, directions):
            pose_bone = rig.pose.bones[bone_names[bone_name + suffix]]
            context.view_layer.update()
            current_direction = pose_bone.tail - pose_bone.head
            swing = current_direction.rotation_difference(Vector(direction))
            pivot = Matrix.Translation(pose_bone.head)
            pose_bone.matrix = (
                pivot @ swing.to_matrix().to_4x4() @ pivot.inverted() @ pose_bone.matrix
            )

    context.view_layer.update()


def _get_skin_transforms(
    obj: bpy.types.Object, rig: bpy.types.Object, context: bpy.types.Context
) -> tuple[np.ndarray, np.ndarray]:
    """Gets the transform the armature modifier applies to each vertex.

    The armature deforms each vertex with its own rotation and offset, no matter
    where the vertex is. Deforming a copy of the mesh with all vertices on the
    origin and on the three unit vectors therefore gives these for every vertex.

    Args:
        obj (bpy.types.Object): Mesh object deformed by the rig.
        rig (bpy.types.Object): Posed armature object.
        context (bpy.types.Context): Blender context.

    Returns:
        tuple[np.ndarray, np.ndarray]: Rotation matrix per vertex (n, 3, 3) and
            offset per vertex (n, 3).
    """
    probe_obj = obj.copy()
    probe_obj.data = obj.data.copy()
    context.scene.collection.objects.link(probe_obj)
    if probe_obj.data.shape_keys:
        probe_obj.shape_key_clear()
    for mod in probe_obj.modifiers[:]:
        if mod.type == "ARMATURE" and mod.object == rig:
            mod.show_viewport = True
        else:
            probe_obj.modifiers.remove(mod)

    vert_count = len(probe_obj.data.vertices)
    deformed_coords = []
    for point in ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)):
        coords = np.tile(np.array(point, dtype=np.float64), vert_count)
        probe_obj.data.vertices.foreach_set("co", coords)
        probe_obj.data.update()

        depsgraph = context.evaluated_depsgraph_get()
        depsgraph.update()
        probe_eval = probe_obj.evaluated_get(depsgraph)
        coords = np.empty(vert_count * 3, dtype=np.float64)
        probe_eval.data.vertices.foreach_get("co", coords)
        deformed_coords.append(coords.reshape((-1, 3)))

    probe_mesh = probe_obj.data
    bpy.data.objects.remove(probe_obj)
    bpy.data.meshes.remove(probe_mesh)

    offsets = deformed_coords[0]
    rotations = np.stack([coords - offsets for coords in deformed_coords[1:]], axis=2)

    return rotations, offsets


def _transform_mesh(
    obj: bpy.types.Object, rotations: np.ndarray, offsets: np.ndarray
) -> None:
    mesh = obj.data
    coord_collections = [mesh.vertices]
    if mesh.shape_keys:
        coord_collections.extend(sk.data for sk in mesh.shape_keys.key_blocks)

    for coord_collection in coord_collections:
        coords = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
        coord_collection.foreach_get("co", coords)
        coords = np.einsum("nij,nj->ni", rotations, coords.reshape((-1, 3))) + offsets
        coord_collection.foreach_set("co", coords.reshape((-1)))

    mesh.update()
