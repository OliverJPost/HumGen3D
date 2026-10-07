# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Converts the rig of a processed human to a skeleton for game engines.

The Human Generator rig is a Rigify metarig: every bone is flagged as deforming,
the face rig and the eye targets are control bones and the hips are the root.
Game engines want the opposite, a plain hierarchy of bones that all deform the
mesh, under a root bone at the origin, without constraints or drivers. The
conversion strips the bones that deform nothing, merges the weights of bones the
user does not want into their parents, adds the root bone, limits the number of
bones per vertex and renames the bones for the chosen engine.

The presets in game_rig_presets.json only differ in names, root bone, rest pose
and export settings. The source human is never changed, the conversion runs on
the duplicate the process system makes.
"""

import json
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator, Optional

import bmesh
import bpy
from HumGen3D.backend.preferences.preference_func import get_addon_root
from HumGen3D.common import is_legacy
from HumGen3D.common.exceptions import HumGenException
from mathutils import Matrix

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

GAME_RIG_KEY = "game_rig"
# Names of the bone groups a user can merge into their parents, with the
# original names of the bones they hold, without side suffix
MERGEABLE_BONES = {
    "eyes": ("eyeball",),
    "jaw": ("jaw", "jaw_upper"),
    "breasts": ("breast",),
    "metacarpals": ("palm.01", "palm.02", "palm.03", "palm.04"),
}
SIDE_SUFFIXES = (".L", ".R", "_L", "_R")
# Points along the Y axis, so the rest matrix of the root bone is the identity
ROOT_BONE_LENGTH = 0.2

# Identifier, name and description of the units the exported file is in
UNIT_ITEMS = [
    ("meters", "Meters", "Blender units, what Unity, Godot and Mixamo expect", 0),
    (
        "centimeters",
        "Centimeters",
        "Unreal Engine units, written to FBX without a scale on the armature",
        1,
    ),
]
# Identifier, name and description of the rest poses
REST_POSE_ITEMS = [
    ("a_pose", "A-pose", "Keep the A-pose as rest pose, as Unreal expects", 0),
    (
        "t_pose",
        "T-pose",
        "Make the T-pose the rest pose, as Unity, Godot, VRM and most retargeting"
        " tools expect",
        1,
    ),
]
# Identifier, name and description of the bones per vertex limits
INFLUENCE_LIMITS = [
    ("4", "4", "The default of Unity and Unreal, supported everywhere", 4),
    ("8", "8", "Smoother deformation, needs the higher limit enabled in the engine", 8),
    ("2", "2", "For mobile and VR, where the engines often clamp to two bones", 2),
    ("0", "Unlimited", "Keep all weights, the engine decides what to drop", 0),
]


def _load_presets() -> dict[str, dict[str, Any]]:
    path = os.path.join(get_addon_root(), "human", "process", "game_rig_presets.json")
    with open(path, "r") as f:
        return json.load(f)  # type:ignore[no-any-return]


PRESETS = _load_presets()
CUSTOM_PRESET = "custom"
# Identifier, name, description and value, in the order of the file
PRESET_ITEMS = [
    (identifier, preset["label"], preset["description"], i)
    for i, (identifier, preset) in enumerate(PRESETS.items())
]


def get_preset(preset: str, names_file: Optional[str] = None) -> dict[str, Any]:
    """Settings of a game rig preset.

    Args:
        preset (str): Identifier of the preset, see PRESETS, or "custom" for a
            names profile file.
        names_file (Optional[str]): Path of a JSON file with "names" and
            "sides" like the presets, for the "custom" preset.

    Returns:
        dict[str, Any]: Rest pose, root bone name, side tokens, bone names and
            FBX export settings of the preset.

    Raises:
        ValueError: If the preset does not exist.
        HumGenException: If the names file can't be read.
    """
    if preset == CUSTOM_PRESET:
        return _load_names_file(names_file)
    if preset not in PRESETS:
        raise ValueError(f"Preset has to be one of {tuple(PRESETS)}")
    return PRESETS[preset]


def _load_names_file(path: Optional[str]) -> dict[str, Any]:
    """A custom names profile: the names and sides of a preset, in a user file."""
    if not path or not os.path.isfile(path):
        raise HumGenException(f"Bone names file not found: {path}")
    with open(path, "r") as f:
        data = json.load(f)
    if "names" not in data:
        raise HumGenException(f"Bone names file {path} has no 'names'")
    profile = dict(PRESETS["generic_a"])
    profile["names"] = data["names"]
    profile["sides"] = data.get("sides", PRESETS["generic_a"]["sides"])
    return profile


def preset_for_names(names: str, rest_pose: str = "a_pose") -> str:
    """The preset identifier for a names profile of the settings.

    Args:
        names (str): "humanoid", "unreal", "mixamo", "humgen" or "custom".
        rest_pose (str): Picks the generic preset for the HumGen names.
    """
    if names == "humgen":
        return "generic_t" if rest_pose == "t_pose" else "generic_a"
    return names


def fbx_export_settings(units: str) -> dict[str, Any]:
    """Keyword arguments for ExportBuilder.to_fbx that write the file in these units.

    Args:
        units (str): "meters" or "centimeters", see UNIT_ITEMS.

    Returns:
        dict[str, Any]: Empty for meters. Centimeters apply the FBX unit scale to
            the objects, so Unreal imports the armature at scale 1.
    """
    if units == "centimeters":
        return {"apply_scale_options": "FBX_SCALE_ALL"}
    return {}


def convert_to_game_rig(
    human: "Human",
    context: bpy.types.Context,
    preset: str = "generic_a",
    keep_eyes: bool = True,
    keep_jaw: bool = True,
    keep_breasts: bool = True,
    keep_metacarpals: bool = False,
    max_influences: int = 4,
    root_bone: Optional[bool] = None,
    root_bone_name: Optional[str] = None,
    names_file: Optional[str] = None,
) -> None:
    """Converts the rig of this human to a skeleton for game engines.

    Removes the bones that deform no mesh, like the face rig controls and the eye
    targets, and bakes the current values of the shape keys they drove. Merges
    the weights of the optional bones into their parents, adds a root bone at the
    origin, bakes the constraints into the pose and removes them, removes the
    vertex groups that are not bones or in use, limits the bones per vertex and
    renames the bones for the preset. Bones keep their "original_name" property,
    so the other process steps still find them.

    Args:
        human (Human): Human to convert the rig of.
        context (bpy.types.Context): Blender context.
        preset (str): Engine to name the bones for, see PRESETS.
        keep_eyes (bool): Keep the eye bones, otherwise the eyes follow the head.
        keep_jaw (bool): Keep the jaw bones that move the teeth.
        keep_breasts (bool): Keep the breast bones.
        keep_metacarpals (bool): Keep the palm bones between hand and fingers.
        max_influences (int): Maximum number of bones per vertex, 0 for no limit.
        root_bone (Optional[bool]): Add a root bone at the origin. None uses the
            choice of the preset.
        root_bone_name (Optional[str]): Name of the root bone, None uses the name
            of the preset.
        names_file (Optional[str]): Names profile file for the "custom" preset,
            see get_preset.

    Raises:
        HumGenException: If the human is a Rigify or legacy human, or already has
            a game rig.
        ValueError: If the preset does not exist.
    """
    preset_data = get_preset(preset, names_file)
    rig = human.objects.rig
    if human.pose.rigify.is_rigify:
        raise HumGenException("Can't make a game rig of a Rigify human.")
    if is_legacy(rig):
        raise HumGenException("Can't make a game rig of a legacy human.")
    if GAME_RIG_KEY in rig:
        raise HumGenException("Human already has a game rig.")

    merge_bases = set()
    for group, keep in (
        ("eyes", keep_eyes),
        ("jaw", keep_jaw),
        ("breasts", keep_breasts),
        ("metacarpals", keep_metacarpals),
    ):
        if not keep:
            merge_bases.update(MERGEABLE_BONES[group])

    meshes = _skinned_meshes(human, rig)
    weighted_names = _weighted_group_names(meshes)
    removed = {
        bone.name
        for bone in rig.data.bones
        if bone.name not in weighted_names
        or _split_side(_original_name(bone))[0] in merge_bases
    }
    merge_targets = _merge_targets(rig, removed)

    _bake_drivers(human, rig, removed, context)

    with _rig_active(rig, context):
        _bake_constraints(rig, context)
        for obj in meshes:
            _merge_weights(obj, merge_targets)
        _remove_bones(rig, removed, merge_targets)

        add_root = preset_data["root_bone"] if root_bone is None else root_bone
        if add_root:
            _add_root_bone(rig, root_bone_name or preset_data["root_bone"] or "root")

        # Before the bones are renamed, so the groups of the bones are known by
        # their current names, and no leftover group can take a new bone name
        for obj in meshes:
            _remove_unused_vertex_groups(obj, rig)
            _free_vertex_group_names(obj, rig, preset_data)
        _rename_bones(rig, preset_data)

    for obj in meshes:
        if max_influences:
            _limit_influences(obj, rig, max_influences)

    _remove_rigify_properties(rig)
    _remove_empty_bone_collections(rig)
    rig[GAME_RIG_KEY] = names_file if preset == CUSTOM_PRESET else preset


def _skinned_meshes(human: "Human", rig: bpy.types.Object) -> list[bpy.types.Object]:
    return [
        obj
        for obj in human.objects
        if obj.type == "MESH"
        and any(m.type == "ARMATURE" and m.object == rig for m in obj.modifiers)
    ]


def _weighted_group_names(meshes: list[bpy.types.Object]) -> set[str]:
    """Names of the vertex groups that have weight on at least one vertex."""
    names = set()
    for obj in meshes:
        used = set()
        for vertex in obj.data.vertices:
            for group in vertex.groups:
                if group.weight > 0:
                    used.add(group.group)
        names.update(obj.vertex_groups[index].name for index in used)
    return names


def _original_name(bone: bpy.types.Bone) -> str:
    return str(bone.get("original_name", bone.name))


def _split_side(name: str) -> tuple[str, Optional[str]]:
    """Splits "upper_arm.L" into ("upper_arm", "L"), names without side get None."""
    if name.endswith(SIDE_SUFFIXES):
        return name[:-2], name[-1]
    return name, None


def _merge_targets(rig: bpy.types.Object, removed: set[str]) -> dict[str, Optional[str]]:
    """The closest kept ancestor of every removed bone, None if there is none."""
    targets = {}
    for name in removed:
        parent = rig.data.bones[name].parent
        while parent and parent.name in removed:
            parent = parent.parent
        targets[name] = parent.name if parent else None
    return targets


def _bake_drivers(
    human: "Human",
    rig: bpy.types.Object,
    removed: set[str],
    context: bpy.types.Context,
) -> None:
    """Replaces the drivers that read removed bones by their current values.

    The face rig and eye look keys are driven by the face bones, these keys stay
    as plain shape keys at the value they have now.
    """
    depsgraph = context.evaluated_depsgraph_get()
    depsgraph.update()
    for obj in human.objects:
        if obj.type != "MESH" or not obj.data.shape_keys:
            continue
        key = obj.data.shape_keys
        if not key.animation_data:
            continue
        key_eval = obj.evaluated_get(depsgraph).data.shape_keys

        for fcurve in key.animation_data.drivers[:]:
            reads_removed = any(
                target.id == rig and target.bone_target in removed
                for variable in fcurve.driver.variables
                for target in variable.targets
            )
            if not reads_removed:
                continue
            data_path = fcurve.data_path
            try:
                value = key_eval.path_resolve(data_path)
                key_block = key.path_resolve(data_path.rsplit(".", 1)[0])
            except ValueError:
                # The driver points at a key that does not exist anymore
                key.animation_data.drivers.remove(fcurve)
                continue
            key.animation_data.drivers.remove(fcurve)
            key_block.value = value


@contextmanager
def _rig_active(rig: bpy.types.Object, context: bpy.types.Context) -> Iterator[None]:
    """Makes the rig the only selected, active object in object mode, restores after."""
    old_active = context.view_layer.objects.active
    old_selected = list(context.selected_objects)
    for obj in old_selected:
        obj.select_set(False)
    rig.hide_viewport = False
    rig.hide_set(False)
    rig.select_set(True)
    context.view_layer.objects.active = rig
    try:
        yield
    finally:
        if rig.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        rig.select_set(False)
        for obj in old_selected:
            obj.select_set(True)
        context.view_layer.objects.active = old_active


def _bake_constraints(rig: bpy.types.Object, context: bpy.types.Context) -> None:
    """Writes the pose the constraints give into the bones and removes them.

    The scale is dropped, as the stretch constraints of the spine would otherwise
    end up as a scale on the bones.
    """
    constrained = [pose_bone for pose_bone in rig.pose.bones if pose_bone.constraints]
    if not constrained:
        return

    context.view_layer.update()
    matrices = {pose_bone.name: pose_bone.matrix.copy() for pose_bone in constrained}
    for pose_bone in constrained:
        for constraint in pose_bone.constraints[:]:
            pose_bone.constraints.remove(constraint)

    # Parents first, as the matrix of a bone depends on the pose of its parent
    constrained.sort(key=lambda pose_bone: len(pose_bone.parent_recursive))
    for pose_bone in constrained:
        location, rotation, _ = matrices[pose_bone.name].decompose()
        pose_bone.matrix = Matrix.LocRotScale(location, rotation, None)
        context.view_layer.update()


def _merge_weights(obj: bpy.types.Object, merge_targets: dict[str, Optional[str]]) -> None:
    """Adds the weights of the removed bones to their kept ancestors."""
    for source_name, target_name in merge_targets.items():
        source = obj.vertex_groups.get(source_name)
        if not source:
            continue
        if target_name:
            weights = []
            for vertex in obj.data.vertices:
                for group in vertex.groups:
                    if group.group == source.index and group.weight > 0:
                        weights.append((vertex.index, group.weight))
            target = obj.vertex_groups.get(target_name)
            if not target:
                target = obj.vertex_groups.new(name=target_name)
            for index, weight in weights:
                target.add([index], weight, "ADD")
        obj.vertex_groups.remove(source)


def _remove_bones(
    rig: bpy.types.Object, removed: set[str], merge_targets: dict[str, Optional[str]]
) -> None:
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = rig.data.edit_bones
    for name in removed:
        target_name = merge_targets[name]
        for child in edit_bones[name].children:
            if child.name in removed:
                continue
            child.use_connect = False
            child.parent = edit_bones[target_name] if target_name else None
    for name in removed:
        edit_bones.remove(edit_bones[name])
    bpy.ops.object.mode_set(mode="OBJECT")


def _add_root_bone(rig: bpy.types.Object, name: str) -> None:
    """Adds a bone at the origin and parents the bones without parent to it."""
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = rig.data.edit_bones
    orphans = [bone for bone in edit_bones if not bone.parent]
    root = edit_bones.new(name)
    root.head = (0, 0, 0)
    root.tail = (0, ROOT_BONE_LENGTH, 0)
    root.roll = 0
    for bone in orphans:
        bone.use_connect = False
        bone.parent = root
    bpy.ops.object.mode_set(mode="OBJECT")

    bone = rig.data.bones[name]
    # Nothing is weighted to the root, it only carries the motion of the character
    bone.use_deform = False
    rig.pose.bones[name]["original_name"] = name


def _new_bone_names(rig: bpy.types.Object, preset_data: dict[str, Any]) -> dict[str, str]:
    """The name every bone gets from the preset, by its current name."""
    names = preset_data["names"]
    sides = preset_data["sides"]
    new_names = {}
    for pose_bone in rig.pose.bones:
        base, side = _split_side(_original_name(pose_bone.bone))
        template = names.get(base)
        if not template:
            continue
        new_name = template.format(**sides[side]) if side else template
        if new_name != pose_bone.name:
            new_names[pose_bone.name] = new_name
    return new_names


def _free_vertex_group_names(
    obj: bpy.types.Object, rig: bpy.types.Object, preset_data: dict[str, Any]
) -> None:
    """Renames vertex groups that are not bones but hold a new bone name.

    Blender refuses to rename the group of a bone when another group has the
    new name already, which would leave the bone without weights.
    """
    bone_names = {bone.name for bone in rig.data.bones}
    for new_name in _new_bone_names(rig, preset_data).values():
        group = obj.vertex_groups.get(new_name)
        if group and group.name not in bone_names:
            group.name = new_name + ".group"


def _rename_bones(rig: bpy.types.Object, preset_data: dict[str, Any]) -> None:
    """Renames the bones for the preset, by their original name.

    Blender renames the vertex groups and driver targets along with the bones.
    Bones the preset has no name for keep their name.
    """
    for old_name, new_name in _new_bone_names(rig, preset_data).items():
        rig.pose.bones[old_name].name = new_name


def _referenced_vertex_groups(obj: bpy.types.Object) -> set[str]:
    """Names of the vertex groups the modifiers, hair and shape keys of obj use."""
    names = set()
    for modifier in obj.modifiers:
        for attr in ("vertex_group", "mask_vertex_group"):
            names.add(getattr(modifier, attr, ""))
    for particle_system in obj.particle_systems:
        for attr in dir(particle_system):
            if attr.startswith("vertex_group_"):
                names.add(getattr(particle_system, attr))
    if obj.data.shape_keys:
        names.update(sk.vertex_group for sk in obj.data.shape_keys.key_blocks)
    names.discard("")
    return names


def _remove_unused_vertex_groups(obj: bpy.types.Object, rig: bpy.types.Object) -> None:
    """Removes the vertex groups that neither belong to a bone nor are in use.

    The body carries groups Human Generator uses in Blender, like the masks of
    the clothing, the lips and the hair fading, and some groups of bones that no
    longer exist. Groups a modifier, hair system or shape key reads stay, as the
    modifiers are only applied after this step.
    """
    keep = {bone.name for bone in rig.data.bones} | _referenced_vertex_groups(obj)
    for group in obj.vertex_groups[:]:
        if group.name not in keep:
            obj.vertex_groups.remove(group)


def _limit_influences(obj: bpy.types.Object, rig: bpy.types.Object, limit: int) -> None:
    """Keeps the strongest bone weights of each vertex and normalizes them.

    Only the groups of deforming bones are changed, the masks and other groups
    of the body are left alone. Done per vertex here instead of with the
    vertex group operators, which silently do nothing on a human whose shape
    keys were processed.
    """
    bone_names = {bone.name for bone in rig.data.bones if bone.use_deform}
    bone_groups = {
        group.index for group in obj.vertex_groups if group.name in bone_names
    }
    # The deform layer of bmesh holds one weight per group, so vertices with
    # the same group listed twice, which the base mesh has, come out clean
    bm = bmesh.new()  # type:ignore[call-arg]
    bm.from_mesh(obj.data)
    layer = bm.verts.layers.deform.verify()
    for vertex in bm.verts:
        weights = vertex[layer]
        # The base mesh lists some groups twice on a vertex, their weights add up
        bone_weights: dict[int, float] = {}
        other_weights: dict[int, float] = {}
        for group_index, weight in weights.items():
            target = bone_weights if group_index in bone_groups else other_weights
            target[group_index] = target.get(group_index, 0.0) + weight
        if not bone_weights:
            continue
        entries = sorted(
            ((g, w) for g, w in bone_weights.items() if w > 0),
            key=lambda entry: entry[1],
            reverse=True,
        )
        kept = entries[:limit] if limit else entries
        total = sum(weight for _, weight in kept) or 1.0
        weights.clear()
        for group_index, weight in other_weights.items():
            weights[group_index] = weight
        for group_index, weight in kept:
            weights[group_index] = weight / total
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def _remove_rigify_properties(rig: bpy.types.Object) -> None:
    for pose_bone in rig.pose.bones:
        for key in list(pose_bone.keys()):
            if key.startswith("rigify"):
                del pose_bone[key]
    for key in list(rig.data.keys()):
        if key.startswith("rigify"):
            del rig.data[key]


def _remove_empty_bone_collections(rig: bpy.types.Object) -> None:
    for collection in list(rig.data.collections_all):
        if not collection.bones and not collection.children:
            rig.data.collections.remove(collection)
