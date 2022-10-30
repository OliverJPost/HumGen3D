# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from __future__ import annotations

import hashlib
import os
import re
from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Union, cast

import bpy
import numpy as np
from bpy.types import Object, ShapeKey
from HumGen3D.common.type_aliases import C
from HumGen3D.common.decorators import injected_context

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.backend import get_prefs, hg_log
from HumGen3D.human.common_baseclasses.savable_content import SavableContent

if TYPE_CHECKING:
    from .bpy_livekey import BpyLiveKey


def import_npz_key(
    vert_count: int, filepath: str
) -> np.ndarray[Any, np.dtype[np.float64]]:
    npz_dict = np.load(filepath)
    new_key_relative_coords = np.zeros(vert_count * 3, dtype=np.float64)
    new_key_relative_coords[npz_dict["indices"]] = npz_dict["relative_coordinates"]
    return new_key_relative_coords


def update_livekey_collection() -> None:
    """Updates the livekeys collection inside context.window_manager to contain all
    livekeys present in the Human Generator folder structure.
    """
    bpy.context.window_manager.livekeys.clear()

    subcategories = []

    folder = os.path.join(get_prefs().filepath, "livekeys")
    for root, _, files in os.walk(folder):
        for file in files:
            if not file.endswith(".npz"):
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

            subcategories.append(subcategory)

            item.category = category
            item.subcategory = subcategory
            item.path = os.path.relpath(abspath, get_prefs().filepath)

    from HumGen3D.backend.properties.ui_properties import UserInterfaceProps

    for category in set(subcategories):
        if not category:
            continue

        setattr(
            UserInterfaceProps,
            category,
            bpy.props.BoolProperty(default=False),  # type:ignore[func-returns-value]
        )


def transfer_shapekey(sk: bpy.types.ShapeKey, to_obj: bpy.types.Object) -> None:
    new_sk = to_obj.shape_key_add(name=sk.name, from_mix=False)
    new_sk.interpolation = "KEY_LINEAR"
    old_sk_data = np.empty(len(to_obj.data.vertices) * 3, dtype=np.float64)

    sk.data.foreach_get("co", old_sk_data)
    new_sk.data.foreach_set("co", old_sk_data)


# MODULE
def apply_shapekeys(ob: bpy.types.Object) -> None:
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

    for _ in range(1, i):
        ob.active_shape_key_index = 1
        ob.shape_key_remove(ob.active_shape_key)

    ob.shape_key_remove(ob.active_shape_key)
    ob.shape_key_remove(ob.active_shape_key)


class KeyItem:
    def __init__(
        self,
        name: str,
        category: str,
        human: "Human",
        subcategory: Optional[str] = None,
    ) -> None:
        """Create new KeyItem."""
        self.name = name
        self.category = category
        self._human = human
        self.subcategory = subcategory

    @property
    def value(self) -> float:
        raise NotImplementedError

    @value.setter
    def value(self, value: float) -> None:
        raise NotImplementedError

    def as_bpy(self) -> Union[bpy.types.ShapeKey, "BpyLiveKey"]:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"({self.name=}, {self.value=}, {self.category=}, {self.subcategory=})"


