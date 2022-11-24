# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE


from HumGen3D.user_interface.documentation.tips_and_suggestions.tip_baseclasses import (
    Tip,
    URLOperator,
)


def get_main_ui_tips_from_context(context, sett, human):
    yield main_tutorial


main_tutorial = Tip(
    "Documentation",
    "You can find the HG documentation here:",
    icon="HELP",
    operator=URLOperator("Open website", "https://help.humgen3d.com"),
)
