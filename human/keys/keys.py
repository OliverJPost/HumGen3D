# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements public part of LiveKeys and shape keys on this human.

Internal part (bpy side) is implemented in bpy_livekeys.py
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import TYPE_CHECKING, Any, Iterable, List, Literal, Optional, Union, cast

import bpy
import numpy as np
from bpy.types import Object, ShapeKey  # type:ignore
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C
from HumGen3D.user_interface.panel_functions import prettify

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from HumGen3D.backend import get_prefs, hg_log
from HumGen3D.human.common_baseclasses.savable_content import SavableContent

if TYPE_CHECKING:
    from .bpy_livekey import BpyLiveKey


def _get_starting_coordinates(
    human: Human, path: str
) -> tuple[int, np.ndarray[Any, Any], np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    body = human.objects.body
    vert_count = len(body.data.vertices)
    obj_coords = np.empty(vert_count * 3, dtype=np.float64)
    body.data.vertices.foreach_get("co", obj_coords)

    # Load coordinates of livekey that is being changed
    filepath = os.path.join(get_prefs().filepath, path)
    new_key_relative_coords = import_npz_key(vert_count, filepath)
    new_key_coords = obj_coords + new_key_relative_coords

    return vert_count, obj_coords, new_key_relative_coords, new_key_coords


def import_npz_key(
    vert_count: int, filepath: str
) -> np.ndarray[Any, np.dtype[np.float64]]:
    """Import coordinates from .npz file.

    Args:
        vert_count (int): number of vertices in the mesh
        filepath (str): Path to the .npz file

    Returns:
        np.ndarray: coordinates of the shape key deformation.
    """
    npz_dict = np.load(filepath)
    new_key_relative_coords = np.zeros(vert_count * 3, dtype=np.float64)
    new_key_relative_coords[npz_dict["indices"]] = npz_dict["relative_coordinates"]
    return new_key_relative_coords


def update_livekey_collection() -> None:
    """Updates the livekeys collection inside context.window_manager.

    Updates it to contain all livekeys present in the Human Generator folder structure.
    """
    bpy.context.window_manager.livekeys.clear()

    subcategories = []

    folder = os.path.join(get_prefs().filepath, "livekeys")
    for root, _, files in os.walk(folder):
        for file in files:
            if not file.endswith(".npz"):
                continue
            item = bpy.context.window_manager.livekeys.add()
            if file.startswith(("male_", "female_")) or os.path.splitext(file)[
                0
            ].endswith(("_male", "_female")):
                item.gender = "female" if "female" in file else "male"
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
    """Transfer shapekey to another object.

    Args:
        sk (ShapeKey): shapekey to transfer
        to_obj (Object): object to transfer shapekey to
    """
    new_sk = to_obj.shape_key_add(name=sk.name, from_mix=False)
    new_sk.interpolation = "KEY_LINEAR"
    old_sk_data = np.empty(len(to_obj.data.vertices) * 3, dtype=np.float64)

    sk.data.foreach_get("co", old_sk_data)
    new_sk.data.foreach_set("co", old_sk_data)


# MODULE
def apply_shapekeys(ob: bpy.types.Object) -> None:
    """Applies all shapekeys on the given object.

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
    """Baseclass for ShapeKey and LiveKey."""

    def __init__(
        self,
        name: str,
        category: str,
        human: "Human",
        subcategory: Optional[str] = None,
    ) -> None:
        self.name = name
        self.category = category
        self._human = human
        self.subcategory = subcategory

    @property
    def value(self) -> float:  # noqa
        raise NotImplementedError

    @value.setter
    def value(self, value: float) -> None:
        raise NotImplementedError

    def as_bpy(self) -> Union[bpy.types.ShapeKey, "BpyLiveKey"]:  # noqa
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"({self.name=}, {self.value=}, {self.category=}, {self.subcategory=})"

    def draw_prop(
        self,
        layout: bpy.types.UILayout,
        value_propname: Literal[
            "value", "value_limited", "value_positive_limited"
        ] = "value",
    ) -> bpy.types.UILayout:
        """Draw a slider of this key item in the given layout.

        Args:
            layout (UILayout): layout to draw in
            value_propname (str, optional): name of the property to draw.
                Defaults to "value". Only used for livekeys.

        Returns:
            bpy.types.UILayout: layout with the slider drawn in it, as row.
        """
        row = layout.row(align=True)
        row.prop(self.as_bpy(), value_propname, text=prettify(self.name), slider=True)

        return row


class LiveKeyItem(KeyItem):
    """Item representing a livekey, used for changing the value and converting it."""

    def __init__(
        self,
        name: str,
        category: str,
        path: str,
        human: "Human",
        subcategory: Optional[str] = None,
    ) -> None:
        super().__init__(name, category, human, subcategory)
        self.path = path

    @property
    def value(self) -> float:
        """Get current value from temp_key or stored list on human.

        Returns:
            float: value of the livekey
        """
        # TODO this is repetition from get_livekey
        temp_key = self._human.keys.temp_key
        current_sk_values = self._human.props.sk_values
        if temp_key and temp_key.name.replace("LIVE_KEY_TEMP_", "") == self.name:
            return temp_key.value
        elif self.name in current_sk_values:
            return cast(float, current_sk_values[self.name])
        else:
            return 0.0

    @value.setter
    def value(self, value: float) -> None:
        """Way of setting a SINGLE livekey.

        If you want to set a lot of livekeys, use `set_without_update()` and call
        `human.keys.update_human_from_key_change()` when you're done modifiny the
        livekeys. This is MUCH faster as this will only update the rig, clothing etc.
        at the end instead of every time you change a livekey.

        Args:
            value (float): value to set the livekey to
        """
        self.set_without_update(value)
        self._human.keys.update_human_from_key_change(bpy.context)

    def set_without_update(self, value: float) -> None:
        """Set the value of the livekey without updating the human rig and clothing.

        This can be used for faster livekey changes. Call `update_human_from_key_change()` # noqa
        when done with setting your livekeys.

        Args:
            value (float): value to set the livekey to
        """
        (
            vert_count,
            obj_coords,
            new_key_relative_coords,
            new_key_coords,
        ) = _get_starting_coordinates(self._human, self.path)

        # Set temp key to base coordinates if it's the same as the key being set.
        temp_key = self._human.keys.temp_key
        if temp_key and self.name == temp_key.name.replace("LIVE_KEY_TEMP_", ""):
            temp_key.data.foreach_set("co", obj_coords.reshape((-1)))

        current_sk_values = self._human.props.sk_values
        old_value = (
            current_sk_values[self.name] * -1 if self.name in current_sk_values else 0
        )

        permanent_key_coords = np.empty(vert_count * 3, dtype=np.float64)
        self._human.keys.permanent_key.data.foreach_get("co", permanent_key_coords)
        permanent_key_coords += new_key_relative_coords * (old_value + value)

        self._human.keys.permanent_key.data.foreach_set("co", permanent_key_coords)

        self._human.props.sk_values[self.name] = value

    def to_shapekey(self) -> ShapeKeyItem:
        """Convert this livekey to a Blender shape key on the human.

        Returns:
            ShapeKeyItem: shapekey item representing the converted livekey
        """
        filepath = os.path.join(get_prefs().filepath, self.as_bpy().path)
        body = self._human.objects.body
        vert_count = len(body.data.vertices)
        new_key_relative_coords = import_npz_key(vert_count, filepath)

        if self.category:
            if self.subcategory:
                # Tripe curly braces for result of f{chin}_chin_size
                name = f"{self.category[0]}_{{{self.subcategory}}}_{self.name}"
            else:
                name = f"{self.category[0]}_{self.name}"
        else:
            name = self.name
        obj_coords = np.empty(vert_count * 3, dtype=np.float64)
        body.data.vertices.foreach_get("co", obj_coords)

        new_key_coords = obj_coords + new_key_relative_coords
        key = self._human.objects.body.shape_key_add(name=name)
        key.slider_max = 2
        key.slider_min = -2

        key.data.foreach_set("co", new_key_coords)

        idx = bpy.context.window_manager.livekeys.find(self.name)
        bpy.context.window_manager.livekeys.remove(idx)  # FIXME

        return ShapeKeyItem(name, self._human)

    def as_bpy(self) -> "BpyLiveKey":
        """Get a pointer to a CollectionProperty item representing this livekey.

        This is useful for sliders in the UI.

        Returns:
            BpyLiveKey: CollectionProperty item representing this livekey
        """
        # Get livekey based on path instead of name as the name is not unique for
        # multi-gender keys.
        livekey = next(
            key for key in bpy.context.window_manager.livekeys if key.path == self.path
        )
        return cast("BpyLiveKey", livekey)

    def draw_prop(
        self,
        layout: bpy.types.UILayout,
        value_propname: Literal[
            "value", "value_limited", "value_positive_limited"
        ] = "value",
    ) -> bpy.types.UILayout:
        """Draw the livekey as a slider in the UI.

        Args:
            layout (bpy.types.UILayout): layout to draw the livekey in
            value_propname (str, optional): name of the property to draw. Defaults to
                "value".

        Returns:
            bpy.types.UILayout: layout with the slider drawn in it, as row.
        """
        row = super().draw_prop(layout, value_propname)
        row.operator(
            "hg3d.livekey_to_shapekey",
            text="",
            icon="SHAPEKEY_DATA",
            emboss=False,
        ).livekey_name = self.name

        return row

    def __repr__(self) -> str:
        return "LiveKey " + super().__repr__()


class ShapeKeyItem(KeyItem, SavableContent):
    """Item representing a Blender shape key on the human."""

    category_dict = {
        "f": "face_proportions",
        "b": "body_proportions",
        "p": "presets",
        "e": "expressions",
        "s": "special",
    }

    def __init__(self, sk_name: str, human: "Human") -> None:
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
        self.sk_name = sk_name

    @property
    def value(self) -> float:
        """Get the current value of the shape key.

        Returns:
            float: value of the shape key
        """
        key_blocks = self._human.objects.body.data.shape_keys.key_blocks
        return cast(float, key_blocks[self.sk_name].value)

    @value.setter
    def value(self, value: float) -> None:
        """Set the value of the shape key.

        Args:
            value (float): value to set the shape key to
        """
        key_blocks = self._human.objects.body.data.shape_keys.key_blocks
        key_blocks[self.sk_name].value = value

    def as_bpy(self) -> ShapeKey:
        """Get pointer to the Blender shape key's key_block.

        This is useful for sliders in the UI.

        Returns:
            ShapeKey: Blender shape key's key_block
        """
        body_obj = self._human.objects.body
        return cast(ShapeKey, body_obj.data.shape_keys.key_blocks[self.sk_name])

    def save_to_library(
        self,
        name: str,
        category: str,
        subcategory: str,
        as_livekey: bool = True,
        delete_original: bool = False,
    ) -> None:
        """Save this shape key to the Human Generator content library.

        This means this shape key will be available for all other characters you create
        in Human Generator. Save it as a livekey to save space and to have the rig and
        clothing update automatically when you change the key. Save as shape key if
        it will be used for animation.

        Args:
            name (str): Name to save the key as
            category (str): Category to save the key in. This has to be one of the
                preset categories. As of writing these are "face_proportions",
                "body_proportions", "presets", "expressions", and "special".
            subcategory (str): Subcategory to save the key in. If the subcategory does
                not exist, a new folder will be created.
            as_livekey (bool): Save as livekey or shape key. Defaults to True.
            delete_original (bool): Delete the original key after saving. Defaults to
                False.
        """
        body = self._human.objects.body
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
            sk.name = f"{category.lower()[0]}_{{{subcategory}}}_{name}"

        update_livekey_collection()

    def draw_prop(
        self,
        layout: bpy.types.UILayout,
        value_propname: Literal[
            "value", "value_limited", "value_positive_limited"
        ] = "value",
    ) -> bpy.types.UILayout:
        """Draw the shape key as a slider in the UI.

        Args:
            layout (bpy.types.UILayout): layout to draw the slider in
            value_propname (Literal): IGNORED for shapekeys. Defaults to "value".

        Returns:
            bpy.types.UILayout: layout with the slider drawn in it
        """
        return super().draw_prop(layout, "value")

    def __repr__(self) -> str:
        return "ShapeKey " + super().__repr__()

    def __hash__(self) -> int:
        data = self.as_bpy().data
        coords = np.empty(len(data) * 3, dtype=np.float64)  # type:ignore[arg-type]
        data.foreach_get("co", coords)
        return int(hashlib.sha1(data).hexdigest(), 16)  # type:ignore[arg-type] # noqa


class KeySettings:
    """Class for changing the shape keys and  LiveKeys of this human."""

    def __init__(self, human: "Human") -> None:
        self._human = human

    @property
    def all_keys(self) -> List[Union[LiveKeyItem, ShapeKeyItem]]:
        """A list of all ShapeKeyItems and LiveKeyItems of this human.

        Returns:
            List[Union[LiveKeyItem, ShapeKeyItem]]: List of all keys
        """
        return self.all_livekeys + self.all_shapekeys  # type:ignore[operator]

    @property
    def all_livekeys(self) -> List[LiveKeyItem]:
        """A list of all LiveKeyItems of this human.

        Returns:
            List[LiveKeyItem]: List of all livekeys
        """
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
        """A list of all ShapeKeyItems of this human.

        Returns:
            List[ShapeKeyItem]: List of all shapekeys
        """
        shapekeys = []
        # TODO Skip Basis?
        for sk in self._human.objects.body.data.shape_keys.key_blocks:
            shapekeys.append(ShapeKeyItem(sk.name, self._human))
        return shapekeys

    @property
    def all_added_shapekeys(self) -> List[ShapeKeyItem]:
        """A list of all ShapeKeyItems that were added by the user or converted from lk.

        Returns:
            List[ShapeKeyItem]: List of all shapekeys
        """
        SKIP_SUFFIXES = ("LIVE_KEY", "Male", "Basis", "cor_", "eyeLook")
        return [
            sk
            for sk in self.all_shapekeys
            if not sk.as_bpy().name.startswith(SKIP_SUFFIXES)
        ]

    @property
    def all_deformation_shapekeys(self) -> List[ShapeKeyItem]:
        """A list of ShapeKeyItems that are used for deformation.

        This means they are not used for animation, but for changing the base shape of
        the human. It leaves out the Basis key, the corrective keys, the eye look keys,
        and the expression keys.

        Returns:
            List[ShapeKeyItem]: List of all shapekeys
        """
        SKIP_SUFFIXES = ("Basis", "cor_", "eyeLook", "expr_")
        return [
            sk
            for sk in self.all_shapekeys
            if not sk.as_bpy().name.startswith(SKIP_SUFFIXES)
        ]

    @property
    def temp_key(self) -> bpy.types.ShapeKey:
        """The temporary shape key used for livekeying. Points to the Blender key.

        Returns:
            bpy.types.ShapeKey: The temporary shape key
        """
        temp_key = next(
            (sk for sk in self.all_shapekeys if sk.name.startswith("LIVE_KEY_TEMP_")),
            None,
        )
        if not temp_key:
            temp_key = self._human.objects.body.shape_key_add(
                name="LIVE_KEY_TEMP_"
            )  # type:ignore[assignment]
            temp_key.slider_max = 10
            temp_key.slider_min = -10
        else:
            temp_key = temp_key.as_bpy()  # type:ignore[assignment]
        return cast(bpy.types.ShapeKey, temp_key)

    @property
    def permanent_key(self) -> bpy.types.ShapeKey:
        """The permanent shape key used for livekeying. Points to the Blender key.

        Returns:
            bpy.types.ShapeKey: The permanent shape key
        """
        return cast(bpy.types.ShapeKey, self["LIVE_KEY_PERMANENT"].as_bpy())

    def get(self, name: str) -> Optional[Union[ShapeKeyItem, LiveKeyItem]]:  # noqa
        try:
            return self[name]
        except KeyError:
            return None

    def filtered(
        self, category: str, subcategory: Optional[str] = None  # FIXME
    ) -> List[Union[LiveKeyItem, ShapeKeyItem]]:
        """Get all keys that match the given category and subcategory.

        Args:
            category (str): The category to filter for.
            subcategory (Optional[str]): The subcategory to filter for.

        Returns:
            List[Union[LiveKeyItem, ShapeKeyItem]]: List of all keys matching the filter
        """
        keys = []
        for key in self:
            if key.name in ("height_200", "height_150"):
                continue
            if key.category == category and (
                subcategory is None or key.subcategory == subcategory
            ):
                keys.append(key)

        return keys

    def load_from_npz(
        self, npz_filepath: str, obj_override: Optional[Object] = None
    ) -> bpy.types.ShapeKey:
        """Creates new shapekey on the body or the passed obj_override from a npz file.

        This .npy file contains a one dimensional array with coordinates of the
        shape key, RELATIVE to the base coordinates of the body.

        Args:
            npz_filepath (str): Path to the .npz file
            obj_override (Object, optional): Add the shape key to this object instead of
                to the body object. Defaults to None.

        Returns:
            bpy.types.ShapeKey: The newly created shape key
        """
        if obj_override:
            obj = obj_override
        else:
            obj = self._human.objects.body

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

    def as_dict(self) -> dict[str, float]:
        """Get the current shape key and live key values as a dictionary.

        Returns:
            dict[str, float]: Dictionary of shape key and live key values
        """
        key_dict = {key.name: key.value for key in self.all_livekeys}
        key_dict.update({key.name: key.value for key in self.all_deformation_shapekeys})

        return key_dict

    @injected_context
    def set_from_dict(self, key_dict: dict[str, float], context: C = None) -> list[str]:
        """Set the shape key and live key values from a dictionary.

        Args:
            key_dict (dict[str, float]): Dictionary of shape key and live key values
            context (C): Blender context. Defaults to None.

        Returns:
            list[str]: List of errors that occurred during setting the values
        """
        errors = []
        for key_name, value in key_dict.items():
            key = self.get(key_name)
            if key:
                if hasattr(key, "set_without_update"):
                    key.set_without_update(value)
                else:
                    key.value = value
            else:
                if key.name.lower.startswith("HG_TEMP_KEY"):
                    continue
                hg_log(
                    f"Could not find key '{key_name}' while setting values", "WARNING"
                )
                errors.append("Key not found: " + key_name)

        self.update_human_from_key_change(context)

        return errors

    @injected_context
    def update_human_from_key_change(self, context: C = None) -> None:
        """Update the human mesh from the current live key values.

        This is used when updating a live key directly or after changing multiple
        livekeys with their `set_without_update` method.

        Args:
            context (C): Blender context. Defaults to None.
        """
        human = self._human
        human.hide_set(False)
        human.height._correct_armature(context)
        human.height._correct_eyes()
        human.height._correct_teeth()
        for mod in human.objects.body.modifiers:
            if mod.type == "MASK":
                mod.show_viewport = True
        for cloth_obj in human.clothing.outfit.objects:
            human.clothing.outfit.deform_cloth_to_human(context, cloth_obj)
        for shoe_obj in human.clothing.footwear.objects:
            human.clothing.footwear.deform_cloth_to_human(context, shoe_obj)

        human.objects.body.data.update()

    @staticmethod
    def _set_gender_specific(human: "Human") -> None:
        """Renames shapekeys, removing Male_ and Female_ prefixes according to gender.

        Args:
            human (Human): The human to set gnder specific keys for.
        """
        gender = human.gender
        hg_body = human.objects.body
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
        """Adds a new driver to the passed shapekey, using the passed dict as settings.

        Args:
            target_sk (bpy.types.key_block): shapekey to add driver to
            sett_dict (dict): dict containing copied settings of old drivers

        Returns:
            bpy.types.Driver: The newly created driver
        """
        driver = target_sk.driver_add("value").driver
        var = driver.variables.new()
        var.type = "TRANSFORMS"
        target = var.targets[0]  # type:ignore[index]
        target.id = self._human.objects.rig

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
            # pylint: disable-next=raise-missing-from
            raise KeyError(f"Key '{name}' not found")

    def __iter__(self) -> Iterable[Union[ShapeKeyItem, LiveKeyItem]]:
        yield from self.all_keys
