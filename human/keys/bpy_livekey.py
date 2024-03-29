# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements internal implementation of livekeys."""

from __future__ import annotations

from typing import Any, cast

import bpy
import numpy as np
from bpy.props import FloatProperty, StringProperty  # type:ignore
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.human.human import Human
from HumGen3D.human.keys.key_slider_update import HG3D_OT_SLIDER_SUBSCRIBE
from HumGen3D.human.keys.keys import _get_starting_coordinates


def get_livekey(self: BpyLiveKey) -> float:
    """Get value of livekey from either the temp_key or the stored values on the model.

    Args:
        self: The livekey to get the value of.

    Returns:
        The value of the livekey.
    """
    try:
        human = Human.from_existing(
            bpy.context.object
        )  # TODO better way than bpy.context
    except HumGenException as e:
        raise HumGenException(
            "`as_bpy()` only works when a part of the human is selected in Blender."
        ) from e
    name = self.name
    temp_key = human.keys.temp_key
    current_sk_values = human.props.sk_values
    if temp_key and temp_key.name.replace("LIVE_KEY_TEMP_", "") == name:
        return cast(float, temp_key.value)
    elif name in current_sk_values:
        return cast(float, current_sk_values[name])
    else:
        return 0.0


def set_livekey(self: BpyLiveKey, value: float) -> None:
    """Set the value of this live key in a way optimised for realtime changing.

    This method will load the live key into a temporary shape key that stays on
    the model until another live key's value is changed. This costs more performance
    for the first change, but much less for subsequent changes of the value.

    Args:
        self: The livekey to set the value of.
        value: The value to set the livekey to.

    Raises:
        HumGenException: If the active object is not part of a human.
    """
    name = self.name
    try:
        human = Human.from_existing(
            bpy.context.object
        )  # TODO better way than bpy.context
    except HumGenException as e:
        raise HumGenException(
            "`as_bpy()` only works when a part of the human is selected in Blender."
        ) from e

    # If the value was not changed, for example by the user exiting the value
    # typing modal, then do nothing. This prevents crash.
    try:
        found_value = human.props.sk_values[name]
    except KeyError:
        found_value = 0
    if name not in human.props.sk_values:
        if value == 0:
            return
    elif round(value, 3) == round(found_value, 3):
        return

    temp_key = human.keys.temp_key

    # Change value of existing temp_key if it matches the changing key
    if temp_key and temp_key.name.replace("LIVE_KEY_TEMP_", "") == name:
        # If the value was not changed, for example by the user exiting the value
        # typing modal, then do nothing. This prevents crash.
        if round(temp_key.value, 3) != round(value, 3):
            temp_key.value = value
            human.props.sk_values[name] = value
            _run_modal()
        return

    (
        vert_count,
        obj_coords,
        new_key_relative_coords,
        new_key_coords,
    ) = _get_starting_coordinates(human, self.path)

    permanent_key_coords = np.empty(vert_count * 3, dtype=np.float64)
    human.keys.permanent_key.data.foreach_get("co", permanent_key_coords)
    permanent_key_coords = _add_temp_key_to_permanent_key_coords(
        human, temp_key, vert_count, obj_coords, permanent_key_coords
    )

    # Correct for previous value if this shape key has been added before
    current_sk_values = human.props.sk_values
    if temp_key and name in current_sk_values:
        old_value = current_sk_values[name]
        permanent_key_coords -= new_key_relative_coords * old_value

    # Write the coordinates to the permanent_key
    human.keys.permanent_key.data.foreach_set("co", permanent_key_coords)

    # Write the coordinates to the temp_key
    human.keys.temp_key.data.foreach_set("co", new_key_coords)
    human.keys.temp_key.name = "LIVE_KEY_TEMP_" + name

    temp_key.value = value

    human.props.sk_values[name] = value

    _run_modal()


def _run_modal() -> None:
    if not HG3D_OT_SLIDER_SUBSCRIBE.is_running():
        bpy.ops.hg3d.slider_subscribe("INVOKE_DEFAULT")


def _add_temp_key_to_permanent_key_coords(
    human: "Human",
    temp_key: bpy.types.ShapeKey,
    vert_count: int,
    obj_coords: np.ndarray,
    permanent_key_coords: np.ndarray,
) -> np.ndarray:
    temp_key_coords = np.empty(vert_count * 3, dtype=np.float64)
    human.keys.temp_key.data.foreach_get("co", temp_key_coords)

    relative_temp_coords = temp_key_coords - obj_coords
    permanent_key_coords += relative_temp_coords * temp_key.value

    old_temp_key_name = temp_key.name.replace("LIVE_KEY_TEMP_", "")
    human.props.sk_values[old_temp_key_name] = temp_key.value
    return permanent_key_coords


class BpyLiveKey(bpy.types.PropertyGroup):
    """Internal representation of a livekey stored in CollectionProperty.

    This is a shape key that is not on the model but loaded from an external file.
    """

    path: StringProperty()
    category: StringProperty()
    subcategory: StringProperty()
    name: StringProperty()
    gender: StringProperty()
    value: FloatProperty(
        default=0,
        min=-10,
        max=10,
        soft_min=-2,
        soft_max=2,
        get=get_livekey,
        set=set_livekey,
    )
    value_limited: FloatProperty(
        default=0,
        min=-10,
        max=10,
        soft_min=-1,
        soft_max=1,
        get=get_livekey,
        set=set_livekey,
    )
    value_positive_limited: FloatProperty(
        default=0,
        min=-10,
        max=10,
        soft_min=0,
        soft_max=1,
        get=get_livekey,
        set=set_livekey,
    )
