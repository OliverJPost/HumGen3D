# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
from enum import Enum

from HumGen3D.user_interface.documentation.tips_and_suggestions.tip_baseclasses import (
    Tip,
    URLOperator,
)

# String enum of possible active sections
class ActiveSection(str, Enum):
    """Enum of possible active sections."""

    BODY = "body"
    AGE = "age"
    FACE = "face"
    HEIGHT = "height"
    SKIN = "skin"
    HAIR = "hair"
    CLOTHING = "clothing"
    POSE = "pose"
    EXPRESSION = "expression"


CLOTHING_MATERIAL_MENU_TIP = Tip(
    title="Clothing Materials",
    text="""By selecting a clothing object, the Human Generator
interface will change to the clothing material menu.

This menu allows you to change the colors of the clothing
and also add patterns to it.""",
)

HAIR_RENDER_TIP = Tip(
    title="Hair Rendering",
    text="""It looks like you are using Cycles.
For the best results, set the hair rendering to
"Accurate" instead of "Fast".

NOTE: This setting looks better in Cycles, but
does not show correctly in the material preview.
""",
)

A_LOT_OF_EXPRESSIONS_TIP = Tip(
    title="Many Expressions",
    text="""It looks like you have a lot
(more than 10) expressions loaded on
this human. Consider removing some of
them to improve performance.

You can remove expressions by clicking
the trash icon next to the expression
name in the strength dropdown.
""",
    important=True,
)

TRIAL_HUMAN_TIP = Tip(
    title="Trial Human",
    text="""This human was created using the trial 
version of HumGen. The functionality of the
trial version is almost identical to the full
version, but the trial models and textures
have watermarks/holes.

NOTE: You cannot upgrade a trial human to a
full version human! You will have to create
a new human from scratch after purchasing.

Also, note that the trial version only permits
trial use. Both personal and commercial use
are not permitted.

Want to purchase a full version? Click the
link below to go to the BlenderMarket.
""",
    important=True,
    operator =
        URLOperator(
            url="https://blendermarket.com/products/humgen3d",
            text="Shop page",
        )

)


def get_main_ui_tips_from_context(context, sett, human):
    active_tab = sett.ui.phase

    if human.is_trial:
        yield TRIAL_HUMAN_TIP

    if active_tab == ActiveSection.CLOTHING and human.clothing.outfit.objects:
        yield CLOTHING_MATERIAL_MENU_TIP

    if (
        active_tab == ActiveSection.HAIR
        and context.scene.render.engine == "CYCLES"
        and sett.hair_shader_type == "fast"
    ):

        yield HAIR_RENDER_TIP

    if active_tab == ActiveSection.EXPRESSION and len(human.expression.keys) > 10:
        yield A_LOT_OF_EXPRESSIONS_TIP