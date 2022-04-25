from __future__ import annotations

import json
import os
from sys import platform
from typing import TYPE_CHECKING, Any, Dict, List, Tuple, Union

import bpy
from bpy.props import FloatVectorProperty
from bpy.types import Context, Object, PropertyGroup

from ..old.blender_operators.common.common_functions import (
    HumGenException,
    add_to_collection,
    get_prefs,
)
from ..old.blender_operators.creation_phase.creation import set_eevee_ao_and_strip

if TYPE_CHECKING:
    from .creation_phase import CreationPhaseSettings


class Human:
    rig_obj: Object

    # creation_phase: CreationPhaseSettings
    # finalize_phase: FinalizePhaseSettings
    # phase: Union[CreationPhaseSettings, FinalizePhaseSettings]
    # hair: HairSettings
    # skin: SkinSettings
    # teeth: TeethSettings
    # eyes: EyeSettings

    def __init__(self, rig_obj):
        if not rig_obj.HG.ishuman:
            raise HumGenException("Did not pass a valid HG rig object")

        self.rig_obj = rig_obj

    @classmethod
    def from_existing(
        cls, existing_human: Object, strict_check: bool = True
    ) -> Human:
        if not isinstance(existing_human, Object):
            raise TypeError(
                f"Expected a Blender object, got {type(existing_human)}"
            )

        rig_obj = cls.find(existing_human)

        if not rig_obj and strict_check:
            raise HumGenException(
                f"Passed object '{existing_human.name}' is not part of an existing human"
            )

        return cls(rig_obj)

    @classmethod
    def from_preset(
        cls, preset: str, context: Context = None, prettify_eevee: bool = True
    ) -> Human:
        if not context:
            context = bpy.context

        preset_path = os.path.join(
            get_prefs().filepath, preset.replace("jpg", "json")
        )
        with open(preset_path) as json_file:
            preset_data = json.load(json_file)

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
            human.shape_keys[sk_name] = sk_value

        # Set skin material from preset
        human.skin.texture._set_from_preset(preset_data["material"])
        human.skin.nodes._set_from_preset(
            preset_data["material"]["node_inputs"]
        )

        # Set eyebrows from preset
        human.hair.eyebrows._set_from_preset(preset_data["eyebrows"])

        return human

    @classmethod
    def find(cls, obj, include_applied_batch_results=False) -> Object:
        """Checks if the passed object is part of a HumGen human

        This makes sure the add-on works as expected, even if a child object of the
        rig is selected.

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
        if not obj:
            return None
        elif not obj.HG.ishuman:
            if obj.parent:
                if obj.parent.HG.ishuman:
                    return obj.parent
            else:
                return None
        else:
            if all(cls._is_batch_result(obj)):
                if include_applied_batch_results:
                    return obj
                else:
                    return None

            return obj

    @classmethod
    def _is_batch_result(self, obj) -> Tuple[bool, bool]:
        return (
            obj.HG.batch_result,
            obj.HG.body_obj == obj,
        )

    def __repr__(self):
        pass  # TODO

    def __nonzero__(self) -> bool:
        return self.rig_obj

    @property
    def gender(self) -> str:
        """Gender of this human in ("male", "female")"""
        return self.rig_obj.HG.gender

    @property
    def name(self) -> str:
        pass  # TODO

    @name.setter
    def name(self, name: str):
        pass  # TODO

    @property
    def location(self) -> FloatVectorProperty:
        pass  # TODO

    @location.setter
    def location(self, location: FloatVectorProperty):
        pass  # TODO

    @property
    def rotation(self) -> FloatVectorProperty:
        pass  # TODO

    @rotation.setter
    def rotation(self, location: FloatVectorProperty):
        pass  # TODO

    @property
    def props(self) -> PropertyGroup:
        return self.rig_obj.HG

    @property
    def creation_phase(self):
        if not self._creation_phase:
            self._creation_phase = CreationPhaseSettings(self)
        return self._creation_phase

    def objects(self) -> List[Object]:
        return self.rig_obj.children + self.rig_obj

    def delete(self) -> None:
        pass  # TODO

    def finish_creation_phase(self) -> None:
        pass  # TODO

    def revert_to_creation_phase(self) -> None:
        pass  # TODO

    def _verify_body_object(self):
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
                self.body_obj = new_body[0]
                if "no_body" in self.rig_obj:
                    del self.rig_obj["no_body"]
            else:
                self.rig_obj = None["no_body"] = 1
        else:
            if "no_body" in self.rig_obj:
                del self.rig_obj["no_body"]

    @classmethod
    def _import_human(cls, context, gender) -> Object:
        """Import human from HG_HUMAN.blend and add it to scene
        Also adds some identifiers to the objects to find them later

        Args:
            sett (PropertyGroup)   : HumGen props
            pref (AddonPreferences): HumGen preferences

        Returns:
            tuple[str, bpy.types.Object*3]:
                gender  (str)   : gender of the imported human
                hg_rig  (Object): imported armature of human
                hg_body (Object): imported body of human
                hg_eyes (Object): imported eyes of human
        """
        # import from HG_Human file
        blendfile = os.path.join(
            get_prefs().filepath, "models", "HG_HUMAN.blend"
        )
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

        human.shape_keys._load_external()
        human.shape_keys._set_gender_specific()
        human.hair._delete_opposite_gender_specific()

        if platform == "darwin":
            human.body.material._mac_material_fix()

        human.creation_phase.body.material._set_gender_specific()
        human.creation_phase.body.material._remove_opposite_gender_specific()

        # new hair shader?
        for hairstyle in human.hair:
            hairstyle._add_quality_props()

        for mod in human.body.modifiers:
            mod.show_expanded = False

        return human