class LiveKeyItem(KeyItem):
    def __init__(
        self,
        name: str,
        category: str,
        path: str,
        human: "Human",
        subcategory: Optional[str] = None,
    ) -> None:
        """Create new LiveKeyItem."""
        super().__init__(name, category, human, subcategory)
        self.path = path

    @property
    def value(self) -> float:
        # TODO this is repetition from get_livekey
        temp_key = self._human.keys.temp_key
        current_sk_values = self._human.props.sk_values
        if temp_key and temp_key.name.endswith(self.name):
            return temp_key.value
        elif self.name in current_sk_values:
            return cast(float, current_sk_values[self.name])
        else:
            return 0.0

    @value.setter
    def value(self, value: float) -> None:
        self.set_without_update(value)
        self._human.keys.update_human_from_key_change(bpy.context)
        self._human.body_obj.data.update()

    def set_without_update(self, value: float) -> None:
        # TODO repetition from set_livekey
        body = self._human.body_obj
        vert_count = len(body.data.vertices)
        obj_coords = np.empty(vert_count * 3, dtype=np.float64)
        body.data.vertices.foreach_get("co", obj_coords)

        permanent_key_coords = np.empty(vert_count * 3, dtype=np.float64)
        self._human.keys.permanent_key.data.foreach_get("co", permanent_key_coords)

        npz_path = os.path.join(get_prefs().filepath, self.path)
        new_key_relative_coords = import_npz_key(vert_count, npz_path)

        current_sk_values = self._human.props.sk_values
        old_value = (
            current_sk_values[self.name] * -1 if self.name in current_sk_values else 0
        )
        permanent_key_coords += new_key_relative_coords * (old_value + value)

        self._human.keys.permanent_key.data.foreach_set("co", permanent_key_coords)

        self._human.props.sk_values[self.name] = value

    def to_shapekey(self) -> ShapeKeyItem:
        filepath = os.path.join(get_prefs().filepath, self.as_bpy().path)
        body = self._human.body_obj
        vert_count = len(body.data.vertices)
        new_key_relative_coords = import_npz_key(vert_count, filepath)

        if self.category:
            if self.subcategory:
                # Tripe curly braces for result of f{chin}_chin_size
                name = f"{self.category[0]}]_{{{self.subcategory}}}_{self.name}"
            else:
                name = f"{self.category[0]}_{self.name}"
        else:
            name = self.name
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

    def as_bpy(self) -> "BpyLiveKey":
        # livekey = getattr(context.scene.livekeys, self.category).get(self.name)
        livekey = bpy.context.window_manager.livekeys.get(self.name)
        assert livekey
        return cast("BpyLiveKey", livekey)

    def __repr__(self) -> str:
        return "LiveKey " + super().__repr__()


class ShapeKeyItem(KeyItem, SavableContent):
    category_dict = {
        "f": "face_proportions",
        "b": "body_proportions",
        "p": "presets",
        "e": "expressions",
    }

    def __init__(self, sk_name: str, human: "Human") -> None:
        """Create new ShapeKeyItem."""
        pattern = re.compile(
            "^((?P<category>[^_])[_\{])?((?P<subcategory>.+)\}_)?(?P<name>.*)"  # noqa
        )
        match = pattern.match(sk_name)
        groupdict = match.groupdict()
        category_code = groupdict.get("category")
        category = self.category_dict[category_code] if category_code else ""
        subcategory = groupdict.get("subcategory")
        name = groupdict.get("name")
        assert name
        super().__init__(name, category, human, subcategory=subcategory)

    @property
    def value(self) -> float:
        key_blocks = self._human.body_obj.data.shape_keys.key_blocks
        return cast(float, key_blocks[self.name].value)

    @value.setter
    def value(self, value: float) -> None:
        key_blocks = self._human.body_obj.data.shape_keys.key_blocks
        key_blocks[self.name].value = value

    def as_bpy(self) -> ShapeKey:
        if self.category:
            if self.subcategory:
                name = f"{self.category[0]}{{{self.subcategory}}}_{self.name}"
            else:
                name = f"{self.category[0]}_{self.name}"
        else:
            name = self.name
        return cast(ShapeKey, self._human.body_obj.data.shape_keys.key_blocks[name])

    def save_to_library(
        self,
        name: str,
        category: str,
        subcategory: str,
        as_livekey: bool = True,
        delete_original: bool = False,
    ) -> None:
        body = self._human.body_obj
        sk = self.as_bpy()
        sk_coords = np.empty(
            len(sk.data) * 3, dtype=np.float64  # type:ignore[arg-type]
        )
        sk.data.foreach_get("co", sk_coords)

        vert_count = len(body.data.vertices)
        body_coordinates = np.empty(vert_count * 3, dtype=np.float64)
        body.data.vertices.foreach_get("co", body_coordinates)

        relative_coordinates = sk_coords - body_coordinates

        folder = "livekeys" if as_livekey else "shapekeys"
        path = os.path.join(get_prefs().filepath, folder, category, subcategory)

        if not os.path.exists(path):
            os.makedirs(path)

        # Only save nonzero values. NOTE: This operatates on a 1-dimensional array, it
        # does not store vertex indices but individual vector member indices.
        relative_coordinates = relative_coordinates.round(4)
        changed_idxs = np.nonzero(relative_coordinates)

        np.savez(
            os.path.join(path, name),
            indices=changed_idxs,
            relative_coordinates=relative_coordinates[changed_idxs],
        )

        if delete_original:
            body.shape_key_remove(sk)
        else:
            sk.name = f"$[{category}]_$[{subcategory}]_{name}"

        update_livekey_collection()

    def __repr__(self) -> str:
        return "ShapeKey " + super().__repr__()

    def __hash__(self) -> int:
        data = self.as_bpy().data
        coords = np.empty(len(data) * 3, dtype=np.float64)  # type:ignore[arg-type]
        data.foreach_get("co", coords)
        return int(hashlib.sha1(data).hexdigest(), 16)  # type:ignore[arg-type] # noqa


