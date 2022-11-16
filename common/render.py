# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Module for functions related to Blender's render engines Cycles and Eevee"""

import bpy


def set_eevee_ao_and_strip(context: bpy.types.Context) -> None:
    """Set eevee's AO and strip settings to the best looking configuration for hair.

    Args:
        context (bpy.types.Context): Blender context
    """
    current_render_engine = str(context.scene.render.engine)
    context.scene.render.engine = "BLENDER_EEVEE"
    context.scene.eevee.use_gtao = True
    context.scene.render.hair_type = "STRIP"
    context.scene.render.engine = current_render_engine
