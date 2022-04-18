import bpy

from ..features.common.HG_COMMON_FUNC import hg_delete


def test_human_creation(context):

    assert not [obj for obj in bpy.data.objects if obj.HG.ishuman]

    bpy.ops.hg3d.deselect()
    context.scene.HG3D.gender = "female"
    context.scene.HG3D.pcoll_humans = "/models/female/Caucasian 2.json"
    __create_all_starting_humans(context)

    context.scene.HG3D.gender = "male"
    __create_all_starting_humans(context)


def __create_all_starting_humans(context):
    pcoll_list = context.scene.HG3D["previews_list_humans"]

    for item_name in pcoll_list:
        context.scene.HG3D.pcoll_humans = item_name
        bpy.ops.hg3d.startcreation()

        human = next(obj for obj in bpy.data.objects if obj.HG.ishuman)

        for child in human.children:
            hg_delete(child)
        hg_delete(human)


def test_creation_phase(context):

    pass
