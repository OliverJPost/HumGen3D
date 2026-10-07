# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Retargets animation clips onto the Human Generator rig.

A clip stores, per bone and frame, the rotation in armature space relative to a
reference T-pose (see clip.py). The bones of the rig get the same rotation applied
on top of their own reference T-pose:

    bone_rotation(frame) = clip_rotation(frame) @ reference_rotation

Because the rotations are absolute, the rig keeps its own rest offsets (the angle
of its shoulders, thumbs or feet) without those differences adding up along the
chain. The result is converted to the local matrix_basis Blender keys, using the
actual rest pose of the rig, so it works for every body shape, height and rest pose.

Two adjustments are made for realistic humans. The bend between the hips and the
chest is spread evenly over the spine bones, since game animations often bend the
whole torso at one joint, which looks like a hunchback on a continuous mesh. And the
fingers can be blended towards the relaxed hand of the rest pose of the human,
because tight fists fold the fingers of the human into each other.
"""

import math
from typing import Any, Dict, Iterator, List, Optional, Tuple

import bpy
from bpy.types import Bone, Object, PoseBone  # type:ignore
from HumGen3D.human.process.rest_pose import ARM_BONES, ELBOW_BEND, load_t_pose
from mathutils import Matrix, Quaternion, Vector

from .clip import LEG_BONES, ROOT_BONE

BoneKeys = Dict[str, Tuple[List[Quaternion], Optional[List[Vector]]]]
Rotations = Dict[str, List[Quaternion]]

# The bend between the first and last bone is spread evenly over these bones
SPINE_CHAIN = ("spine", "spine.001", "spine.002", "spine.003")
FINGER_CHAINS = tuple(
    (f"hand{suffix}", *(f"{finger}.0{i}{suffix}" for i in (1, 2, 3)))
    for suffix in (".L", ".R")
    for finger in ("thumb", "f_index", "f_middle", "f_ring", "f_pinky")
)
# Bones whose reference direction is taken from the clip instead of the T-pose json.
# The thumb of the T-pose json lies in the plane of the palm, while most libraries
# rotate it downwards, which gives fists a thumb that pokes through the fingers.
SNAP_TO_CLIP_REFERENCE = tuple(name for chain in FINGER_CHAINS for name in chain[1:])


def original_name(pose_bone: PoseBone) -> str:
    """Name of the bone before it was renamed by the user, or its own name."""
    return pose_bone.get(  # type:ignore[no-any-return]
        "original_name", pose_bone.get("hg_original_name", pose_bone.name)
    )


def hierarchy_order(rig: Object) -> Iterator[PoseBone]:
    """Yields the pose bones of the rig with every parent before its children."""
    stack = [pose_bone for pose_bone in rig.pose.bones if not pose_bone.parent]
    while stack:
        pose_bone = stack.pop()
        yield pose_bone
        stack.extend(pose_bone.children)


def leg_length(rig: Object) -> float:
    """Length of the left thigh and shin together, in armature space."""
    bones = {original_name(pose_bone): pose_bone.bone for pose_bone in rig.pose.bones}
    return sum(bones[f"{name}.L"].length for name in LEG_BONES)


def reference_pose(rig: Object, clip: Optional[dict] = None) -> Dict[str, Matrix]:
    """Matrices of the bones of the rig in the reference T-pose, in armature space.

    This is the T-pose of HumGen3D/human/process/t_pose.json, computed the same way
    rest_pose._set_t_pose does, without changing the rig. If the T-pose was baked
    into the rest pose it is the rest pose itself. The fingers point in the direction
    they have in the reference pose of the clip, if it stores those.

    Args:
        rig (Object): Human Generator armature object.
        clip (Optional[dict]): Animation clip with reference directions.

    Returns:
        dict[str, Matrix]: Per bone name the matrix in the reference pose.
    """
    snap_directions = {}
    if clip:
        for name in SNAP_TO_CLIP_REFERENCE:
            direction = clip.get("reference_directions", {}).get(name)
            if direction:
                snap_directions[name] = Vector(direction)

    if rig.get("t_pose_rest"):
        reference = {bone.name: bone.matrix_local.copy() for bone in rig.data.bones}
        return _snap_directions(rig, reference, snap_directions)

    t_pose = load_t_pose()
    rest = {}
    for pose_bone in rig.pose.bones:
        bone = pose_bone.bone
        bone_data = t_pose.get(original_name(pose_bone))
        if bone_data:
            # The rotations in the json are relative to the rolls in the json
            rotation = Bone.MatrixFromAxisRoll(
                bone.tail_local - bone.head_local, bone_data["roll"]
            )
            rest[bone.name] = Matrix.LocRotScale(bone.head_local, rotation, None)
        else:
            rest[bone.name] = bone.matrix_local.copy()

    # The same rotations give slightly different results per body type, so point
    # the arm bones exactly along the X axis. Humans face the -Y direction.
    for suffix, side in ((".L", 1), (".R", -1)):
        forearm_direction = (side * math.cos(ELBOW_BEND), -math.sin(ELBOW_BEND), 0)
        directions = ((side, 0, 0), forearm_direction, (side, 0, 0))
        for bone_name, direction in zip(ARM_BONES, directions):
            snap_directions[bone_name + suffix] = Vector(direction)

    reference = {}
    for pose_bone in hierarchy_order(rig):
        name = pose_bone.name
        bone_data = t_pose.get(original_name(pose_bone))
        if bone_data:
            location = Vector(bone_data.get("location", (0, 0, 0))) * pose_bone.length
            rotation = Quaternion(bone_data["rotation"])
            basis = Matrix.LocRotScale(location, rotation, None)
        else:
            basis = Matrix.Identity(4)

        if pose_bone.parent:
            parent_matrix = reference[pose_bone.parent.name]
            local_rest = rest[pose_bone.parent.name].inverted() @ rest[name]
        else:
            parent_matrix = Matrix.Identity(4)
            local_rest = rest[name]
        reference[name] = parent_matrix @ local_rest @ basis

    # rest_pose._set_t_pose changes the rolls of the bones to the ones of the json,
    # which keeps the mesh from twisting. The rolls of this rig are left as they
    # are, so the matrices are twisted back to the rest frames of the rig, which
    # gives the same deformation of the mesh.
    for pose_bone in rig.pose.bones:
        name = pose_bone.name
        if original_name(pose_bone) in t_pose:
            twist = rest[name].inverted() @ pose_bone.bone.matrix_local
            reference[name] = reference[name] @ twist

    return _snap_directions(rig, reference, snap_directions)


def _snap_directions(
    rig: Object, reference: Dict[str, Matrix], directions: Dict[str, Vector]
) -> Dict[str, Matrix]:
    """Rotates bones around their head to point in the given directions.

    The children of a rotated bone rotate along, like they would in Blender.

    Args:
        rig (Object): Armature the reference matrices belong to.
        reference (dict[str, Matrix]): Per bone name the matrix to adjust.
        directions (dict[str, Vector]): Per original bone name the direction.

    Returns:
        dict[str, Matrix]: The adjusted matrices.
    """
    # Per bone the swings of itself and its ancestors combined, in armature space
    swings: Dict[str, Matrix] = {}
    snapped = {}
    for pose_bone in hierarchy_order(rig):
        name = pose_bone.name
        swing = Matrix.Identity(4)
        if pose_bone.parent:
            swing = swings[pose_bone.parent.name]
        matrix = swing @ reference[name]

        direction = directions.get(original_name(pose_bone))
        if direction:
            current_direction = matrix.to_3x3() @ Vector((0, 1, 0))
            rotation = current_direction.rotation_difference(direction).to_matrix()
            pivot = Matrix.Translation(matrix.translation)
            own_swing = pivot @ rotation.to_4x4() @ pivot.inverted()
            matrix = own_swing @ matrix
            swing = own_swing @ swing

        swings[name] = swing
        snapped[name] = matrix

    return snapped


def retarget_clip(clip: dict, rig: Object, finger_curl: float = 1.0) -> BoneKeys:
    """Converts the rotations of a clip to local bone transforms of the rig.

    Args:
        clip (dict): Animation clip, see clip.py.
        rig (Object): Human Generator armature object.
        finger_curl (float): Blend between the fingers of the rest pose of the rig
            (0) and the fingers of the clip (1). Defaults to 1.0.

    Returns:
        BoneKeys: Per bone name a list of rotation quaternions, one per frame, and
            for the root bone also a list of locations. These are the matrix_basis
            values of the bones.
    """
    reference = reference_pose(rig, clip)
    rest = {bone.name: bone.matrix_local for bone in rig.data.bones}
    bone_names = {
        original_name(pose_bone): pose_bone.name for pose_bone in rig.pose.bones
    }
    clip_rotations = {
        name: [Quaternion(q) for q in quaternions]
        for name, quaternions in clip["rotations"].items()
        if name in bone_names
    }
    _smooth_spine(clip_rotations)
    rotations = {bone_names[name]: quats for name, quats in clip_rotations.items()}
    root = bone_names[ROOT_BONE]
    location_scale = leg_length(rig) / clip["reference_leg_length"]

    # Bones in the T-pose json without clip data hold their reference pose
    driven = set(rotations)
    driven.update(bone_names[name] for name in load_t_pose() if name in bone_names)
    ordered = [
        pose_bone for pose_bone in hierarchy_order(rig) if pose_bone.name in driven
    ]

    keys: BoneKeys = {
        pose_bone.name: ([], [] if pose_bone.name == root else None)
        for pose_bone in ordered
    }
    for frame in range(clip["frame_count"]):
        matrices: Dict[str, Matrix] = {}
        for pose_bone in ordered:
            name = pose_bone.name
            # A game rig has a root bone above the hips, which is not animated
            # and holds its rest pose, so the hips are the top of the animation
            parent_name = pose_bone.parent.name if pose_bone.parent else None
            if parent_name in matrices:
                local_rest = rest[parent_name].inverted() @ rest[name]
                parent_matrix = matrices[parent_name] @ local_rest
                # Children stay attached to their parent, only the root moves
                location = parent_matrix.translation
            else:
                parent_name = None
                parent_matrix = rest[name]
                location = reference[name].translation + (
                    Vector(clip["root_location"][frame]) * location_scale
                )

            if name in rotations:
                delta = rotations[name][frame].to_matrix()
                rotation = delta @ reference[name].to_3x3()
            elif parent_name:
                # Bones without clip data hold their local reference pose, so they
                # move along with their parent
                reference_parent = reference[parent_name] @ local_rest
                reference_basis = reference_parent.inverted() @ reference[name]
                rotation = (parent_matrix @ reference_basis).to_3x3()
            else:
                rotation = reference[name].to_3x3()
            matrix = Matrix.LocRotScale(location, rotation, None)
            matrices[name] = matrix

            basis = parent_matrix.inverted() @ matrix
            bone_rotations, bone_locations = keys[name]
            bone_rotations.append(basis.to_quaternion())
            if bone_locations is not None:
                bone_locations.append(basis.translation)

    _blend_fingers_to_rest(keys, bone_names, finger_curl)
    for bone_rotations, _ in keys.values():
        _make_continuous(bone_rotations)

    return keys


def _smooth_spine(rotations: Rotations) -> None:
    """Spreads the bend between the first and last spine bone over the chain.

    The first and last bone keep their rotation, so the hips and the chest with the
    arms stay where the animation puts them.
    """
    if any(name not in rotations for name in SPINE_CHAIN):
        return
    first, last = rotations[SPINE_CHAIN[0]], rotations[SPINE_CHAIN[-1]]
    identity = Quaternion()
    steps = len(SPINE_CHAIN) - 1
    for frame, (hips, chest) in enumerate(zip(first, last)):
        bend = chest @ hips.inverted()
        for step, name in enumerate(SPINE_CHAIN[1:-1], start=1):
            rotations[name][frame] = identity.slerp(bend, step / steps) @ hips


def _blend_fingers_to_rest(
    keys: BoneKeys, bone_names: Dict[str, str], factor: float
) -> None:
    """Blends the local rotation of the finger bones towards the rest pose.

    The rest pose of the human has relaxed, slightly bent fingers, which look
    better than a clenched game fist on the hands of the human.
    """
    if factor == 1:
        return
    identity = Quaternion()
    for chain in FINGER_CHAINS:
        for original in chain[1:]:
            name = bone_names.get(original)
            if name not in keys:
                continue
            rotations = keys[name][0]
            for frame, rotation in enumerate(rotations):
                rotations[frame] = identity.slerp(rotation, factor)


def _make_continuous(quaternions: List[Quaternion]) -> None:
    """Flips quaternions so consecutive ones interpolate the short way."""
    for previous, current in zip(quaternions, quaternions[1:]):
        if previous.dot(current) < 0:
            current.negate()


def resample_keys(keys: BoneKeys, frame_scale: float) -> BoneKeys:
    """Resamples keys from one per clip frame to one per whole scene frame.

    The clip is stretched to the nearest whole number of scene frames, so all keys
    land on whole frames, which are easier to edit than subframe keys. The last
    key, which is the same as the first one for cyclic animations, stays on the
    last frame so loops stay seamless.

    Args:
        keys (BoneKeys): Output of retarget_clip.
        frame_scale (float): Scene frames per clip frame, to convert frame rates.

    Returns:
        BoneKeys: Keys with one value per scene frame.
    """
    if frame_scale == 1 or not keys:
        return keys
    clip_count = len(next(iter(keys.values()))[0])
    if clip_count < 2:
        return keys
    scene_count = max(1, round((clip_count - 1) * frame_scale)) + 1
    step = (clip_count - 1) / (scene_count - 1)

    resampled: BoneKeys = {}
    for name, (rotations, locations) in keys.items():
        new_rotations = []
        new_locations: Optional[List[Vector]] = [] if locations is not None else None
        for i in range(scene_count):
            position = i * step
            index = min(int(position), clip_count - 2)
            factor = min(max(position - index, 0.0), 1.0)
            new_rotations.append(rotations[index].slerp(rotations[index + 1], factor))
            if locations is not None and new_locations is not None:
                new_locations.append(
                    locations[index].lerp(locations[index + 1], factor)
                )
        resampled[name] = (new_rotations, new_locations)

    return resampled


def new_action(rig: Object, name: str) -> bpy.types.Action:
    """Creates an empty action with a slot for the rig, not assigned to anything.

    Args:
        rig (Object): Armature object the action is for.
        name (str): Name of the new action.

    Returns:
        bpy.types.Action: The created action.
    """
    action = bpy.data.actions.new(name)
    if hasattr(action, "slots"):
        slot = action.slots.new("OBJECT", rig.name)
        strip = action.layers.new("Layer").strips.new(type="KEYFRAME")
        strip.channelbag(slot, ensure=True)
    return action


def _channels(action: bpy.types.Action) -> Tuple[Any, Any]:
    """The fcurve and group collections of an action, for slotted and legacy actions."""
    if hasattr(action, "slots"):
        channelbag = action.layers[0].strips[0].channelbag(action.slots[0], ensure=True)
        return channelbag.fcurves, channelbag.groups
    return action.fcurves, action.groups


def _data_paths(keys: BoneKeys) -> List[str]:
    """Data paths of the fcurves the keys are written to."""
    paths = []
    for bone_name, (_, locations) in keys.items():
        paths.append(f'pose.bones["{bone_name}"].rotation_quaternion')
        if locations is not None:
            paths.append(f'pose.bones["{bone_name}"].location')
    return paths


def keyed_frame_start(action: bpy.types.Action, keys: BoneKeys) -> Optional[int]:
    """First frame of the channels in the action that the keys would replace.

    Args:
        action (bpy.types.Action): Action to look in.
        keys (BoneKeys): Output of retarget_clip.

    Returns:
        Optional[int]: The frame, None if the action has none of these channels.
    """
    paths = set(_data_paths(keys))
    fcurves, _ = _channels(action)
    firsts = [
        fcurve.keyframe_points[0].co.x
        for fcurve in fcurves
        if fcurve.data_path in paths and fcurve.keyframe_points
    ]
    return round(min(firsts)) if firsts else None


def write_keys(
    action: bpy.types.Action,
    rig: Object,
    keys: BoneKeys,
    frame_start: int,
    loop: bool,
) -> None:
    """Writes bone keys to an action, replacing the channels of these bones.

    Channels of other bones and properties, like ones added by the user, stay as
    they are. So does everything else of the action: its name, fake user and the
    NLA strips that use it.

    Args:
        action (bpy.types.Action): Action to write to, see new_action.
        rig (Object): Armature object the action animates.
        keys (BoneKeys): Output of retarget_clip, one key per scene frame.
        frame_start (int): Scene frame of the first key.
        loop (bool): Make the animation repeat before and after its frame range.
    """
    fcurves, groups = _channels(action)
    paths = set(_data_paths(keys))
    for fcurve in [f for f in fcurves if f.data_path in paths]:
        fcurves.remove(fcurve)

    for bone_name, (rotations, locations) in keys.items():
        pose_bone: PoseBone = rig.pose.bones[bone_name]
        pose_bone.rotation_mode = "QUATERNION"
        group = groups.get(bone_name) or groups.new(bone_name)
        frames = [frame_start + i for i in range(len(rotations))]
        channels = [(f'pose.bones["{bone_name}"].rotation_quaternion', rotations)]
        if locations is not None:
            channels.append((f'pose.bones["{bone_name}"].location', locations))

        for data_path, values in channels:
            for index in range(len(values[0])):
                fcurve = fcurves.new(data_path, index=index)
                fcurve.group = group
                fcurve.keyframe_points.add(len(values))
                coords = [
                    c
                    for frame, value in zip(frames, values)
                    for c in (frame, value[index])
                ]
                fcurve.keyframe_points.foreach_set("co", coords)
                if loop:
                    fcurve.modifiers.new("CYCLES")
                fcurve.update()
