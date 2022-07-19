import os
import time
from pathlib import Path

import bpy
import numpy as np
from HumGen3D.backend.memory_management import hg_delete, remove_broken_drivers
from HumGen3D.backend.preferences import get_prefs
from HumGen3D.human.base.decorators import injected_context
from HumGen3D.human.base.drivers import build_driver_dict
from HumGen3D.human.base.pcoll_content import PreviewCollectionContent
from HumGen3D.human.creation_phase.length.length import apply_armature
from HumGen3D.human.shape_keys.shape_keys import apply_shapekeys


class ExpressionSettings(PreviewCollectionContent):
    def __init__(self, _human):
        self._human = _human
        self._pcoll_name = "expressions"
        self._pcoll_gender_split = False

    def set(self, preset):
        """Loads the active expression in the preview collection"""
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

        hg_rig = self._human.rig_obj
        hg_body = hg_rig.HG.body_obj
        sk_names = [sk.name for sk in hg_body.data.shape_keys.key_blocks]
        if "expr_{}".format(sk_name) in sk_names:
            new_key = hg_body.data.shape_keys.key_blocks["expr_{}".format(sk_name)]
        else:
            backup_rig = hg_rig.HG.backup
            backup_body = next(
                child for child in backup_rig.children if "hg_body" in child
            )
            sks = backup_body.data.shape_keys.key_blocks
            keys = [sks[k] for k in sett_dict.keys()]
            values = [float(v) for v in sett_dict.values()]
            print(keys, values)
            new_key = self._transfer_multiple_as_one(
                keys, values, hg_body, f"expr_{sk_name}"
            )

        for sk in hg_body.data.shape_keys.key_blocks:
            if not sk.name == f"expr_{sk_name}":
                sk.value = 0

        new_key.mute = False
        new_key.value = 1

    def _transfer_as_one_shapekey(self, context, source, target, sk_dict, backup_rig):
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

    @injected_context
    def load_facial_rig(self, context=None):
        frig_bones = self._get_frig_bones()
        for b_name in frig_bones:
            b = self._human.pose_bones[b_name]
            b.bone.hide = False

        for sk in self._human.shape_keys:
            if sk.name.startswith("expr"):
                sk.mute = True

        self._load_FACS_sks(context)

        self._human.body_obj["facial_rig"] = 1

    def _load_FACS_sks(self, context):
        """Imports the needed FACS shapekeys to be used by the rig

        Args:
            hg_body (Object): HumGen body object to import shapekeys on
        """
        pref = get_prefs()
        t = time.perf_counter()
        blendfile = pref.filepath + str(Path("/models/FACS/HG_FACS.blend"))
        with bpy.data.libraries.load(blendfile, link=False) as (
            data_from,
            data_to,
        ):
            data_to.objects = data_from.objects

        print("import", time.perf_counter() - t)
        t = time.perf_counter()
        remove_broken_drivers()
        print("remove broken", time.perf_counter() - t)
        t = time.perf_counter()
        # TODO make easier
        hg_lower_teeth = next(
            c
            for c in self._human.children
            if "hg_teeth" in c and "lower" in c.name.lower()
        )
        # hg_lower_teeth.data = bpy.data.objects['HG_FACS_TEETH'].data
        # for driver in hg_lower_teeth.data.shape_keys.animation_data.drivers:
        #     var    = driver.driver.variables[0]
        #     var.targets[0].id = hg_rig

        hg_body = self._human.body_obj
        from_obj = bpy.data.objects["HG_FACS_BODY"]
        context.scene.collection.objects.link(from_obj)
        context.view_layer.objects.active = hg_body
        self._transfer_sk(context, hg_body, from_obj)

        from_obj = bpy.data.objects["HG_FACS_TEETH"]
        context.scene.collection.objects.link(from_obj)
        context.view_layer.objects.active = hg_lower_teeth
        self._transfer_sk(context, hg_lower_teeth, from_obj)

    def _transfer_sk(self, context, to_obj, from_obj):
        # normalize objects
        driver_dict = build_driver_dict(from_obj, remove=False)

        for obj in context.selected_objects:
            obj.select_set(False)

        to_obj.select_set(True)
        from_obj.select_set(True)

        for idx, sk in enumerate(from_obj.data.shape_keys.key_blocks):
            if sk.name in ["Basis", "Male"]:
                continue
            from_obj.active_shape_key_index = idx
            # bpy.ops.object.shape_key_transfer()
            self._transfer(sk, to_obj)

        sks_on_target = to_obj.data.shape_keys.key_blocks
        for driver_shapekey in driver_dict:
            if driver_shapekey in sks_on_target:
                sk = to_obj.data.shape_keys.key_blocks[driver_shapekey]
                driver = self._human.shape_keys._add_driver(
                    sk, driver_dict[driver_shapekey]
                )

                # correction for mistake in expression
                if driver_shapekey == "mouthClose":
                    driver.expression = "var*100"

        from_obj.select_set(False)
        hg_delete(from_obj)
        to_obj.show_only_shape_key = False

    def _transfer(self, sk, to_obj):
        new_sk = to_obj.shape_key_add(name=sk.name, from_mix=False)
        new_sk.interpolation = "KEY_LINEAR"
        old_sk_data = np.empty(len(to_obj.data.vertices) * 3, dtype=np.float64)

        sk.data.foreach_get("co", old_sk_data)
        new_sk.data.foreach_set("co", old_sk_data)

    def _transfer_multiple_as_one(self, sks, values, to_obj, name):
        new_sk = to_obj.shape_key_add(name=name, from_mix=False)
        new_sk.interpolation = "KEY_LINEAR"
        combined_sk_data = np.zeros(len(to_obj.data.vertices) * 3, dtype=np.float64)

        for sk, value in zip(sks, values):
            sk_data = np.empty(len(to_obj.data.vertices) * 3, dtype=np.float64)
            sk.data.foreach_get("co", sk_data)
            combined_sk_data += sk_data * value - combined_sk_data

        new_sk.data.foreach_set("co", combined_sk_data)

        return new_sk

    def remove_facial_rig(self):
        frig_bones = self._get_frig_bones()
        for b_name in frig_bones:
            b = self._human.pose_bones[b_name]
            b.bone.hide = True

        # FIXME make it only delete Frig sks instead of all outside naming scheme
        for sk in [
            sk
            for sk in self._human.shape_keys
            if not sk.name.startswith(("Basis", "cor_", "expr_", "eye"))
        ]:
            self._human.body_obj.shape_key_remove(sk)

        del self._human.body_obj["facial_rig"]

        remove_broken_drivers()

    # TODO make json
    def _get_frig_bones(self):
        return [
            "brow_inner_up",
            "pucker_cheekPuf",
            "jaw_dwn_mouth_clsd",
            "jaw_open_lt_rt_frwd",
            "brow_dwn_L",
            "eye_blink_open_L",
            "eye_squint_L",
            "brow_outer_up_L",
            "nose_sneer_L",
            "cheek_squint_L",
            "mouth_smile_frown_L",
            "mouth_stretch_L",
            "brow_dwn_R",
            "brow_outer_up_R",
            "eye_blink_open_R",
            "eye_squint_R",
            "cheek_squint_R",
            "mouth_smile_frown_R",
            "mouth_stretch_R",
            "nose_sneer_R",
            "brow_inner_up",
            "pucker_cheekPuf",
            "mouth_shrug_roll_upper",
            "mouth_lt_rt_funnel",
            "mouth_roll_lower",
            "jaw_dwn_mouth_clsd",
            "jaw_open_lt_rt_frwd",
            "brow_dwn_L",
            "eye_blink_open_L",
            "eye_squint_L",
            "brow_outer_up_L",
            "nose_sneer_L",
            "cheek_squint_L",
            "mouth_dimple_L",
            "mouth_smile_frown_L",
            "mouth_upper_up_L",
            "mouth_lower_down_L",
            "mouth_stretch_L",
            "brow_dwn_R",
            "brow_outer_up_R",
            "eye_blink_open_R",
            "eye_squint_R",
            "cheek_squint_R",
            "mouth_dimple_R",
            "mouth_lower_down_R",
            "mouth_upper_up_R",
            "mouth_smile_frown_R",
            "mouth_stretch_R",
            "nose_sneer_R",
            "tongue_out_lt_rt_up_dwn",
        ]
