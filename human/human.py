from __future__ import annotations

import json
import os
from sys import platform
from typing import TYPE_CHECKING, Generator, List, Tuple

import bpy
from bpy.types import Object  # type:ignore

from ..backend import get_prefs, hg_delete, hg_log, refresh_pcoll, remove_broken_drivers
from .base.collections import add_to_collection
from .base.decorators import injected_context
from .base.exceptions import HumGenException
from .base.namegen import get_name
from .base.render import set_eevee_ao_and_strip
from .creation_phase.creation_phase import CreationPhaseSettings
from .eyes.eyes import EyeSettings
from .finalize_phase.finalize_phase import FinalizePhaseSettings
from .hair.hair import HairSettings
from .shape_keys.shape_keys import ShapeKeySettings
from .skin.skin import SkinSettings

if TYPE_CHECKING:
    from bpy.props import FloatVectorProperty  # type:ignore
    from bpy.types import (  # type:ignore
        Context,
        EditBone,
        PoseBone,
        PropertyGroup,
        bpy_prop_collection,
    )


class Human:
    """Python representation of a Human Generator human.

    This class with its subclasses can be used to modify the
    Human Generator human inside Blender.
    """

    def __init__(self, rig_obj: Object, strict_check: bool = True):
        """Internal use only. Use .from_preset or .from_existing classmethods instead.

        Args:
            rig_obj (Object): Blender Armature object that is part of an existing human.
            strict_check (bool, optional): If True, an exception will be thrown if the
                rig_obj is incorrect. Defaults to True.

        Raises:
            HumGenException: Raised if the rig_obj is incorrect and strict_check is
                False.
        """
        if strict_check and not rig_obj.HG.ishuman:
            raise HumGenException("Did not pass a valid HG rig object")

        self.rig_obj = rig_obj

    def __repr__(self) -> str:
        """Return a string representation of this object."""
        return f"Human '{self.name}' [{self.gender.capitalize()}]in {self.phase} phase."

    @staticmethod
    @injected_context
    def get_preset_options(gender: str, context: Context = None) -> List[str]:
        """
        Return a list of human possible presets for the given gender.

        Choose one of the options to pass to Human.from_preset() constructor.

        Args:
          gender (str): string in ('male', 'female')
          context (Context): Blender context, uses bpy.context if not passed

        Returns:
          A list of starting human presets you can choose from
        """
        refresh_pcoll(None, context, "humans", gender_override=gender)
        # TODO more low level way
        return context.scene.HG3D["previews_list_humans"]

    @classmethod
    def from_existing(
        cls, existing_human: Object, strict_check: bool = True
    ) -> Human | None:
        """
        Creates a Human instance from a passed Blender object that is part of an existing Blender human.

        Args:
          existing_human (Object): The object that is part of the human you want to get.
          strict_check (bool): If True, the function will raise an exception if the passed object is not part of a
          human. IfnFalse, it will return None instead. Defaults to True

        Returns:
          A Human instance or None
        """

        if strict_check and not isinstance(existing_human, Object):
            raise TypeError(f"Expected a Blender object, got {type(existing_human)}")

        rig_obj = cls.find(existing_human)

        if rig_obj:
            return cls(rig_obj, strict_check=strict_check)
        elif strict_check:
            raise HumGenException(
                f"Passed object '{existing_human.name}' is not part of an existing human"
            )
        else:
            return None

    @classmethod
    @injected_context
    def from_preset(
        cls, preset: str, context: Context = None, prettify_eevee: bool = True
    ) -> Human:
        """
        Creates a new human in Blender based on the passed preset and returns a Human instance

        Args:
          preset (str): The name of the preset, as retrieved from Human.get_preset_options()
          context (Context): The Blender context.
          prettify_eevee (bool): If True, the AO and Strip settings will be set to settings that look nicer.
            Defaults to True

        Returns:
          A Human instance
        """
        preset_path = os.path.join(
            get_prefs().filepath, preset.replace("jpg", "json")[1:]  # TODO
        )

        with open(preset_path) as json_file:
            preset_data = json.load(json_file)

        gender = preset.split(os.sep)[2]

        human: Human = cls._import_human(context, gender)
        # remove broken drivers
        if prettify_eevee:
            set_eevee_ao_and_strip(context)

        # Set to experimental mode from preset
        human.creation_phase.body.set_experimental(preset_data["experimental"])

        # Set length from preset
        preset_length = preset_data["body_proportions"]["length"] * 100
        if 181 < preset_length < 182:
            # Fix for old presets that use wrong default length
            preset_length = 183.15
        human.creation_phase.length.set(preset_length, context)

        # Set shape key values from preset
        for sk_name, sk_value in preset_data["shapekeys"].items():
            human.shape_keys[sk_name].value = sk_value

        # Set skin material from preset
        human.skin.texture._set_from_preset(preset_data["material"], context)
        human.skin._set_from_preset(preset_data["material"]["node_inputs"])

        # Set eyebrows from preset
        human.hair.eyebrows._set_from_preset(preset_data["eyebrows"])

        human._set_random_name()

        return human

    @classmethod
    def find(
        cls, obj: Object, include_applied_batch_results: bool = False
    ) -> Object | None:
        """Checks if the passed object is part of a HumGen human. Does NOT return an instance

        Args:
            obj (bpy.types.Object): Object to check for if it's part of a HG human
            include_applied_batch_results (bool): If enabled, this function will
                return the body object for humans that were created with the batch
                system and which armatures have been deleted instead of returning
                the rig. Defaults to False

        Returns:
            Object: Armature of human (hg_rig) or None if not part of human (or body object
            if the human is an applied batch result and include_applied_batch_results
            is True)
        """
        # TODO clean up this mess

        if not obj:
            return None
        elif not obj.HG.ishuman:
            if obj.parent:
                if obj.parent.HG.ishuman:
                    return obj.parent
            else:
                return None
        else:
            if all(cls._obj_is_batch_result(obj)):
                if include_applied_batch_results:
                    return obj
                else:
                    return None

            return obj

    @staticmethod
    def _obj_is_batch_result(obj: Object) -> Tuple[bool, bool]:
        return (
            obj.HG.batch_result,
            obj.HG.body_obj == obj,
        )

    # endregion
    # region Properties

    @property
    def objects(self) -> Generator[Object]:
        """Yields all the Blender objects that the human consists of"""
        for child in self.rig_obj.children:
            for subchild in child.children:
                yield subchild
            yield child

        yield self.rig_obj

    @property
    def body_obj(self) -> Object:
        """Returns the human body Blender object"""
        return self.rig_obj.HG.body_obj

    @property
    def eye_obj(self) -> Object:
        """Returns the eye Blender object"""
        return self.eyes.eye_obj

    @property
    def phase(self) -> str:
        """String in ("creation", "finalize") to indicate what phase this human is in."""
        if self.props.phase in ["body", "face", "skin", "length"]:
            return "creation"
        else:
            return "finalize"

    @property
    def children(self) -> Generator[Object]:
        """A generator of all children of the rig object of the human. Does NOT yield subchildren."""
        for child in self.rig_obj.children:
            yield child

    # TODO as method?
    @property
    def is_batch_result(self) -> Tuple[bool, bool]:
        """Checks if this human was created with the batch system and if 'apply armature' was used.
        If apply armature was used, the human no longer has a rig object.
        """
        return self.props.batch_result, self.body_obj == self.rig_obj

    @property
    def gender(self) -> str:
        """Gender of this human in ("male", "female")"""
        return self.rig_obj.HG.gender

    @property
    def name(self) -> str:
        """Name of this human. Takes the name of the rig object and removes "HG_" prefix."""
        return self.rig_obj.name.replace("HG_", "")

    @name.setter
    def name(self, name: str):
        self.rig_obj.name = name

    @property
    def pose_bones(self) -> bpy_prop_collection[PoseBone]:
        """rig_obj.pose.bones prop collection"""
        return self.rig_obj.pose.bones

    @property
    def edit_bones(self) -> bpy_prop_collection[EditBone]:
        """rig_obj.data.edit_bones prop collection"""
        return self.rig_obj.data.edit_bones

    @property
    def location(self) -> FloatVectorProperty:
        """Location of the human in Blender global space. Retrieved from rig_obj.location"""
        return self.rig_obj.location

    @location.setter
    def location(self, location: FloatVectorProperty | Tuple[float]):
        self.rig_obj.location = location

    @property
    def rotation_euler(self) -> FloatVectorProperty:
        """Euler rotation of the human in Blender global space. Retrieved from rig_obj.rotation_euler"""
        return self.rig_obj.rotation_euler

    @rotation_euler.setter
    def rotation_euler(self, rotation: FloatVectorProperty | Tuple[float]):
        self.rig_obj.rotation_euler = rotation

    @property
    def props(self) -> PropertyGroup:
        """Custom object properties of the human, used by the add-on for storing metadata like
        gender, backup_human pointer, current phase, body_obj pointer. Points to rig_obj.HG"""
        return self.rig_obj.HG

    @property  # TODO make cached
    def creation_phase(self) -> CreationPhaseSettings:
        """
        Subclass used to control aspects that can ONLY be changed
        during the creation phase like human length, face proportions and body proportions.

        Raises:
            HumGenException: Raised if accessing on a human that is not in creation phase

        Returns:
            CreationPhaseSettings: Subclass containing creation_phase options
        """
        if self.phase != "creation":
            raise HumGenException(f"Human is in {self.phase}, not in creation phase.")
        return CreationPhaseSettings(self)

    @property  # TODO make cached
    def finalize_phase(self) -> FinalizePhaseSettings:
        """
        Subclass used to control aspects that can ONLY be changed
        during the finalize_phase like clothing and expression.

        Raises:
            HumGenException: Raised if accessing on a human that is not in finalize phase

        Returns:
            FinalizePhaseSettings: Subclass containing finalize_phase options
        """
        if self.phase != "finalize":
            raise HumGenException(f"Human is in {self.phase}, not in finalize phase.")
        return FinalizePhaseSettings(self)

    @property  # TODO make cached
    def skin(self) -> SkinSettings:
        """Subclass used to change the skin material of the human body."""
        return SkinSettings(self)

    @property
    def shape_keys(self) -> ShapeKeySettings:
        """Subclass used to access and change the shape keys of the body object. Iterating yields key_blocks."""
        return ShapeKeySettings(self)

    @property  # TODO make cached
    def eyes(self) -> EyeSettings:
        """Subclass used to access and change the eye object and material of the human."""
        return EyeSettings(self)

    @property  # TODO make cached
    def hair(self) -> HairSettings:
        """Subclass used to access and change the hair systems and materials of the human."""
        return HairSettings(self)

    def delete(self) -> None:
        """Delete the human from Blender. Will delete all meshes and objects that this human consists of, including
        the backup human.
        """
        backup_obj = self.props.backup
        humans = [obj for obj in bpy.data.objects if obj.HG.ishuman]

        copied_humans = [
            human
            for human in humans
            if human.HG.backup == backup_obj and human != self.rig_obj
        ]

        delete_list = [
            self.rig_obj,
        ]
        for child in self.rig_obj.children:
            delete_list.append(child)
            for sub_child in child.children:
                delete_list.append(sub_child)

        if not copied_humans and backup_obj:
            delete_list.append(backup_obj)
            for child in backup_obj.children:
                delete_list.append(child)

        for obj in delete_list:
            try:
                hg_delete(obj)
            except Exception:
                hg_log("Could not remove", obj)

    def hide_set(self, state: bool) -> None:
        """Switch between visible and hidden state for all objects this human consists of. Does NOT affect backup human.

        Args:
            state: Use True for hidden, False for visible
        """
        for obj in self.objects:
            obj.hide_set(state)
            obj.hide_viewport = state

    def _verify_body_object(self) -> None:
        """Update HG.body_obj if it's not a child of the rig. This would happen if
        the user duplicated the human manually
        """
        # TODO clean up this mess
        if self.body_obj not in self.objects and not self.props.batch:
            new_body = (
                [obj for obj in self.rig_obj.children if "hg_rig" in obj]
                if self.rig_obj.children
                else None
            )

            if new_body:
                self.props.body_obj = new_body[0]
                if "no_body" in self.rig_obj:
                    del self.rig_obj["no_body"]
            else:
                self.rig_obj["no_body"] = 1
        else:
            if "no_body" in self.rig_obj:
                del self.rig_obj["no_body"]

    # TODO this method is too broad
    @classmethod
    def _import_human(cls, context: Context, gender: str) -> Human:
        """
        It imports the human model from the HG_Human.blend file, sets it up correctly, and returns a Human instance

        Args:
          context: The context of the current scene.
          gender: "male" or "female"

        Returns:
          A Human object
        """
        # import from HG_Human file

        blendfile = os.path.join(get_prefs().filepath, "models", "HG_HUMAN.blend")
        with bpy.data.libraries.load(blendfile, link=False) as (_, data_to):
            data_to.objects = [
                "HG_Rig",
                "HG_Body",
                "HG_Eyes",
                "HG_TeethUpper",
                "HG_TeethLower",
            ]

        # link to scene
        hg_rig, hg_body, hg_eyes, *hg_teeth = data_to.objects
        scene = context.scene
        for obj in data_to.objects:
            scene.collection.objects.link(obj)
            add_to_collection(context, obj)

        hg_rig.location = context.scene.cursor.location

        # set custom properties for identifying
        hg_body["hg_body"] = hg_eyes["hg_eyes"] = 1
        for tooth in hg_teeth:
            tooth["hg_teeth"] = 1

        props = hg_rig.HG

        props.ishuman = True
        props.gender = gender
        props.phase = "body"
        props.body_obj = hg_body
        props.length = hg_rig.dimensions[2]

        human = cls(hg_rig)
        human.shape_keys._load_external(human, context)
        human.shape_keys._set_gender_specific(human)
        human.hair._delete_opposite_gender_specific()

        if platform == "darwin":
            human.skin._mac_material_fix()

        human.skin._set_gender_specific()
        human.skin._remove_opposite_gender_specific()

        # new hair shader?
        human.hair._add_quality_props()

        for mod in human.body_obj.modifiers:
            mod.show_expanded = False

        remove_broken_drivers()

        return human

    def _set_random_name(self) -> None:
        """Randomizes name of human. Will add "HG_" prefix"""
        taken_names = []
        for obj in bpy.data.objects:
            if not obj.HG.ishuman:
                continue
            taken_names.append(obj.name[4:])

        # generate name
        name = get_name(self.gender)

        # get new name if it's already taken
        i = 0
        while i < 10 and name in taken_names:
            name = get_name(self.gender)
            i += 1

        self.name = "HG_" + name
