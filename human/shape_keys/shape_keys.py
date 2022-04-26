import os
from pathlib import Path

import bpy
from bpy.types import bpy_prop_collection

from ...old.blender_operators.common.common_functions import (
    get_prefs,
    hg_delete,
    hg_log,
    show_message,
)
from ..base.prop_collection import PropCollection


class ShapeKeySettings(PropCollection):
    def __init__(self, human):
        super().__init__(human.body_obj.data.shape_keys.key_blocks)
        self._human = human

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
