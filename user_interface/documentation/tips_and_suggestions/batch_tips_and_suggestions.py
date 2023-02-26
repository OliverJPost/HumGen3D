# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy

from .tip_baseclasses import Tip, URLOperator


def get_batch_tips_from_context(context, sett, human):

    markers = [o for o in bpy.data.objects if "hg_marker" in o]
    if not markers:
        yield no_markers_in_scene


no_markers_in_scene = Tip(
    title="No markers in scene?",
    text="""If the purple button says
"Generate 0 Humans", add some
Human Generator markers from
the Add Object (Shift+A) menu.
""",
)
