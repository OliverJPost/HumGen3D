from pathlib import Path

import bpy
from HumGen3D.backend.memory_management import hg_delete, remove_broken_drivers
from HumGen3D.backend.preference_func import get_prefs
from HumGen3D.human.base.drivers import build_driver_dict
from HumGen3D.old.blender_operators.common.common_functions import find_human


class HG_REMOVE_SHAPEKEY(bpy.types.Operator):
    """Removes the corresponding shapekey

    Operator type
        Shapekeys

    Prereq:
        shapekey str passed
        active object is part of HumGen human

    Args:
        shapekey (str): name of shapekey to remove
    """

    bl_idname = "hg3d.removesk"
    bl_label = "Remove this shapekey"
    bl_description = "Remove this shapekey"
    bl_options = {"UNDO"}

    shapekey: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        hg_rig = find_human(context.active_object)
        hg_body = hg_rig.HG.body_obj

        sk_delete = hg_body.data.shape_keys.key_blocks[self.shapekey]
        hg_body.shape_key_remove(sk_delete)

        return {"FINISHED"}


class FRIG_DATA:  # TODO this is a bit weird
    def get_frig_bones(self):
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


class HG_ADD_FRIG(bpy.types.Operator, FRIG_DATA):
    """Adds the facial rig to this human, importing the necessary shapekeys

    Operator type:
        Facial rig
        Shapekeys

    Prereq:
        Active object is part of HumGen human
        Human doesn't already have a facial rig
    """

    bl_idname = "hg3d.addfrig"
    bl_label = "Add facial rig"
    bl_description = "Adds facial rig"
    bl_options = {"UNDO"}

    def execute(self, context):
        hg_rig = find_human(context.active_object)
        hg_body = hg_rig.HG.body_obj

        frig_bones = self.get_frig_bones()
        for b_name in frig_bones:
            b = hg_rig.pose.bones[b_name]
            b.bone.hide = False

        for sk in hg_body.data.shape_keys.key_blocks:
            if sk.name.startswith("expr"):
                sk.mute = True

        self._load_FACS_sks(context, hg_rig)

        hg_body["facial_rig"] = 1
        return {"FINISHED"}

    def _load_FACS_sks(self, context, hg_rig):
        """Imports the needed FACS shapekeys to be used by the rig

        Args:
            hg_body (Object): HumGen body object to import shapekeys on
        """
        pref = get_prefs()

        blendfile = pref.filepath + str(Path("/models/FACS/HG_FACS.blend"))
        with bpy.data.libraries.load(blendfile, link=False) as (
            data_from,
            data_to,
        ):
            data_to.objects = data_from.objects
        remove_broken_drivers()
        hg_lower_teeth = next(
            c
            for c in hg_rig.children
            if "hg_teeth" in c and "lower" in c.name.lower()
        )
        # hg_lower_teeth.data = bpy.data.objects['HG_FACS_TEETH'].data
        # for driver in hg_lower_teeth.data.shape_keys.animation_data.drivers:
        #     var    = driver.driver.variables[0]
        #     var.targets[0].id = hg_rig

        hg_body = hg_rig.HG.body_obj
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
            bpy.ops.object.shape_key_transfer()

        sks_on_target = to_obj.data.shape_keys.key_blocks
        for driver_shapekey in driver_dict:
            if driver_shapekey in sks_on_target:
                sk = to_obj.data.shape_keys.key_blocks[driver_shapekey]
                driver = None  # FIXME add_driver(to_obj, sk, driver_dict[driver_shapekey])

                # correction for mistake in expression
                if driver_shapekey == "mouthClose":
                    driver.expression = "var*100"

        from_obj.select_set(False)
        hg_delete(from_obj)
        to_obj.show_only_shape_key = False


class HG_REMOVE_FRIG(bpy.types.Operator, FRIG_DATA):
    """Removes the facial rig, including its shapekeys

    Operator type:
        Facial rig
        Shapekeys

    Prereq:
        Active object is part of HumGen human
        Human has a facial rig loaded
    """

    bl_idname = "hg3d.removefrig"
    bl_label = "Remove facial rig"
    bl_description = "Remove facial rig"
    bl_options = {"UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        hg_rig = find_human(context.active_object)
        hg_body = hg_rig.HG.body_obj

        frig_bones = self.get_frig_bones()
        for b_name in frig_bones:
            b = hg_rig.pose.bones[b_name]
            b.bone.hide = True

        # TODO make it only delete Frig sks instead of all outside naming scheme
        for sk in [
            sk
            for sk in hg_body.data.shape_keys.key_blocks
            if not sk.name.startswith(("Basis", "cor_", "expr_", "eye"))
        ]:
            hg_body.shape_key_remove(sk)

        del hg_body["facial_rig"]

        remove_broken_drivers()

        return {"FINISHED"}
