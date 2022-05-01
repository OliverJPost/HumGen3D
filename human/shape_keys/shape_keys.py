import os
from pathlib import Path
from HumGen3D.backend.logging import hg_log
from HumGen3D.backend.memory_management import hg_delete
from HumGen3D.backend.preference_func import get_prefs

import bpy
from bpy.types import Context
from HumGen3D.human.base.drivers import build_driver_dict
from HumGen3D.user_interface.feedback_func import show_message


from ..base.prop_collection import PropCollection


# MODULE
def apply_shapekeys(ob):
    """Applies all shapekeys on the given object, so modifiers on the object can
    be applied

    Args:
        ob (Object): object to apply shapekeys on
    """
    bpy.context.view_layer.objects.active = ob
    if not ob.data.shape_keys:
        return

    bpy.ops.object.shape_key_add(from_mix=True)
    ob.active_shape_key.value = 1.0
    ob.active_shape_key.name = "All shape"

    i = ob.active_shape_key_index

    for n in range(1, i):
        ob.active_shape_key_index = 1
        ob.shape_key_remove(ob.active_shape_key)

    ob.shape_key_remove(ob.active_shape_key)
    ob.shape_key_remove(ob.active_shape_key)


class ShapeKeySettings(PropCollection):
    def __init__(self, human):
        super().__init__(human.body_obj.data.shape_keys.key_blocks)
        self._human = human

    @property
    def body_proportions(self):
        if not hasattr(self, "_body_proportions"):
            self._body_proportions = PropCollection(
                sk for sk in self if sk.name.startswith("bp_")
            )
        return self._body_proportions

    @property
    def face_presets(self):
        if not hasattr(self, "_face_presets"):
            self._face_presets = PropCollection(
                sk for sk in self if sk.name.startswith("pr_")
            )
        return self._face_presets

    def _load_external(self, human, context=None):
        """Imports external shapekeys from the models/shapekeys folder

        Args:
            pref (AddonPreferences): HumGen preferences
            hg_body (Object): Humgen body object
        """
        if not context:
            context = bpy.context

        context.view_layer.objects.active = human.body_obj
        walker = os.walk(
            str(get_prefs().filepath) + str(Path("/models/shapekeys"))
        )  # TODO

        for root, _, filenames in walker:
            for fn in filenames:
                hg_log(
                    f"Existing shapekeys, found {fn} in {root}", level="DEBUG"
                )
                if not os.path.splitext(fn)[1] == ".blend":
                    continue

                imported_body = self._import_external_sk_human(
                    context, get_prefs(), root, fn
                )
                if not imported_body:
                    continue

                self._transfer_shapekeys(
                    context, human.body_obj, imported_body
                )

                imported_body.select_set(False)
                hg_delete(imported_body)

        human.body_obj.show_only_shape_key = False

    def _import_external_sk_human(
        self, context, pref, root, fn
    ) -> bpy.types.Object:
        """Imports the Humgen body from the passed file in order to import the
        shapekeys on that human

        Args:
            pref (AddonPReferences): HumGen preferences
            root (dir): Root directory the file is in
            fn (str): Filename

        Returns:
            Object: Imported body object
        """
        blendfile = root + str(Path(f"/{fn}"))
        try:
            with bpy.data.libraries.load(blendfile, link=False) as (
                data_from,
                data_to,
            ):
                data_to.objects = data_from.objects
        except OSError as e:
            show_message(self, "Could not import " + blendfile)
            print(e)
            return None

        hg_log("Existing shapekeys imported:", data_to.objects, level="DEBUG")
        imported_body = [
            obj for obj in data_to.objects if obj.name.lower() == "hg_shapekey"
        ][0]

        context.scene.collection.objects.link(imported_body)

        return imported_body

    def _transfer_shapekeys(self, context, hg_body, imported_body):
        """Transfer all non-Basis shapekeys from the passed object to hg_body

        Args:
            hg_body (Object): HumGen body object
            imported_body (Object): imported body object that contains shapekeys
        """
        for obj in context.selected_objects:
            obj.select_set(False)
        hg_body.select_set(True)
        imported_body.select_set(True)
        for idx, sk in enumerate(imported_body.data.shape_keys.key_blocks):
            if sk.name in ["Basis", "Male"]:
                continue
            imported_body.active_shape_key_index = idx
            bpy.ops.object.shape_key_transfer()

    def _set_gender_specific(self, human):
        """Renames shapekeys, removing Male_ and Female_ prefixes according to
        the passed gender

        Args:
            hg_body (Object): HumGen body object
            gender (str): gender of this human
        """
        gender = human.gender
        hg_body = human.body_obj
        for sk in [sk for sk in hg_body.data.shape_keys.key_blocks]:
            if sk.name.lower().startswith(gender):
                if sk.name != "Male":
                    GD = gender.capitalize()
                    sk.name = sk.name.replace(f"{GD}_", "")

            opposite_gender = "male" if gender == "female" else "female"

            if (
                sk.name.lower().startswith(opposite_gender)
                and sk.name != "Male"
            ):
                hg_body.shape_key_remove(sk)

    def _extract_permanent_keys(
        self, context: Context = None, apply_armature: bool = True, override_obj = None
    ):
        if not context:
            context = bpy.context

        pref = get_prefs()

        driver_dict = build_driver_dict(self)

        obj = override_obj if override_obj else self._human.body_obj
        sks = override_obj.data.shape_keys.key_blocks if override_obj else self._human.shape_keys

        obj_list = []
        for shapekey in sks:
            if (
                not shapekey.name.startswith(("cor_", "eyeLook"))
                and not pref.keep_all_shapekeys
            ):
                continue
            ob = obj.copy()
            ob.data = ob.data.copy()
            context.collection.objects.link(ob)
            ob.name = shapekey.name
            obj_list.append(ob)

            face_sk = ob.data.shape_keys.key_blocks[shapekey.name]
            face_sk.mute = False
            face_sk.value = 1
            apply_shapekeys(ob)
            if apply_armature:
                bpy.ops.object.modifier_apply(modifier="HG_Armature")

        return obj_list, driver_dict

    def _reapply_permanent_keys(
        self, sk_objects, driver_dict, context: Context = None
    ):
        if not context:
            context = bpy.context

        for ob in context.selected_objects:
            ob.select_set(False)
        context.view_layer.objects.active = self._human.body_obj
        self._human.body_obj.select_set(True)

        for ob in sk_objects:
            ob.select_set(True)
            bpy.ops.object.join_shapes()
            ob.select_set(False)
            if ob.name in driver_dict:
                target_sk = self[ob.name]
                self._add_driver(target_sk, driver_dict[ob.name])

        for ob in sk_objects:
            hg_delete(ob)

    def _add_driver(self, target_sk, sett_dict):
        """Adds a new driver to the passed shapekey, using the passed dict as settings

        Args:
            hg_body (Object): object the shapekey is on
            target_sk (bpy.types.key_block): shapekey to add driver to
            sett_dict (dict): dict containing copied settings of old drivers
        """
        driver = target_sk.driver_add("value").driver
        var = driver.variables.new()
        var.type = "TRANSFORMS"
        target = var.targets[0]
        target.id = self._human.rig_obj

        driver.expression = sett_dict["expression"]
        target.bone_target = sett_dict["target_bone"]
        target.transform_type = sett_dict["transform_type"]
        target.transform_space = sett_dict["transform_space"]

        return driver
