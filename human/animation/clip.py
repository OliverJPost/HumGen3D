# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Reading and writing of animation clip files.

A clip stores an animation independent of the rig it was made on. For every bone
it stores, per frame, the rotation of the bone in armature space relative to the
rotation of that bone in a reference pose. The reference pose is a T-pose with the
palms facing down and the feet flat on the ground. Applying a clip to a rig only
needs the pose of that rig in the same reference pose, see retarget.py.

Bones are named after the bones of the Human Generator rig. The root bone also
stores its location in armature space, relative to the reference pose, in meters.
It is scaled to the leg length of the rig the clip is applied to, so feet stay on
the ground for humans of different proportions.

File layout (json):
    {
        "format_version": 1,
        "source": "...", "license": "...",
        "fps": 30,
        "frame_count": 41,
        "loop": true,
        "root_motion": false,
        "reference_leg_length": 0.829,
        "reference_directions": {"spine": [x, y, z], ...},
        "rotations": {"spine": [[w, x, y, z], ...], "thigh.L": [...], ...},
        "root_location": [[x, y, z], ...]
    }

The reference directions are the directions of the bones in the reference pose of
the rig the clip was made on. They are optional, the retargeting uses them to point
the fingers of the human the same way.
"""

import json
from typing import Any, Dict, List

FORMAT_VERSION = 1
ROOT_BONE = "spine"
LEG_BONES = ("thigh", "shin")

# Keys of a clip dict that end up in the file, in this order
CLIP_KEYS = (
    "format_version",
    "source",
    "license",
    "fps",
    "frame_count",
    "loop",
    "root_motion",
    "reference_leg_length",
    "reference_directions",
    "rotations",
    "root_location",
)


def write_clip(path: str, clip: Dict[str, Any]) -> None:
    """Writes a clip dict to a json file.

    Args:
        path (str): Path of the file to write.
        clip (dict): Clip in the layout described in the module docstring. The
            rotations and locations can be mathutils types or sequences.
    """
    serializable = {
        "rotations": {
            bone_name: [_round(q) for q in quaternions]
            for bone_name, quaternions in clip["rotations"].items()
        },
        "root_location": [_round(loc) for loc in clip["root_location"]],
        "reference_directions": {
            bone_name: _round(direction)
            for bone_name, direction in clip.get("reference_directions", {}).items()
        },
    }
    for key in CLIP_KEYS:
        if key not in serializable:
            serializable[key] = clip[key]

    with open(path, "w") as f:
        ordered = {key: serializable[key] for key in CLIP_KEYS}
        json.dump(ordered, f, separators=(",", ":"))


def read_clip(path: str) -> Dict[str, Any]:
    """Reads a clip json file.

    Args:
        path (str): Path of the file to read.

    Returns:
        dict: Clip in the layout described in the module docstring.

    Raises:
        ValueError: If the file is not a clip or has an unsupported version.
    """
    with open(path, "r") as f:
        clip = json.load(f)

    if clip.get("format_version") != FORMAT_VERSION:
        raise ValueError(f"Unsupported animation clip version in {path}")
    frame_count = clip["frame_count"]
    if len(clip["root_location"]) != frame_count or any(
        len(quaternions) != frame_count for quaternions in clip["rotations"].values()
    ):
        raise ValueError(f"Animation clip {path} has an inconsistent frame count")

    return clip


def _round(values: Any, digits: int = 5) -> List[float]:
    return [round(float(v), digits) for v in values]
