# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Generator, List, Union

import bpy
import numpy as np
from bpy.types import Object  # type: ignore
from bpy.types import Context, ShapeKey  # type:ignore
from HumGen3D.backend import get_prefs, hg_delete, hg_log
from HumGen3D.human.base.decorators import injected_context
from HumGen3D.human.base.drivers import build_driver_dict

if TYPE_CHECKING:
    from .bpy_livekey import LiveKey

from HumGen3D.user_interface.documentation.feedback_func import show_message

from ..base.exceptions import HumGenException
from ..base.prop_collection import PropCollection


def update_livekey_collection():
    """Updates the livekeys collection inside context.window_manager to contain all
    livekeys present in the Human Generator folder structure.
    """
    bpy.context.window_manager.livekeys.clear()

    folder = os.path.join(get_prefs().filepath, "livekeys")
    for root, dirs, files in os.walk(folder):
        for file in files:
            if not file.endswith(".npy"):
                continue
            item = bpy.context.window_manager.livekeys.add()
            if file.startswith(("male_", "female_")):
                item.gender = file.split("_")[0]
                item.name = file[:-4].replace(f"{item.gender}_", "")
            else:
                item.name = file[:-4]
            abspath = os.path.join(root, file)
            relpath = os.path.relpath(abspath, folder).split(os.sep)

            if len(relpath) >= 3:
                category, subcategory, *_ = relpath
            else:
                category = relpath[0]
                subcategory = ""

            item.category = category
            item.subcategory = subcategory
            item.path = os.path.relpath(abspath, get_prefs().filepath)
            print("adding", item)


def transfer_shapekey(sk, to_obj):
    new_sk = to_obj.shape_key_add(name=sk.name, from_mix=False)
    new_sk.interpolation = "KEY_LINEAR"
    old_sk_data = np.empty(len(to_obj.data.vertices) * 3, dtype=np.float64)

    sk.data.foreach_get("co", old_sk_data)
    new_sk.data.foreach_set("co", old_sk_data)


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


class KeyItem:
    def __init__(self, name, category, human, subcategory=None):
        self.name = name
        self.category = category
        self._human = human
        self.subcategory = subcategory

    @property
    def value(self) -> float:
        raise NotImplementedError

    @value.setter
    def value(self, value) -> None:
        raise NotImplementedError

    def as_bpy(self):
        raise NotImplementedError


class LiveKeyItem(KeyItem):
    def __init__(self, name, category, path, human, subcategory=None):
        super().__init__(name, category, human, subcategory)
        self.path = path

    def to_shapekey(self) -> ShapeKeyItem:
        filepath = os.path.join(get_prefs().filepath, self.as_bpy().path)
        new_key_relative_coords = np.load(filepath)

        if self.category:
            if self.subcategory:
                name = f"${self.category}_${self.subcategory}_{self.name}"
            else:
                name = f"${self.category}_{self.name}"
        else:
            name = self.name

        body = self._human.body_obj
        vert_count = len(body.data.vertices)
        obj_coords = np.empty(vert_count * 3, dtype=np.float64)
        body.data.vertices.foreach_get("co", obj_coords)

        new_key_coords = obj_coords + new_key_relative_coords
        key = self._human.body_obj.shape_key_add(name=name)
        key.slider_max = 2
        key.slider_min = -2

        key.data.foreach_set("co", new_key_coords)

        idx = bpy.context.window_manager.livekeys.find(self.name)
        bpy.context.window_manager.livekeys.remove(idx)  # FIXME

        return ShapeKeyItem(name, self._human)

    @property
    def value(self) -> float:
        raise NotImplementedError

    @value.setter
    def value(self, value) -> None:
        self._human.keys.livekey_set(self.name, value)

    @injected_context
    def as_bpy(self, context=None) -> LiveKey:
        # livekey = getattr(context.scene.livekeys, self.category).get(self.name)
        livekey = context.window_manager.livekeys.get(self.name)
        assert livekey
        return livekey