class KeySettings:
    def __init__(self, human: "Human") -> None:
        self._human = human

    @property
    def all_keys(self) -> List[Union[LiveKeyItem, ShapeKeyItem]]:
        return self.all_livekeys + self.all_shapekeys  # type:ignore[operator]

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

        if not livekeys:
            update_livekey_collection()
        return livekeys

    @property
    def all_shapekeys(self) -> List[ShapeKeyItem]:
        shapekeys = []
        # TODO Skip Basis?
        for sk in self._human.body_obj.data.shape_keys.key_blocks:
            shapekeys.append(ShapeKeyItem(sk.name, self._human))
        return shapekeys

    @property
    def all_added_shapekeys(self) -> List[ShapeKeyItem]:
        SKIP_SUFFIXES = ("LIVE_KEY", "Male", "Basis", "cor_", "eyeLook")
        return [
            sk
            for sk in self.all_shapekeys
            if not sk.as_bpy().name.startswith(SKIP_SUFFIXES)
        ]

    @property
    def all_deformation_shapekeys(self) -> List[ShapeKeyItem]:
        SKIP_SUFFIXES = ("Basis", "cor_", "eyeLook", "expr_")
        return [
            sk
            for sk in self.all_shapekeys
            if not sk.as_bpy().name.startswith(SKIP_SUFFIXES)
        ]

    @property
    def temp_key(self) -> bpy.types.ShapeKey:
        temp_key = next(
            (sk for sk in self.all_shapekeys if sk.name.startswith("LIVE_KEY_TEMP_")),
            None,
        )
        if not temp_key:
            temp_key = self._human.body_obj.shape_key_add(
                name="LIVE_KEY_TEMP_"
            )  # type:ignore[assignment]
            temp_key.slider_max = 10
            temp_key.slider_min = -10
        else:
            temp_key = temp_key.as_bpy()  # type:ignore[assignment]
        return cast(bpy.types.ShapeKey, temp_key)

    @property
    def permanent_key(self) -> bpy.types.ShapeKey:
        return cast(bpy.types.ShapeKey, self["LIVE_KEY_PERMANENT"].as_bpy())

    def get(self, name: str) -> Optional[Union[ShapeKeyItem, LiveKeyItem]]:
        try:
            return self[name]
        except ValueError:
            return None

    def filtered(
        self, category: str, subcategory: Optional[str] = None  # FIXME
    ) -> List[Union[LiveKeyItem, ShapeKeyItem]]:
        keys = []
        for key in self:
            if key.name in ("height_200", "height_150"):
                continue
            if key.category == category:
                keys.append(key)

        return keys

    def load_from_npz(
        self, npz_filepath: str, obj_override: Optional[Object] = None
    ) -> bpy.types.ShapeKey:
        """Creates new shapekey on the body or the passed obj_override from a npz file.

        This .npy file contains a one dimensional array with coordinates of the
        shape key, RELATIVE to the base coordinates of the body.

        Args:
            npz_filepath (str | os.PathLike): Path to the .npz file
            obj_override (Object, optional): Add the shape key to this object instead of
                to the body object. Defaults to None.
        """

        if obj_override:
            obj = obj_override
        else:
            obj = self._human.body_obj

        vert_count = len(obj.data.vertices)

        relative_sk_co = import_npz_key(vert_count, npz_filepath)
        vert_co = np.empty(vert_count * 3, dtype=np.float64)
        obj.data.vertices.foreach_get("co", vert_co)

        name = os.path.basename(os.path.splitext(npz_filepath)[0])

        sk = obj.shape_key_add(name=name)
        sk.interpolation = "KEY_LINEAR"

        adjusted_vert_co = vert_co + relative_sk_co

        sk.data.foreach_set("co", adjusted_vert_co)

        return sk

    def as_dict(self) -> dict[str, dict[str, float]]:
        key_dict = {}  # noqa SIM904
        key_dict["livekeys"] = {key.name: key.value for key in self.all_livekeys}
        key_dict["shapekeys"] = {key.name: key.value for key in self.all_shapekeys}

        return key_dict

    @injected_context
    def update_human_from_key_change(self, context: C = None) -> None:
        human = self._human
        human.hide_set(False)
        human.height.correct_armature(context)
        human.height.correct_eyes()
        human.height.correct_teeth()
        for mod in human.body_obj.modifiers:
            if mod.type == "MASK":
                mod.show_viewport = True
        for cloth_obj in human.outfit.objects:
            human.outfit.deform_cloth_to_human(context, cloth_obj)
        for shoe_obj in human.footwear.objects:
            human.footwear.deform_cloth_to_human(context, shoe_obj)

        human.body_obj.data.update()

    def _set_gender_specific(self, human: "Human") -> None:
        """Renames shapekeys, removing Male_ and Female_ prefixes according to
        the passed gender

        Args:
            hg_body (Object): HumGen body object
            gender (str): gender of this human
        """
        gender = human.gender
        hg_body = human.body_obj
        for sk in hg_body.data.shape_keys.key_blocks:
            if sk.name.lower().startswith(gender) and sk.name != "Male":
                GD = gender.capitalize()
                sk.name = sk.name.replace(f"{GD}_", "")

            opposite_gender = "male" if gender == "female" else "female"

            if sk.name.lower().startswith(opposite_gender) and sk.name != "Male":
                hg_body.shape_key_remove(sk)

    def _add_driver(
        self, target_sk: bpy.types.ShapeKey, sett_dict: dict[str, str]
    ) -> bpy.types.Driver:
        """Adds a new driver to the passed shapekey, using the passed dict as settings

        Args:
            hg_body (Object): object the shapekey is on
            target_sk (bpy.types.key_block): shapekey to add driver to
            sett_dict (dict): dict containing copied settings of old drivers
        """
        driver = target_sk.driver_add("value").driver
        var = driver.variables.new()
        var.type = "TRANSFORMS"
        target = var.targets[0]  # type:ignore[index]
        target.id = self._human.rig_obj

        driver.expression = sett_dict["expression"]
        target.bone_target = sett_dict["target_bone"]
        target.transform_type = sett_dict["transform_type"]
        target.transform_space = sett_dict["transform_space"]

        return driver

    def __getitem__(self, name: str) -> Union[LiveKeyItem, ShapeKeyItem]:
        try:
            return next(key for key in self.all_keys if key.name == name)
        except StopIteration:
            hg_log(f"{self.all_keys = }", level="DEBUG")
            raise ValueError(f"Key '{name}' not found")

    def __iter__(self) -> Iterable[Union[ShapeKeyItem, LiveKeyItem]]:
        yield from self.all_keys
