# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import json
import os
from pathlib import Path

import bpy  # type: ignore
from HumGen3D.backend import get_prefs
from HumGen3D.human.human import Human


def refresh_modapply(self, context):
    sett = context.scene.HG3D
    col = context.scene.modapply_col
    col.clear()

    header = col.add()
    header.mod_name = "HEADER"
    header.count = 1 if sett.modapply_search_modifiers == "summary" else 0
    objs = build_object_list(context, sett)

    for obj in objs:
        for mod in obj.modifiers:
            if mod.type == "PARTICLE_SYSTEM":
                continue
            if sett.modapply_search_modifiers == "individual":
                build_full_list(col, mod, obj)
            else:
                build_summary_list(col, mod)


def build_object_list(context, sett) -> list:
    objs = [obj for obj in context.selected_objects if not obj.HG.ishuman]
    if sett.modapply_search_objects != "selected":
        if sett.modapply_search_objects == "full":
            human = Human.from_existing(context.object, strict_check=False)
            humans = [
                human,
            ]
        else:
            humans = [obj for obj in bpy.data.objects if obj.HG.ishuman]

        for human in humans:
            if not human:
                continue
            objs.extend([child for child in human.children])
    return list(set(objs))


def build_full_list(col, mod, obj):
    item = col.add()
    item.mod_name = mod.name
    item.mod_type = mod.type

    item.viewport_visible = mod.show_viewport
    item.render_visible = mod.show_render
    item.count = 0
    item.object = obj

    if mod.type in ["ARMATURE", "SUBSURF"]:
        item.enabled = False
    else:
        item.enabled = True


def build_summary_list(col, mod):
    existing = [item for item in col if item.mod_type == mod.type]
    if existing:
        item = existing[0]
        item.count += 1
    else:
        item = col.add()
        item.mod_name = mod.type.title().replace("_", " ")
        item.mod_type = mod.type
        item.count = 1
        if mod.type in ["ARMATURE", "SUBSURF"]:
            item.enabled = False
        else:
            item.enabled = True
