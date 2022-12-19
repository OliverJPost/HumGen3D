"""
Removes the armature object, drivers, corrective shape keys and vertex groups.
HG WILL NO LONGER RECOGNIZE THIS AS A HUMAN GENERATOR HUMAN AFTER DELETING THE RIG.
"""
from HumGen3D.common.memory_management import hg_delete


def main(context, human):
    body_obj = human.objects.body
    if body_obj.data.shape_keys:
        for sk in body_obj.data.shape_keys.key_blocks[:]:
            if sk.name.startswith("cor_"):
                body_obj.shape_key_remove(sk)

    body_obj.vertex_groups.clear()

    if body_obj.animation_data:
        for fcu in body_obj.animation_data.drivers:
            body_obj.driver_remove(fcu.data_path, fcu.array_index)

    hg_delete(human.objects.rig)
