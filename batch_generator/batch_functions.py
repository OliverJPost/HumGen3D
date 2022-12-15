# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from typing import TYPE_CHECKING, Union, no_type_check

import bpy  # type:ignore
import numpy as np

if TYPE_CHECKING:
    from HumGen3D.backend.properties.batch_props import BatchProps


def height_from_bell_curve(
    average_height_cm: int,
    one_sd: float,
    random_seed: bool = True,
    samples: int = 1,
) -> list[float]:
    """Returns one or multiple samples from a bell curve generated from the
    batch_average_height and batch_standard_deviation properties.

    Args:
        sett (PropertyGroup): HumGen props
        gender (str): 'male' or 'female', determines the gender specific
            batch_average_height prop
        random_seed (bool, optional): Used by the example list to make sure the
            list doesn't update all the time. Defaults to True.
        samples (int, optional): Amount of length samples to draw. Defaults to 0.

    Returns:
        list: with the default 0 samples it returns a single length value
            in centimeters, else it returns a list of length values in cm
    """
    if random_seed:
        np.random.seed()
    else:
        np.random.seed(0)

    return list(
        np.random.normal(
            loc=average_height_cm, scale=average_height_cm * one_sd, size=samples
        )
    )


def to_percentage(base: Union[int, float], end_result: Union[int, float]) -> int:
    return int((base + end_result) / base * 100)


def _get_tag_from_dict(
    total: Union[int, float], tag_dict: dict[str, int], fallback: str
) -> str:
    return next(
        (tag for tag, ubound in tag_dict.items() if total < ubound),
        fallback,
    )


@no_type_check
def get_batch_marker_list(context: bpy.types.Context) -> list[bpy.types.Object]:
    batch_sett = context.scene.HG3D.batch  # type:ignore[attr-defined]

    marker_selection = batch_sett.marker_selection

    all_markers = [obj for obj in bpy.data.objects if "hg_batch_marker" in obj]

    if marker_selection == "all":
        return all_markers

    elif marker_selection == "selected":
        return [o for o in all_markers if o in context.selected_objects]

    else:
        # Empty markers
        return [o for o in all_markers if not has_associated_human(o)]


@no_type_check
def has_associated_human(marker: bpy.types.Object) -> bool:
    """Check if this marker has an associated human and if that object still exists.

    Args:
        marker (Object): marker object to check for associated human

    Returns:
        bool: True if associated human was found, False if not
    """
    if "associated_human" not in marker or not bool(marker["associated_human"]):
        return False

    # Check if object still exists
    if not bpy.data.objects.get(marker["associated_human"].name):
        return False

    same_location = marker.location == marker["associated_human"].location
    object_in_scene = bpy.context.scene.objects.get(marker["associated_human"].name)

    return same_location and object_in_scene
