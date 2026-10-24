# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Module for functions related to Blender's render engines Cycles and Eevee"""

import bpy
from ..common.compatibility import EEVEE_RENDER_ENGINE

def set_eevee_ao_and_strip(context: bpy.types.Context) -> None:
    """Set eevee's AO and strip settings to the best looking configuration for hair.

    Args:
        context (bpy.types.Context): Blender context
    """
    current_render_engine = str(context.scene.render.engine)
    context.scene.render.engine = EEVEE_RENDER_ENGINE
    if bpy.app.version < (4, 4, 0):
        context.scene.eevee.use_gtao = True
    context.scene.render.hair_type = "STRIP"
    context.scene.render.engine = current_render_engine


# Transparent surfaces Cycles lets a ray pass before it stops it as black. Hair
# cards stack more than Blender's default of 8, which showed the hair dark and
# blotchy in Cycles
CARD_TRANSPARENT_BOUNCES = 64


def set_cycles_transparent_bounces(context: bpy.types.Context) -> None:
    """Raise the transparent bounces of Cycles so hair cards render fully.

    A higher value set by the user is kept.

    Args:
        context (bpy.types.Context): Blender context
    """
    cycles = getattr(context.scene, "cycles", None)
    if cycles is not None and cycles.transparent_max_bounces < CARD_TRANSPARENT_BOUNCES:
        cycles.transparent_max_bounces = CARD_TRANSPARENT_BOUNCES
