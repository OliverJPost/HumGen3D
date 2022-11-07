# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy


def set_eevee_ao_and_strip(context: bpy.types.Context) -> None:
    current_render_engine = str(context.window_manager.render.engine)
    context.window_manager.render.engine = "BLENDER_EEVEE"
    context.window_manager.eevee.use_gtao = True
    context.window_manager.render.hair_type = "STRIP"
    context.window_manager.render.engine = current_render_engine
