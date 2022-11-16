# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements class for the process system of HumGen3D."""

import json
import os
from typing import TYPE_CHECKING, Any, Dict, Optional

import bpy
from HumGen3D.backend.logging import hg_log
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C

from .lod import LodSettings

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from .bake import BakeSettings


def _fill_tokens(
    name: str, human_name: str, original_name: str, custom_token: str, suffix: str
) -> str:
    kwargs = {}
    if "{name}" in name:
        kwargs["name"] = human_name
    if "{original_name}" in name:
        kwargs["original_name"] = original_name
    if "{custom}" in name:
        kwargs["custom"] = custom_token
    name = name.format(**kwargs)
    if suffix:
        name += suffix
    return name


class SCRIPT_ITEM(bpy.types.PropertyGroup):
    """Item for collectionproprety representing a script that will be run."""

    _register_priority = 2
    name: bpy.props.StringProperty()
    menu_open: bpy.props.BoolProperty(default=False)


class ProcessSettings:
    """Class for accessing methods and subclasses for processing the human."""

    def __init__(self, human: "Human") -> None:
        self._human = human

    @property
    def baking(self) -> BakeSettings:
        """Gives access to the baking settings.

        Returns:
            BakeSettings: The baking settings.
        """
        return BakeSettings(self._human)

    @property
    def lod(self) -> LodSettings:
        """Gives access to the LOD settings.

        Returns:
            LodSettings: The LOD settings.
        """
        return LodSettings(self._human)

    @property
    def has_haircards(self) -> bool:
        """Checks if haircards are present.

        Returns:
            bool: True if haircards are present.
        """
        return "haircard" in self._human.objects.rig

    @property
    def was_baked(self) -> bool:
        """Checks if materials were baked.

        Returns:
            bool: True if materials were baked.
        """
        return "hg_baked" in self._human.objects.rig

    @property
    def is_lod(self) -> bool:
        """Checks if the human is an LOD.

        Returns:
            bool: True if the human is an LOD.
        """
        return "lod" in self._human.objects.rig

    @property
    def rig_renamed(self) -> bool:
        """Checks if the rig was renamed.

        Returns:
            bool: True if the rig was renamed.
        """
        return "bones_renamed" in self._human.objects.rig

    @property
    def parts_were_renamed(self) -> bool:
        """Checks if the parts were renamed.

        Returns:
            bool: True if the parts were renamed.
        """
        return "parts_renamed" in self._human.objects.rig

    def rename_bones_from_json(
        self, json_string: Optional[str] = None, json_path: Optional[str] = None
    ) -> None:
        """Renames the bones of the human according to the provided json str or file.

        Args:
            json_string (Optional[str]): The json string. Defaults to None.
                ONLY ONE OF json_string and json_path may be provided.
            json_path (Optional[str]): The path to the json file. Defaults to
                None.

        Raises:
            ValueError: If both json_string and json_path are provided.
        """
        if json_path and json_string:
            raise ValueError("Only one of json_string and json_path may be provided.")
        if json_path:
            with open(json_path, "r") as f:
                data = json.load(f)
        else:
            data = json.loads(json_string)  # type:ignore

        left_suffix = data["suffix_L"]
        right_suffix = data["suffix_R"]

        for bone_name, new_name in data.items():
            matching_bones = [
                bone
                for bone in self._human.pose_bones
                if bone["original_name"].startswith(bone_name)
            ]
            if len(matching_bones) == 2:
                left_bone = next(
                    b
                    for b in matching_bones
                    if b["original_name"].endswith((".L", "_L"))
                )
                right_bone = next(
                    b
                    for b in matching_bones
                    if b["original_name"].endswith((".R", "_R"))
                )
                left_bone.name = new_name + left_suffix
                right_bone.name = new_name + right_suffix
            elif len(matching_bones) == 1:
                matching_bones[0].name = new_name

    def rename_objects_from_json(
        self,
        json_string: Optional[str] = None,
        json_path: Optional[str] = None,
        custom_token: str = "",
        suffix: str = "",
    ) -> None:
        """Renames the objects of the human according to the provided json str or file.

        Args:
            json_string (Optional[str]): The json string. Defaults to None.
            json_path (Optional[str]): The path to the json file. Defaults to
                None.
            custom_token (str): A custom token that can be inserted into
                name templates.
            suffix (str): A suffix that will be appended to the new names.

        Raises:
            ValueError: If both json_string and json_path are provided.
        """
        if json_path and json_string:
            raise ValueError("Only one of json_string and json_path may be provided.")
        if json_path:
            with open(json_path, "r") as f:
                data = json.load(f)
        else:
            data = json.loads(json_string)  # type:ignore

        for obj_type, new_name in data.items():
            if obj_type in ("bl_rna", "rna_type", "name", "materials", "use_suffix"):
                continue

            if obj_type == "clothing":
                objs = list(self._human.clothing.outfit.objects) + list(
                    self._human.clothing.footwear.objects
                )
            else:
                try:
                    objs = [getattr(self._human, obj_type)]
                except AttributeError:
                    hg_log("No object of type {} found.".format(obj_type))
                    continue

            for obj in objs:
                if not obj:
                    continue

                new_name = _fill_tokens(
                    new_name, self._human.name, obj.name, custom_token, suffix
                )
                obj.name = new_name

    def rename_materials_from_json(
        self,
        json_string: Optional[str] = None,
        json_path: Optional[str] = None,
        custom_token: str = "",
        suffix: str = "",
    ) -> None:
        """Renames materials of the human according to the provided json str or file.

        Args:
            json_string (Optional[str]): The json string. Defaults to None.
            json_path (Optional[str]): The path to the json file. Defaults to
                None.
            custom_token (str): A custom token that can be inserted into
                name templates.
            suffix (str): A suffix that will be appended to the new names.

        Raises:
            ValueError: If both json_string and json_path are provided.
        """
        if json_path and json_string:
            raise ValueError("Only one of json_string and json_path may be provided.")
        if json_path:
            with open(json_path, "r") as f:
                data = json.load(f)
        else:
            data = json.loads(json_string)  # type:ignore

        for mat_type, new_name in data.items():
            if mat_type in ("bl_rna", "rna_type", "name", "materials", "use_suffix"):
                continue
            mats = getattr(self._human.materials, mat_type)
            if not isinstance(mats, list):
                mats = [mats]

            for mat in mats:
                if not mat:
                    continue
                new_name = _fill_tokens(
                    new_name, self._human.name, mat.name, custom_token, suffix
                )
                mat.name = new_name

    @staticmethod
    @injected_context
    def save_settings_to_template(
        folder: str, template_name: str, context: C = None
    ) -> str:
        """Saves the current settings to a template file.

        Args:
            folder (str): The folder to save the template to.
            template_name (str): The name of the template.
            context (C): The Blender context. Defaults to None.

        Returns:
            str: The path to the template file.
        """
        if not os.path.isdir(folder):
            os.makedirs(folder)
        pr_sett = context.scene.HG3D.process

        settings_dict = {}
        if pr_sett.baking_enabled:
            settings_dict["baking"] = ProcessSettings._props_from_propgroup(
                pr_sett.baking
            )

        if pr_sett.haircards_enabled:
            settings_dict["haircards"] = ProcessSettings._props_from_propgroup(
                pr_sett.haircards
            )

        if pr_sett.rig_renaming_enabled:
            settings_dict["rig_renaming"] = ProcessSettings._props_from_propgroup(
                pr_sett.rig_renaming
            )

        if pr_sett.renaming_enabled:
            settings_dict["renaming"] = ProcessSettings._props_from_propgroup(
                pr_sett.renaming
            )
            settings_dict["material_renaming"] = ProcessSettings._props_from_propgroup(
                pr_sett.renaming.materials
            )

        if pr_sett.modapply_enabled:
            settings_dict["modapply"] = ProcessSettings._props_from_propgroup(
                pr_sett.modapply
            )

        if pr_sett.lod_enabled:
            settings_dict["lod"] = ProcessSettings._props_from_propgroup(pr_sett.lod)

        full_path = os.path.join(folder, template_name + ".json")
        with open(full_path, "w") as f:
            json.dump(settings_dict, f, indent=4)

        return full_path

    @staticmethod
    def _props_from_propgroup(prop_group: bpy.types.PropertyGroup) -> Dict[str, Any]:
        prop_dict = {}
        for prop in prop_group.bl_rna.properties:
            if prop.identifier in ("rna_type", "name"):
                continue
            attr = getattr(prop_group, prop.identifier)
            prop_dict[prop.identifier] = (
                attr if prop.identifier != "materials" else None
            )

        return prop_dict

    @staticmethod
    @injected_context
    def set_settings_from_template(template_path: str, context: C = None) -> None:
        """Sets the process settings from a template file.

        Args:
            template_path (str): The path to the template file.
            context (C): The Blender context. Defaults to None.
        """
        with open(template_path, "r") as f:
            data = json.load(f)

        pr_sett = context.scene.HG3D.process

        # Disable all categories
        for prop in pr_sett.bl_rna.properties:
            if "_enabled" in prop.identifier:
                setattr(pr_sett, prop.identifier, False)

        for attr, prop_dict in data.items():
            if attr == "material_renaming":
                continue

            # Set enabled = True because attr being in the dict means it was enabled
            setattr(pr_sett, f"{attr}_enabled", True)
            prop_group = getattr(pr_sett, attr)

            for prop_name, prop_value in prop_dict.items():
                # Set the nested material properties if encountered
                if prop_name == "materials":
                    mat_renaming_data = data["material_renaming"]
                    for mat_prop_name, mat_prop_value in mat_renaming_data.items():
                        setattr(
                            pr_sett.renaming.materials, mat_prop_name, mat_prop_value
                        )
                else:
                    setattr(prop_group, prop_name, prop_value)
