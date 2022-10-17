# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from __future__ import annotations

import os
from typing import Any, cast

import bpy
import numpy as np
from bpy.props import FloatProperty, StringProperty
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.human.base.exceptions import HumGenException
from HumGen3D.human.height.armature_update import HG3D_OT_SLIDER_SUBSCRIBE
from HumGen3D.human.human import Human
from HumGen3D.human.keys.keys import import_npz_key


def get_livekey(self: BpyLiveKey) -> float:
    """Get the value of the livekey from either the temp_key or the stored values on the
    model."""
    human = Human.from_existing(bpy.context.object)  # TODO better way than bpy.context
    name = self.name
    temp_key = human.keys.temp_key
    current_sk_values = human.props.sk_values
    if temp_key and temp_key.name.endswith(name):
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
    """

    name = self.name
    human = Human.from_existing(bpy.context.object)  # TODO better way than bpy.context
    if not human:
        raise HumGenException("No active human")

    temp_key = human.keys.temp_key
    # Change value of existing temp_key if it matches the changing key
    if temp_key and temp_key.name.endswith(name):
        temp_key.value = value
        run_modal()
        return

    # Get coordinates of base human mesh
    body = human.body_obj
    vert_count = len(body.data.vertices)
    obj_coords = np.empty(vert_count * 3, dtype=np.float64)
    body.data.vertices.foreach_get("co", obj_coords)

    # Load coordinates of livekey that is being changed
    filepath = os.path.join(get_prefs().filepath, self.path)
    new_key_relative_coords = import_npz_key(vert_count, filepath)

    new_key_coords = obj_coords + new_key_relative_coords
    # If there was a previous livekey on the temp_key, correct for it
    if temp_key:
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

    # Add a new temp_key if it didn't exist already
    if not temp_key:
        temp_key = human.body_obj.shape_key_add(name="LIVE_KEY_TEMP_" + name)
        temp_key.slider_max = 10
        temp_key.slider_min = -10

    # Write the coordinates to the temp_key
    human.keys.temp_key.data.foreach_set("co", new_key_coords)
    human.keys.temp_key.name = "LIVE_KEY_TEMP_" + name

    temp_key.value = value

    run_modal()


def run_modal() -> None:
    if not HG3D_OT_SLIDER_SUBSCRIBE.is_running():
        bpy.ops.hg3d.slider_subscribe("INVOKE_DEFAULT")  # , hide_armature=True)


def _add_temp_key_to_permanent_key_coords(
    human: "Human",
    temp_key: bpy.types.ShapeKey,
    vert_count: int,
    obj_coords: np.ndarray[Any, Any],
    permanent_key_coords: np.ndarray[Any, Any],
) -> np.ndarray[Any, Any]:
    temp_key_coords = np.empty(vert_count * 3, dtype=np.float64)
    human.keys.temp_key.data.foreach_get("co", temp_key_coords)

    relative_temp_coords = temp_key_coords - obj_coords
    permanent_key_coords += relative_temp_coords * temp_key.value

    old_temp_key_name = temp_key.name.replace("LIVE_KEY_TEMP_", "")
    human.props.sk_values[old_temp_key_name] = temp_key.value
    return permanent_key_coords


class BpyLiveKey(bpy.types.PropertyGroup):
    """Representation of a livekey, a shape key that is not on the model but loaded from
    an external file."""

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
