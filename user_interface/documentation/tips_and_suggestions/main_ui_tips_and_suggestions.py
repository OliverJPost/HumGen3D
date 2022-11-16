# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE


from HumGen3D.user_interface.documentation.tips_and_suggestions.tip_baseclasses import (
    Tip,
    TutorialOperator,
)


def get_main_ui_tips_from_context(context, sett, human):
    yield main_tutorial


main_tutorial = Tip(
    "Quickstart tutorial",
    "You can find the quick start guide again here:",
    icon="HELP",
    operator=TutorialOperator("Open tutorial in Blender", "get_started_tutorial"),
)
