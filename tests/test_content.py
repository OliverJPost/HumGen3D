import os
import time
from HumGen3D.backend.memory_management import hg_delete

import bpy
from HumGen3D.backend.logging import hg_log
from fixtures import context


def test_starting_humans(context):
    """Creates all starting humans in the content packs folder and deletes
    them again. Does not run when there are already humans in the scene"""
    assert not [obj for obj in bpy.data.objects if obj.HG.ishuman]

    bpy.ops.hg3d.deselect()
    context.scene.HG3D.gender = "female"
    __create_all_starting_humans(context)

    context.scene.HG3D.gender = "male"
    __create_all_starting_humans(context)


def __create_all_starting_humans(context):
    pcoll_list = context.scene.HG3D["previews_list_humans"]

    for item_name in pcoll_list:
        context.scene.HG3D.pcoll.humans = item_name
        bpy.ops.hg3d.startcreation()

        human = next(obj for obj in bpy.data.objects if obj.HG.ishuman)

        for child in human.children:
            hg_delete(child)
        hg_delete(human)
