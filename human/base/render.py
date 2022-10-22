# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy


def set_eevee_ao_and_strip(context: bpy.types.Context) -> None:
    current_render_engine = str(context.scene.render.engine)
    context.scene.render.engine = "BLENDER_EEVEE"
    context.scene.eevee.use_gtao = True
    context.scene.render.hair_type = "STRIP"
    context.scene.render.engine = current_render_engine
