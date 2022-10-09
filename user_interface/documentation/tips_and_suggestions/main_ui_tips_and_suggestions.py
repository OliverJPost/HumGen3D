# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy


def get_main_ui_tips_from_context(context, sett, hg_rig):
    yield main_tutorial


main_tutorial = [
    "Quickstart tutorial",
    "HELP",
    """You can find the quick start
guide again here:
""",
    (
        "WINDOW",
        "hg3d.draw_tutorial",
        "Open tutorial in Blender",
        "tutorial_name",
        "get_started_tutorial",
    ),
]
