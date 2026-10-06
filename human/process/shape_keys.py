# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Decides which shape keys end up on a processed human.

Every key of the human belongs to a group, like the face rig or the body
proportions. Each group is either kept as shape keys, baked into the mesh at its
current value or removed. Live keys are not shape keys, so keeping them means
converting them to shape keys first.
"""

from typing import TYPE_CHECKING, Iterable, Literal, Optional

import bpy

from HumGen3D.common.decorators import injected_context
from HumGen3D.common.objects import bake_shape_key, remove_shape_key
from HumGen3D.common.type_aliases import C
from HumGen3D.human.hair import hair_binding
from HumGen3D.human.hair.hair_binding import EXPRESSION_KEY_PREFIXES

if TYPE_CHECKING:
    from HumGen3D.human.human import Human
    from HumGen3D.human.keys.keys import KeyItem, LiveKeyItem, ShapeKeyItem

KeyAction = Literal["keep", "bake", "remove"]

KEY_ACTIONS = [
    ("keep", "Keep", "Keep these as shape keys on the processed human", 0),
    ("bake", "Bake", "Apply the current values to the mesh and remove the keys", 1),
    ("remove", "Remove", "Remove these keys, undoing what they do to the mesh", 2),
]

# Identifier, label and description of each group, in the order of the interface
KEY_GROUPS = [
    (
        "face_rig",
        "Face rig",
        "FACS shape keys driven by the face bones, loaded if the human has no face "
        "rig yet",
    ),
    ("expressions", "Expressions", "The 1-click expression presets"),
    (
        "correctives",
        "Correctives",
        "Keys driven by the bones that fix the joints and the eyelids",
    ),
    ("body", "Body proportions", "Body sliders, including the muscle sliders"),
    ("face", "Face proportions", "Face sliders, face presets and the eye sliders"),
    ("age", "Age", "The aging sliders"),
]
# The face rig can only be loaded or removed, its keys are at rest in rest pose
GROUP_ACTIONS = {"face_rig": ("keep", "remove")}
# Keys that bones drive, these stop working when exported without their drivers
DRIVEN_GROUPS = ("face_rig", "correctives")

CORRECTIVE_KEY_PREFIXES = ("cor_", "eyeLook")
# Set by the height system together with the rig, so they are always baked
HEIGHT_KEY_NAMES = ("height_150", "height_200")
# Clothing holds its fit to this human in this key
CLOTHING_FIT_KEY = "Body Proportions"


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


def key_groups(human: "Human") -> dict[str, list["KeyItem"]]:
    """All livekeys and shape keys of the human, per group.

    Args:
        human (Human): Human to list the keys of.

    Returns:
        dict[str, list[KeyItem]]: Keys per group identifier of KEY_GROUPS. The
            face rig group is empty when no face rig is loaded.
    """
    groups: dict[str, list["KeyItem"]] = {group: [] for group, *_ in KEY_GROUPS}
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


@injected_context
def process_shape_keys(
    human: "Human",
    face_rig: KeyAction = "keep",
    expressions: KeyAction = "keep",
    correctives: KeyAction = "keep",
    body: KeyAction = "bake",
    face: KeyAction = "bake",
    age: KeyAction = "bake",
    context: C = None,
) -> None:
    """Keeps, bakes or removes each group of keys of the human, see KEY_GROUPS.

    Keeping livekeys converts them to shape keys with their current value. The
    livekeys and the gender key are always baked into the mesh afterwards, as is
    the fit of the clothing. Keys outside the groups are left alone.

    Args:
        human (Human): Human to process, this changes the human itself.
        face_rig (KeyAction): "keep" loads the face rig if the human has none,
            "remove" removes it. Baking is not possible.
        expressions (KeyAction): Action for the 1-click expressions.
        correctives (KeyAction): Action for the corrective and eye look keys,
            also on the clothing.
        body (KeyAction): Action for the body proportion keys.
        face (KeyAction): Action for the face proportion keys.
        age (KeyAction): Action for the age keys.
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

    # Removing comes first: refitting the rig and the clothing to the changed body
    # needs the livekeys, which are converted and baked afterwards
    human.keys.fold_temp_key()
    shape_changed = _remove_livekeys(human, actions)
    shape_changed |= _process_body_shapekeys(human, actions, "remove")
    if shape_changed:
        human.keys.update_human_from_key_change(context)

    _convert_livekeys(human, actions)
    bake_live_keys(human)
    _process_body_shapekeys(human, actions, "bake")
    _process_clothing_shapekeys(human, actions["correctives"])
    _bake_all_shapekeys(human.objects.eyes)

    if actions["face_rig"] == "keep" and not human.expression.has_facial_rig:
        human.expression.load_facial_rig(context, reset_expressions=False)
    elif actions["face_rig"] == "remove" and human.expression.has_facial_rig:
        human.expression.remove_facial_rig()

    hair_binding.sync_haircards(human)


def _livekey_actions(human: "Human", actions: dict[str, str]):
    for livekey in human.keys.all_livekeys:
        group = livekey_group(livekey)
        yield livekey, (actions[group] if group else "bake")


def _remove_livekeys(human: "Human", actions: dict[str, str]) -> bool:
    """Resets the livekeys to remove, returns whether the body changed shape."""
    shape_changed = False
    for livekey, action in _livekey_actions(human, actions):
        if action == "remove" and livekey.value:
            livekey.set_without_update(0)
            shape_changed = True

    return shape_changed


def _convert_livekeys(human: "Human", actions: dict[str, str]) -> None:
    """Converts the livekeys to keep into shape keys with their current value."""
    for livekey, action in _livekey_actions(human, actions):
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
    human: "Human", actions: dict[str, str], pass_action: str
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
        action = actions[group] if group else "keep"
        if action != pass_action:
            continue

        sk = shapekey.as_bpy()
        if action == "remove" and sk.value and not sk.mute:
            shape_changed = True
        for obj, obj_sk in _with_haircard_keys(human, sk):
            if action == "bake":
                bake_shape_key(obj_sk, obj)
            else:
                remove_shape_key(obj_sk, obj)

    return shape_changed


def _with_haircard_keys(
    human: "Human", body_sk: bpy.types.ShapeKey
) -> list[tuple[bpy.types.Object, bpy.types.ShapeKey]]:
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


def _process_clothing_shapekeys(human: "Human", correctives: str) -> None:
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
                if correctives == "bake":
                    bake_shape_key(sk, obj)
                elif correctives == "remove":
                    remove_shape_key(sk, obj)
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


def driven_groups_kept(actions: Iterable[tuple[str, str]]) -> list[str]:
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
