# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import os
from typing import TYPE_CHECKING, Optional, Union, no_type_check

import bpy  # type:ignore
import numpy as np
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.backend.preview_collections import PREVIEW_COLLECTION_DATA
from HumGen3D.backend.type_aliases import GenderStr

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


# FIXME
def calculate_batch_statistics(batch_sett: "BatchProps") -> dict[str, str]:  # noqa
    """Calculates performance statistidcs of batch generator settings.

    Returns values to show the user how their choices in the batch settings
    will impact the render times, memory usage and filesize. Good luck reading
    this function, it's a bit of a mess.

    Args:
        batch_sett (BatchProps): Addon batch properties

    Returns:
        dict: Dict with strings that explain to the user what the impact is
    """
    eevee_time = 0.0
    eevee_memory = 0.0
    cycles_time = 0.0
    cycles_memory = 0.0
    scene_memory = 0.0
    storage_weight = 0.0

    if batch_sett.hair:
        storage_weight += 10
        p_quality = batch_sett.hair_quality_particle
        if p_quality == "high":
            eevee_time += 1.58
            eevee_memory += 320
            cycles_time += 2.0
            cycles_memory += 280
            scene_memory += 357
        elif p_quality == "medium":
            eevee_time += 0
            eevee_memory += 180
            cycles_time += 0.29
            cycles_memory += 36
            scene_memory += 182
        elif p_quality == "low":
            eevee_time += 0
            eevee_memory += 100
            cycles_time += 0.25
            cycles_memory += 22
            scene_memory += 122
        else:
            eevee_time += 0
            eevee_memory += 100
            cycles_time += 0.25
            cycles_memory += 10
            scene_memory += 122

    if batch_sett.clothing:
        storage_weight += 8
        scene_memory += 180
        if batch_sett.apply_clothing_geometry_masks:
            storage_weight -= 1

    if batch_sett.texture_resolution == "high":
        if batch_sett.clothing:
            eevee_time += 11.31
            eevee_memory += 2120
            cycles_time += 1.88
            cycles_memory += 1182
    elif batch_sett.texture_resolution == "optimised":
        if batch_sett.clothing:
            eevee_time -= 1.81
            eevee_memory -= 310
            cycles_time += 0.31
            cycles_memory -= 140
        else:
            eevee_time -= 3.63
            eevee_memory -= 654
            cycles_time -= 0.23
            cycles_memory -= 330
    elif batch_sett.texture_resolution == "performance":
        if batch_sett.clothing:
            eevee_time -= 2.86
            eevee_memory -= 523
            cycles_time += 0.11
            cycles_memory -= 271
        else:
            eevee_time -= 3.75
            eevee_memory -= 700
            cycles_time -= 0.48
            cycles_memory -= 352

    if batch_sett.delete_backup:
        storage_weight -= 42
        eevee_memory -= 250
        scene_memory -= 240

    if batch_sett.apply_shapekeys:
        storage_weight -= 6
        eevee_time -= 0.2
        eevee_memory -= 60
        cycles_memory -= 64
        scene_memory -= 47
        if batch_sett.apply_armature_modifier:
            storage_weight -= 2
            scene_memory -= 27

    cycles_time_total = to_percentage(4.40, cycles_time)
    cycles_time_tags = {"Fastest": 95, "Fast": 100, "Normal": 120, "Slow": 150}
    cycles_time_tag = _get_tag_from_dict(cycles_time_total, cycles_time_tags, "Slowest")

    cycles_memory_total = int((563 + cycles_memory) / 3)
    cycles_memory_tags = {
        "Lightest": 60,
        "Light": 80,
        "Normal": 100,
        "Heavy": 180,
    }
    cycles_memory_tag = _get_tag_from_dict(
        cycles_memory_total, cycles_memory_tags, "Heaviest"
    )

    eevee_time_total = to_percentage(6.57, eevee_time)
    eevee_time_tags = {"Fastest": 50, "Fast": 70, "Normal": 100, "Slow": 150}
    eevee_time_tag = _get_tag_from_dict(eevee_time_total, eevee_time_tags, "Slowest")

    eevee_memory_total = int((1450 + eevee_memory) / 3)
    eevee_memory_tags = {
        "Lightest": 150,
        "Light": 200,
        "Normal": 320,
        "Heavy": 600,
    }
    eevee_memory_tag = _get_tag_from_dict(
        eevee_memory_total, eevee_memory_tags, "Heaviest"
    )

    ram_total = 472 + scene_memory
    ram_tags = {"Light": 250, "Normal": 700}
    ram_tag = _get_tag_from_dict(ram_total, ram_tags, "Heavy")

    statistics_dict = {
        "cycles_time": f"{cycles_time_total}% [{cycles_time_tag}]",
        "cycles_memory": f"{cycles_memory_total} [{cycles_memory_tag}]",
        "eevee_time": f"{eevee_time_total}% [{eevee_time_tag}]",
        "eevee_memory": f"{eevee_memory_total} [{eevee_memory_tag}]",
        "scene_memory": f"{ram_total} [{ram_tag}]",
        "storage": f"~{59+storage_weight} MB/human*",
    }

    return statistics_dict  # noqa PIE781


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


def find_item_amount(  # TODO might be redundant
    context: bpy.types.Context, categ: str, gender: Optional[GenderStr], folder: str
) -> int:
    """used by batch menu, showing the total amount of items of the selected
    categories

    Batch menu currently disabled
    """
    pref = get_prefs()

    if categ == "expression":  # FIXME
        ext = ".npz"
    else:
        ext = ".blend"

    pcoll_folder = PREVIEW_COLLECTION_DATA[categ][2]
    if isinstance(pcoll_folder, list):
        pcoll_folder = os.path.join(*pcoll_folder)

    if gender:
        directory = os.path.join(pref.filepath, pcoll_folder, gender, folder)
    else:
        directory = os.path.join(pref.filepath, pcoll_folder, folder)

    if categ == "outfit":
        sett = context.scene.HG3D  # type:ignore[attr-defined]
        inside = sett.batch.clothing_inside
        outside = sett.batch.clothing_outside
        if inside and not outside:
            ext = "I.blend"
        elif outside and not inside:
            ext = "O.blend"

    return len([name for name in os.listdir(directory) if name.endswith(ext)])
