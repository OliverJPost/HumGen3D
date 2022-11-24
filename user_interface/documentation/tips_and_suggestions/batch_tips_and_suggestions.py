# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy

from .tip_baseclasses import Tip, URLOperator


def get_batch_tips_from_context(context, sett, human):

    yield batch_tutorial

    markers = [o for o in bpy.data.objects if "hg_marker" in o]
    if not markers:
        yield no_markers_in_scene


batch_tutorial = Tip(
    "Batch mode tutorial",
    "You can find the tutorial about the batch mode here:",
    icon="HELP",
    operator=URLOperator(
        "Open tutorial in browser",
        "https://help.humgen3d.com/batch",
    ),
)


no_markers_in_scene = Tip(
    "No markers in scene?",
    """If the purple button says
"Generate 0 Humans", add some
Human Generator markers from
the Add Object (Shift+A) menu.
""",
)
