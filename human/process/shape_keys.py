# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Decides which shape keys end up on a processed human.

Every key of the human belongs to a group, like the face rig or the body
proportions. Each group is either kept as shape keys, baked into the mesh at its
current value or removed. Live keys are not shape keys, so keeping them means
converting them to shape keys first. Keeping can be limited to a selection of
the keys of a group; the face rig and the 1-click expressions are loaded from
the library when kept, so the selection is made from everything available.
"""

import json
import os
from typing import TYPE_CHECKING, Dict, Iterable, List, Literal, Optional

import bpy

from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.objects import bake_shape_key, remove_shape_key
from HumGen3D.common.type_aliases import C
from HumGen3D.human.hair import hair_binding
from HumGen3D.human.hair.hair_binding import EXPRESSION_KEY_PREFIXES

if TYPE_CHECKING:
    from HumGen3D.human.human import Human
    from HumGen3D.human.keys.keys import KeyItem, LiveKeyItem, ShapeKeyItem

KeyAction = Literal["keep", "bake", "remove"]
# Per group the names of the keys to keep, None for all of them
KeepSelection = Dict[str, Optional[List[str]]]

KEY_ACTIONS = [
    ("keep", "Keep", "Keep these as shape keys on the processed human", 0),
    ("bake", "Bake", "Apply the current values to the mesh and remove the keys", 1),
    ("remove", "Remove", "Remove these keys, undoing what they do to the mesh", 2),
]

# Identifier, label and description of each group, in the order of the interface
KEY_GROUPS = [
    (
        "face_rig",
        "Face rig / FACS",
        "FACS shape keys driven by the face bones, loaded from the library when kept",
    ),
    (
        "expressions",
        "1-click expressions",
        "The expression presets of the library, loaded when kept",
    ),
    (
        "correctives",
        "Correctives",
        "Keys driven by the bones that fix the joints and the eyelids",
    ),
    ("body", "Body proportions", "Body sliders, including the muscle sliders"),
    ("face", "Face proportions", "Face sliders, face presets and the eye sliders"),
    ("age", "Age", "The aging sliders"),
]
# Groups that can't be baked: the driven keys are at rest in rest pose, the
# expressions are loaded from the library
GROUP_ACTIONS = {
    "face_rig": ("keep", "remove"),
    "expressions": ("keep", "remove"),
    "correctives": ("keep", "remove"),
}
# What happens to the keys of a kept group that are not in its selection
UNSELECTED_ACTION = {
    "face_rig": "remove",
    "expressions": "remove",
    "correctives": "remove",
    "body": "bake",
    "face": "bake",
    "age": "bake",
}
# Keys that bones drive, these stop working when exported without their drivers
DRIVEN_GROUPS = ("face_rig", "correctives")
# Groups whose keys come from the library instead of from the human
LIBRARY_GROUPS = ("face_rig", "expressions")

CORRECTIVE_KEY_PREFIXES = ("cor_", "eyeLook")
# Set by the height system together with the rig, so they are always baked
HEIGHT_KEY_NAMES = ("height_150", "height_200")
# Clothing holds its fit to this human in this key
CLOTHING_FIT_KEY = "Body Proportions"
FACE_RIG_FILE = os.path.join("models", "face_rig.json")

_facs_names: List[str] = []


def facs_key_names() -> List[str]:
    """Names of the FACS keys of the face rig, from the library file."""
    if not _facs_names:
        path = os.path.join(get_prefs().filepath, FACE_RIG_FILE)
        try:
            with open(path, "r") as f:
                _facs_names.extend(json.load(f)["body"].keys())
        except (OSError, KeyError, ValueError):
            return []
    return list(_facs_names)


def expression_options(human: "Human", context: C = None) -> List[str]:
    """Preset paths of every 1-click expression in the library."""
    return [
        option
        for option in human.expression.get_options(context=context)
        if option != "none"
    ]


def expression_name(preset_or_key: str) -> str:
    """Display name of an expression, from its preset path or its key name."""
    name = os.path.splitext(os.path.basename(preset_or_key))[0]
    for prefix in EXPRESSION_KEY_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def key_display_name(group: str, name: str) -> str:
    """Name of a key as the interface lists it."""
    return expression_name(name) if group == "expressions" else name


def livekey_group(key: "LiveKeyItem") -> Optional[str]:
    """The group a livekey belongs to, None if it is always baked."""
    if key.name in HEIGHT_KEY_NAMES:
        return None
    return _category_group(key.category, key.subcategory)


def shapekey_group(key: "ShapeKeyItem", driven_names: set[str]) -> Optional[str]:
    """The group a shape key of the body belongs to, None if it is left alone.

    Args:
        key (ShapeKeyItem): Shape key on the body.
        driven_names (set[str]): Names of the body keys that have a driver.
    """
    name = key.as_bpy().name
    if name.startswith(CORRECTIVE_KEY_PREFIXES):
        return "correctives"
    if name.startswith(EXPRESSION_KEY_PREFIXES):
        return "expressions"
    # The face rig keys are the only other driven keys
    if name in driven_names:
        return "face_rig"
    return _category_group(key.category, key.subcategory)


def _category_group(category: str, subcategory: Optional[str]) -> Optional[str]:
    if category == "body_proportions":
        return "body"
    if category in ("face_proportions", "face_presets", "presets"):
        return "face"
    if category == "special":
        return "age" if (subcategory or "").lower() == "age" else "face"
    return None


def driven_key_names(obj: bpy.types.Object) -> set[str]:
    """Names of the shape keys of an object that have a driver on their value."""
    keys = obj.data.shape_keys
    if not keys or not keys.animation_data:
        return set()
    names = set()
    for fcurve in keys.animation_data.drivers:
        path = fcurve.data_path
        if path.startswith('key_blocks["') and path.endswith('"].value'):
            names.add(bpy.utils.unescape_identifier(path[12:-8]))
    return names


def key_groups(human: "Human") -> Dict[str, List["KeyItem"]]:
    """All livekeys and shape keys of the human, per group.

    Args:
        human (Human): Human to list the keys of.

    Returns:
        dict[str, list[KeyItem]]: Keys per group identifier of KEY_GROUPS. The
            face rig group is empty when no face rig is loaded.
    """
    groups: Dict[str, List["KeyItem"]] = {group: [] for group, *_ in KEY_GROUPS}
    for livekey in human.keys.all_livekeys:
        group = livekey_group(livekey)
        if group:
            groups[group].append(livekey)

    driven_names = driven_key_names(human.objects.body)
    for shapekey in human.keys.all_shapekeys:
        group = shapekey_group(shapekey, driven_names)
        if group:
            groups[group].append(shapekey)

    return groups


def keep_options(human: "Human", context: C = None) -> Dict[str, List[str]]:
    """The keys a user can choose to keep, per group, by display name.

    The face rig and the expressions list everything in the library, the other
    groups what the human has.
    """
    options = {
        group: [key_display_name(group, _key_name(key)) for key in keys]
        for group, keys in key_groups(human).items()
    }
    options["face_rig"] = facs_key_names()
    options["expressions"] = [
        expression_name(preset) for preset in expression_options(human, context)
    ]
    return options


def _key_name(key: "KeyItem") -> str:
    return key.as_bpy().name if hasattr(key, "as_bpy") else key.name


@injected_context
def process_shape_keys(  # noqa: CCR001
    human: "Human",
    face_rig: KeyAction = "keep",
    expressions: KeyAction = "keep",
    correctives: KeyAction = "keep",
    body: KeyAction = "bake",
    face: KeyAction = "bake",
    age: KeyAction = "bake",
    keep: Optional[KeepSelection] = None,
    context: C = None,
) -> None:
    """Keeps, bakes or removes each group of keys of the human, see KEY_GROUPS.

    Keeping livekeys converts them to shape keys with their current value. The
    livekeys and the gender key are always baked into the mesh afterwards, as is
    the fit of the clothing. Keys outside the groups are left alone. The face rig
    and the 1-click expressions are loaded from the library when kept.

    Args:
        human (Human): Human to process, this changes the human itself.
        face_rig (KeyAction): "keep" loads the face rig, "remove" removes it.
        expressions (KeyAction): "keep" loads the expressions of the library,
            "remove" removes them.
        correctives (KeyAction): Action for the corrective and eye look keys,
            also on the clothing.
        body (KeyAction): Action for the body proportion keys.
        face (KeyAction): Action for the face proportion keys.
        age (KeyAction): Action for the age keys.
        keep (Optional[KeepSelection]): Per group the display names of the keys
            to keep, see keep_options. Groups not in it keep all their keys.
            Unselected keys of a kept group are removed, or baked for the
            slider groups.
        context (C): Blender context. bpy.context if not provided.

    Raises:
        ValueError: If an action is not possible for a group.
    """
    actions = {
        "face_rig": face_rig,
        "expressions": expressions,
        "correctives": correctives,
        "body": body,
        "face": face,
        "age": age,
    }
    for group, action in actions.items():
        if action not in GROUP_ACTIONS.get(group, ("keep", "bake", "remove")):
            raise ValueError(f"Cannot {action} the {group} keys")
    keep = keep or {}

    if actions["face_rig"] == "keep" and not human.expression.has_facial_rig:
        human.expression.load_facial_rig(context, reset_expressions=False)
    if actions["expressions"] == "keep":
        load_expressions(human, keep.get("expressions"), context)

    # Removing comes first: refitting the rig and the clothing to the changed body
    # needs the livekeys, which are converted and baked afterwards
    human.keys.fold_temp_key()
    shape_changed = _remove_livekeys(human, actions, keep)
    shape_changed |= _process_body_shapekeys(human, actions, keep, "remove")
    if shape_changed:
        human.keys.update_human_from_key_change(context)

    _convert_livekeys(human, actions, keep)
    bake_live_keys(human)
    _process_body_shapekeys(human, actions, keep, "bake")
    _process_clothing_shapekeys(human, actions["correctives"], keep.get("correctives"))
    _bake_all_shapekeys(human.objects.eyes)

    if actions["face_rig"] == "remove" and human.expression.has_facial_rig:
        human.expression.remove_facial_rig()

    hair_binding.sync_haircards(human)


@injected_context
def load_expressions(
    human: "Human", names: Optional[Iterable[str]] = None, context: C = None
) -> None:
    """Adds expressions of the library as shape keys, at value 0.

    Expressions the human already has keep their value.

    Args:
        human (Human): Human to add the keys to.
        names (Optional[Iterable[str]]): Display names of the expressions, see
            expression_name. None adds every expression of the library.
        context (C): Blender context. bpy.context if not provided.
    """
    wanted = None if names is None else set(names)
    values = {key.as_bpy().name: key.value for key in human.expression.keys}
    for preset in expression_options(human, context):
        if wanted is None or expression_name(preset) in wanted:
            human.expression.set(preset)
    for key in human.expression.keys:
        key.value = values.get(key.as_bpy().name, 0)
    hair_binding.sync_haircards(human)


def _action_for(
    group: str, name: str, actions: Dict[str, str], keep: KeepSelection
) -> str:
    """The action for one key: that of its group, unless it is kept and not selected."""
    action = actions[group]
    selection = keep.get(group)
    if action == "keep" and selection is not None:
        if key_display_name(group, name) not in selection:
            return UNSELECTED_ACTION[group]
    return action


def _livekey_actions(human: "Human", actions: Dict[str, str], keep: KeepSelection):
    for livekey in human.keys.all_livekeys:
        group = livekey_group(livekey)
        yield livekey, (_action_for(group, livekey.name, actions, keep) if group else "bake")


def _remove_livekeys(human: "Human", actions: Dict[str, str], keep: KeepSelection) -> bool:
    """Resets the livekeys to remove, returns whether the body changed shape."""
    shape_changed = False
    for livekey, action in _livekey_actions(human, actions, keep):
        if action == "remove" and livekey.value:
            livekey.set_without_update(0)
            shape_changed = True

    return shape_changed


def _convert_livekeys(human: "Human", actions: Dict[str, str], keep: KeepSelection) -> None:
    """Converts the livekeys to keep into shape keys with their current value."""
    for livekey, action in _livekey_actions(human, actions, keep):
        if action == "keep":
            livekey.to_shapekey(transfer_value=True)


def bake_live_keys(human: "Human") -> None:
    """Bakes the gender key and the livekeys into the mesh of the body."""
    body = human.objects.body
    if not body.data.shape_keys:
        return
    for sk in list(body.data.shape_keys.key_blocks):
        if sk.name == "Male" or sk.name.startswith("LIVE_KEY"):
            bake_shape_key(sk, body)


def _process_body_shapekeys(
    human: "Human", actions: Dict[str, str], keep: KeepSelection, pass_action: str
) -> bool:
    """Bakes or removes the shape keys of the body with the passed action.

    Returns:
        bool: Whether the shape of the body changed.
    """
    body = human.objects.body
    driven_names = driven_key_names(body)
    shape_changed = False
    for shapekey in human.keys.all_shapekeys:
        group = shapekey_group(shapekey, driven_names)
        sk = shapekey.as_bpy()
        action = _action_for(group, sk.name, actions, keep) if group else "keep"
        if action != pass_action:
            continue

        if action == "remove" and sk.value and not sk.mute:
            shape_changed = True
        for obj, obj_sk in _with_haircard_keys(human, sk):
            if action == "bake":
                bake_shape_key(obj_sk, obj)
            else:
                _remove_key_and_driver(obj_sk, obj)

    return shape_changed


def _remove_key_and_driver(sk: bpy.types.ShapeKey, obj: bpy.types.Object) -> None:
    """Removes a shape key with the driver on its value, if it has one."""
    keys = obj.data.shape_keys
    if keys and keys.animation_data:
        path = f'key_blocks["{bpy.utils.escape_identifier(sk.name)}"].value'
        for fcurve in list(keys.animation_data.drivers):
            if fcurve.data_path == path:
                keys.animation_data.drivers.remove(fcurve)
    remove_shape_key(sk, obj)


def _with_haircard_keys(
    human: "Human", body_sk: bpy.types.ShapeKey
) -> List[tuple[bpy.types.Object, bpy.types.ShapeKey]]:
    """The keys of the haircards that follow a body key, then the body key itself.

    The hair keys come first as their drivers point at the body key.
    """
    pairs = []
    for hair_obj in human.objects.haircards:
        hair_keys = hair_obj.data.shape_keys
        if hair_keys and body_sk.name in hair_keys.key_blocks:
            pairs.append((hair_obj, hair_keys.key_blocks[body_sk.name]))
    pairs.append((human.objects.body, body_sk))
    return pairs


def _process_clothing_shapekeys(
    human: "Human", correctives: str, selection: Optional[List[str]]
) -> None:
    """Bakes the fit of the clothing and handles its corrective keys."""
    for obj in human.clothing.outfit.objects + human.clothing.footwear.objects:
        keys = obj.data.shape_keys
        if not keys:
            continue
        for sk in list(keys.key_blocks):
            if sk == keys.reference_key:
                continue
            if sk.name == CLOTHING_FIT_KEY:
                bake_shape_key(sk, obj)
            elif sk.name.startswith(CORRECTIVE_KEY_PREFIXES):
                action = correctives
                if action == "keep" and selection is not None and sk.name not in selection:
                    action = UNSELECTED_ACTION["correctives"]
                if action == "bake":
                    bake_shape_key(sk, obj)
                elif action == "remove":
                    _remove_key_and_driver(sk, obj)
        _remove_basis_if_alone(obj)


def _bake_all_shapekeys(obj: bpy.types.Object) -> None:
    keys = obj.data.shape_keys
    if not keys:
        return
    for sk in list(keys.key_blocks):
        if sk != keys.reference_key:
            bake_shape_key(sk, obj)
    _remove_basis_if_alone(obj)


def _remove_basis_if_alone(obj: bpy.types.Object) -> None:
    keys = obj.data.shape_keys
    if keys and len(keys.key_blocks) == 1:
        obj.shape_key_clear()


def driven_groups_kept(actions: Iterable[tuple[str, str]]) -> List[str]:
    """Labels of the kept groups whose keys need their drivers to work.

    Args:
        actions (Iterable[tuple[str, str]]): Pairs of group identifier and action.

    Returns:
        list[str]: Labels from KEY_GROUPS, empty if none are kept.
    """
    labels = {group: label for group, label, _ in KEY_GROUPS}
    return [
        labels[group]
        for group, action in actions
        if group in DRIVEN_GROUPS and action == "keep"
    ]
