import os

import bpy
from HumGen3D.backend.memory_management import hg_delete
from HumGen3D.backend.preference_func import get_prefs
from HumGen3D.human.creation_phase.length.length import apply_armature
from HumGen3D.human.shape_keys.shape_keys import apply_shapekeys
from HumGen3D.old.blender_operators.common.common_functions import find_human


class ExpressionSettings:
    def __init__(self, _human):
        self._human = _human

    def set(self, preset, context=None):
        """Loads the active expression in the preview collection"""

        if not context:
            context = bpy.context

        pref = get_prefs()

        if preset == "none":
            return
        sk_name, _ = os.path.splitext(os.path.basename(preset))

        sett_dict = {}

        filepath = str(pref.filepath) + str(preset)
        sett_file = open(filepath)
        for line in sett_file:
            key, value = line.split()
            sett_dict[key] = value

        hg_rig = find_human(context.active_object)
        hg_body = hg_rig.HG.body_obj
        sk_names = [sk.name for sk in hg_body.data.shape_keys.key_blocks]
        if "expr_{}".format(sk_name) in sk_names:
            new_key = hg_body.data.shape_keys.key_blocks[
                "expr_{}".format(sk_name)
            ]
            exists = True
        else:
            backup_rig = hg_rig.HG.backup
            backup_body = next(
                child for child in backup_rig.children if "hg_body" in child
            )
            self._transfer_as_one_shapekey(
                context, backup_body, hg_body, sett_dict, backup_rig
            )

            exists = False
            new_key = None

        for sk in hg_body.data.shape_keys.key_blocks:
            if sk.name.startswith(backup_body.name.split(".")[0]):
                new_key = sk
            else:
                sk.value = 0

        if not exists:
            new_key.name = "expr_{}".format(sk_name)
        new_key.mute = False
        new_key.value = 1

    def _transfer_as_one_shapekey(
        self, context, source, target, sk_dict, backup_rig
    ):
        """Transfers multiple shapekeys as one shapekey

        Args:
            context ([type]): [description]
            source (Object): object to copy shapekeys from
            target (Object): Object to copy shapekeys to
            sk_dict (dict): dict containing values to copy the shapekeys at
            backup_rig (Object): Armature of backup human
        """
        backup_rig_copy = backup_rig.copy()
        backup_rig_copy.data = backup_rig_copy.data.copy()
        context.scene.collection.objects.link(backup_rig_copy)

        source_copy = source.copy()
        source_copy.data = source_copy.data.copy()
        context.scene.collection.objects.link(source_copy)

        sks = source_copy.data.shape_keys.key_blocks

        for sk in sks:
            if sk.name.startswith("expr"):
                sk.mute = True
        for key in sk_dict:
            sks[key].mute = False
            sks[key].value = float(sk_dict[key])

        apply_shapekeys(source_copy)

        context.view_layer.objects.active = backup_rig_copy
        backup_rig_copy.hide_viewport = False
        source_copy.hide_viewport = False
        backup_rig_copy.HG.body_obj = source_copy

        apply_armature(source_copy)

        self._human.creation_phase.length.apply(context)

        for obj in context.selected_objects:
            obj.select_set(False)

        context.view_layer.objects.active = target
        source_copy.hide_viewport = False
        source_copy.select_set(True)

        bpy.ops.object.join_shapes()

        hg_delete(source_copy)
        hg_delete(backup_rig_copy)
