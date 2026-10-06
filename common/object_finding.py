"""Contains public functions for finding Humans from Blender objects."""

from typing import Iterable, Optional, Set

from bpy.types import Object  # type:ignore

# Custom properties on the rig object of humans
PROCESSED_KEY = "hg_processed"
HUMAN_ID_KEY = "hg_id"
ORIGINAL_ID_KEY = "hg_original_id"


def is_legacy(obj: Object) -> bool:
    """Check if this object is part of a human created with HG V3 or earlier.

    Args:
        obj (Object): Blender object to check. Can be any object part of human

    Returns:
        bool: True if legacy human, False if not Human or not legacy human
    """
    rig_obj = find_hg_rig(obj, include_legacy=True)
    if not rig_obj:
        return False
    return not hasattr(rig_obj.HG, "version") or tuple(rig_obj.HG.version) == (
        3,
        0,
        0,
    )


def is_part_of_human(obj: Object, include_legacy: bool = False) -> bool:
    """Check if this object is part of a HG human.

    Args:
        obj (Object): Object to check for if it's part of a HG human
        include_legacy (bool): If False, Humans created before HG V4 will not be
            recognized.

    Returns:
        bool: True if part of human
    """
    return bool(find_hg_rig(obj, include_legacy=include_legacy))


def find_hg_rig(  # noqa
    obj: Object,
    include_legacy: bool = False,
) -> Optional[Object]:
    """Checks if passed object is part of a HG human. Does NOT return an instance.

    Args:
        obj (Object): Object to check for if it's part of a HG human
        include_legacy (bool): Whether to find rigs of humans created with Human
            Generator V3 or earlier.

    Returns:
        Object: Armature of human (hg_rig) or None if not part of human (or body
        object if the human is an applied batch result and
        include_applied_batch_results is True)
    """
    if obj and obj.HG.ishuman:
        rig_obj = obj
    elif obj and obj.parent and obj.parent.HG.ishuman:
        rig_obj = obj.parent
    else:
        return None

    if (
        not hasattr(rig_obj.HG, "version") or tuple(rig_obj.HG.version) == (3, 0, 0)
    ) and not include_legacy:
        return None

    return rig_obj


def find_multiple_in_list(objects: Iterable[Object]) -> Set[Object]:
    """From a list of objects, find rig objects belonging to editable HG humans.

    Legacy humans and processed humans are not included.

    Args:
        objects (Iterable[Object]): List of objects to check for if they're part of a
            HG human

    Returns:
        Set[Object]: Set of armatures of humans (hg_rig).
    """
    rigs = {r for r in [find_hg_rig(obj) for obj in objects] if r}
    return {rig for rig in rigs if PROCESSED_KEY not in rig}


def is_processed(obj: Object) -> bool:
    """Check if this object is part of a processed human.

    Processed humans are the frozen results of the process system, they can't be
    edited with Human Generator anymore.

    Args:
        obj (Object): Blender object to check. Can be any object part of human

    Returns:
        bool: True if processed human, False if not Human or not processed
    """
    rig_obj = find_hg_rig(obj)
    return bool(rig_obj and PROCESSED_KEY in rig_obj)


def find_original_rig(obj: Object, objects: Iterable[Object]) -> Optional[Object]:
    """Finds the human a processed human was made from.

    Args:
        obj (Object): Object that is part of the processed human.
        objects (Iterable[Object]): Objects to search the original human in.

    Returns:
        Optional[Object]: Armature of the original human, None if this is not a
            processed human or the original human is not among the objects.
    """
    rig_obj = find_hg_rig(obj)
    original_id = rig_obj.get(ORIGINAL_ID_KEY) if rig_obj else None
    if not original_id:
        return None

    return next(
        (
            other_obj
            for other_obj in objects
            if other_obj.HG.ishuman
            and other_obj.get(HUMAN_ID_KEY) == original_id
            and PROCESSED_KEY not in other_obj
        ),
        None,
    )