class ShapeKeyItem(KeyItem):
    def __init__(self, sk_name, human):
        pattern = re.compile(
            "^(\$(?P<category>[^_]+)_)?(\$(?P<subcategory>[^_]+)_)?(?P<name>.*)"
        )
        match = pattern.match(sk_name)
        groupdict = match.groupdict()
        category = groupdict.get("category")
        subcategory = groupdict.get("subcategory")
        name = groupdict.get("name")
        assert name
        super().__init__(name, category, human, subcategory=subcategory)

    @property
    def value(self) -> float:
        return self._human.body_obj.data.shape_keys.key_blocks[self.name].value

    @value.setter
    def value(self, value) -> None:
        self._human.body_obj.data.shape_keys.key_blocks[self.name].value = value

    @injected_context
    def as_bpy(self, context=None) -> ShapeKey:
        return self._human.body_obj.data.shape_keys.key_blocks[self.name]


class KeySettings:
    def __init__(self, human):
        self._human = human

    def __getitem__(self, name) -> Union[LiveKeyItem, ShapeKeyItem]:
        return next(key for key in self.all_keys if key.name == name)

    def __iter__(self):
        yield from self.all_keys

    def get(self, name):
        try:
            self[name]
        except ValueError:
            return None

    @property
    def all_keys(self) -> List[Union[LiveKeyItem, ShapeKeyItem]]:
        return self.all_livekeys + self.all_shapekeys

    @property
    def all_livekeys(self) -> List[LiveKeyItem]:
        livekeys = []
        for key in bpy.context.window_manager.livekeys:
            # Skip gendered keys
            if key.gender and key.gender != self._human.gender:
                continue
            livekeys.append(
                LiveKeyItem(
                    key.name,
                    key.category,
                    key.path,
                    self._human,
                    subcategory=key.subcategory,
                )
            )
        return livekeys

    @property
    def all_shapekeys(self) -> List[ShapeKeyItem]:
        shapekeys = []
        for sk in self._human.body_obj.data.shape_keys.key_blocks:
            shapekeys.append(ShapeKeyItem(sk.name, self._human))
        return shapekeys

    @property
    def body_proportions(self):
        return PropCollection([sk for sk in self if sk.name.startswith("bp_")])

    @property
    def face_presets(self):
        return PropCollection([sk for sk in self if sk.name.startswith("pr_")])

    @property
    def expressions(self) -> PropCollection:
        return PropCollection([sk for sk in self if sk.name.startswith("expr_")])

    @property
    def temp_key(self):
        temp_key = next(
            (sk for sk in self.all_shapekeys if sk.name.startswith("LIVE_KEY_TEMP_")),
            None,
        )
        if not temp_key:
            temp_key = self._human.body_obj.shape_key_add(name="LIVE_KEY_TEMP_")
            temp_key.slider_max = 10
            temp_key.slider_min = -10
        else:
            temp_key = temp_key.as_bpy(bpy.context)
        return temp_key

    @property
    def permanent_key(self):
        return self["LIVE_KEY_PERMANENT"].as_bpy(bpy.context)

    def filtered(
        self, category, subcategory=None
    ) -> List[Union[LiveKeyItem, ShapeKeyItem]]:
        keys = []
        for key in self:
            if key.category == category:
                keys.append(key)

        return keys

    def load_from_npy(
        self, npy_filepath: Union[str, os.PathLike], obj_override: Object = None
    ):
        """Creates a new shapekey on the body or the passed obj_override from a npy file

        This .npy file contains a one dimensional array with coordinates of the
        shape key, RELATIVE to the base coordinates of the body.

        Args:
            npy_filepath (str | os.PathLike): Path to the .npy file
            obj_override (Object, optional): Add the shape key to this object instead of
                to the body object. Defaults to None.
        """
        relative_sk_co = np.load(npy_filepath)

        if obj_override:
            obj = obj_override
        else:
            obj = self._human.body_obj

        vert_count = len(obj.data.vertices)
        vert_co = np.empty(vert_count * 3, dtype=np.float64)
        obj.data.vertices.foreach_get("co", vert_co)

        name = os.path.basename(os.path.splitext(npy_filepath)[0])

        sk = obj.shape_key_add(name=name)
        sk.interpolation = "KEY_LINEAR"

        adjusted_vert_co = vert_co + relative_sk_co

        sk.data.foreach_set("co", adjusted_vert_co)

        return sk

    def livekey_set(self, name, value):
        livekey_path = None
        search_path = os.path.join(get_prefs().filepath, "livekeys")
        for root, dirs, files in os.walk(search_path):
            for file in files:
                if os.path.splitext(file)[0] == name:
                    livekey_path = os.path.join(root, file)
                    break

        if not livekey_path:
            raise HumGenException(f"Livekey {name} not found in {search_path}")

        # TODO repetition from set_livekey
        body = self._human.body_obj
        vert_count = len(body.data.vertices)
        obj_coords = np.empty(vert_count * 3, dtype=np.float64)
        body.data.vertices.foreach_get("co", obj_coords)

        permanent_key_coords = np.empty(vert_count * 3, dtype=np.float64)
        self._human.keys.permanent_key.data.foreach_get("co", permanent_key_coords)

        new_key_relative_coords = np.load(livekey_path)

        current_sk_values = self._human.props.sk_values
        old_value = current_sk_values[name] * -1 if name in current_sk_values else 0
        permanent_key_coords += new_key_relative_coords * (old_value + value)

        self._human.keys.permanent_key.data.foreach_set("co", permanent_key_coords)

    @injected_context
    def _load_external(self, human, context=None):
        """Imports external shapekeys from the models/shapekeys folder

        Args:
            pref (AddonPreferences): HumGen preferences
            hg_body (Object): Humgen body object
        """
        context.view_layer.objects.active = human.body_obj
        walker = os.walk(
            str(get_prefs().filepath) + str(Path("/models/shapekeys"))
        )  # TODO

        for root, _, filenames in walker:
            for fn in filenames:
                hg_log(f"Existing shapekeys, found {fn} in {root}", level="DEBUG")
                if not os.path.splitext(fn)[1] == ".blend":
                    continue

                imported_body = self._import_external_sk_human(
                    context, get_prefs(), root, fn
                )
                if not imported_body:
                    continue

                self._transfer_shapekeys(context, human.body_obj, imported_body)

                imported_body.select_set(False)
                hg_delete(imported_body)

        human.body_obj.show_only_shape_key = False

    def _import_external_sk_human(self, context, pref, root, fn) -> bpy.types.Object:
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
        for idx, sk in enumerate(imported_body.data.shape_keys.key_blocks):
            if sk.name in ["Basis", "Male"]:
                continue
            transfer_shapekey(sk, hg_body)

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

            if sk.name.lower().startswith(opposite_gender) and sk.name != "Male":
                hg_body.shape_key_remove(sk)

    def _extract_permanent_keys(
        self,
        context: Context = None,
        override_obj=None,
    ):
        if not context:
            context = bpy.context

        pref = get_prefs()

        obj = override_obj if override_obj else self._human.body_obj
        sks = (
            override_obj.data.shape_keys.key_blocks
            if override_obj
            else self._human.keys
        )
        vert_count = len(obj.data.vertices)

        driver_dict = build_driver_dict(obj)

        basis_data = np.empty(vert_count * 3, dtype=np.float64)
        sks.get("Basis").data.foreach_get("co", basis_data)

        sk_vector_dict: Dict[str, np.ndarray] = {}
        for shapekey in sks:
            if (
                not shapekey.name.startswith(("cor_", "eyeLook"))
                and not pref.keep_all_shapekeys
            ):
                continue

            sk_data = np.empty(vert_count * 3, dtype=np.float64)
            shapekey.data.foreach_get("co", sk_data)
            sk_vectors = sk_data - basis_data
            sk_vector_dict[shapekey.name] = sk_vectors

        return sk_vector_dict, driver_dict

    def _reapply_permanent_keys(
        self, sk_vector_dict, driver_dict, context: Context = None
    ):
        if not context:
            context = bpy.context
        body_obj = self._human.body_obj
        vert_count = len(body_obj.data.vertices)
        body_obj.shape_key_add(name="Basis")

        basis_data = np.empty(vert_count * 3, dtype=np.float64)
        sks = body_obj.data.shape_keys.key_blocks
        sks.get("Basis").data.foreach_get("co", basis_data)

        for name, vectors in sk_vector_dict.items():
            sk = body_obj.shape_key_add(name=name, from_mix=False)
            sk.interpolation = "KEY_LINEAR"
            sk.data.foreach_set("co", vectors + basis_data)

            if name in driver_dict:
                self._add_driver(sk, driver_dict[name])

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
