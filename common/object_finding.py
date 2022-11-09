"""Contains public functions for finding Humans from Blender objects."""

from typing import Iterable, Optional, Set

from bpy.types import Object  # type:ignore


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
    """From a list of objects, find rig objects belonging to HG humans (not legacy).

    Args:
        objects (Iterable[Object]): List of objects to check for if they're part of a
            HG human

    Returns:
        Set[Object]: Set of armatures of humans (hg_rig).
    """
    return {r for r in [find_hg_rig(obj) for obj in objects] if r}
