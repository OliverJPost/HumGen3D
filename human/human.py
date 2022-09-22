from __future__ import annotations

import json
import os
from sys import platform
from typing import TYPE_CHECKING, Generator, List, Tuple

import bpy
from bpy.types import Object
from mathutils import Vector
from matplotlib import PathLike

from ..backend import get_prefs, hg_delete, hg_log, refresh_pcoll, remove_broken_drivers
from .base.collections import add_to_collection
from .base.decorators import injected_context
from .base.exceptions import HumGenException
from .base.namegen import get_name
from .base.prop_collection import PropCollection
from .base.render import set_eevee_ao_and_strip
from .body.body import BodySettings
from .clothing.footwear import FootwearSettings
from .clothing.outfit import OutfitSettings
from .expression.expression import ExpressionSettings
from .eyes.eyes import EyeSettings
from .face.face import FaceKeys
from .hair.hair import HairSettings
from .height.height import HeightSettings
from .pose.pose import PoseSettings  # type:ignore
from .process.bake import BakeSettings
from .process.process import ProcessSettings
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
            # Cancel for legacy humans
            if not hasattr(rig_obj.HG, "is_legacy"):
                rig_obj.HG.is_legacy = True
                if strict_check:
                    raise HumGenException(
                        "Passed human created with a version of HG older than 4.0.0"
                    )
                return None
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
        human.body.set_experimental(preset_data["experimental"])

        # Set height from preset
        preset_height = preset_data["body_proportions"]["length"] * 100
        if 181 < preset_height < 182:
            # Fix for old presets that use wrong default height
            preset_height = 183.15
        human.height.set(preset_height, context)
        if gender == "male":
            human.shape_keys["Male"].value = 1.0

        # Set shape key values from preset
        for name, value in preset_data["livekeys"].items():
            human.shape_keys.livekey_set(name, value)

        # Set skin material from preset
        human.skin.texture._set_from_preset(preset_data["material"], context)
        human.skin._set_from_preset(preset_data["material"]["node_inputs"])

        # Set eyebrows from preset
        human.hair.eyebrows._set_from_preset(preset_data["eyebrows"])

        human._set_random_name()
        human.props.is_legacy = False

        return human

    # TODO return instances instead of rigs
    @classmethod
    def find_multiple_in_list(cls, objects):
        rigs = set(r for r in [Human.find(obj) for obj in objects] if r)
        return rigs

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

    @property  # TODO make cached
    def body(self) -> BodySettings:
        return BodySettings(self)

    @property  # TODO make cached
    def height(self) -> HeightSettings:
        return HeightSettings(self)

    @property  # TODO make cached
    def face(self) -> FaceKeys:
        return FaceKeys(self)

    @property
    def stretch_bones(self):
        stretch_bones = []
        for bone in self._human.pose_bones:
            if [c for c in bone.constraints if c.type == "STRETCH_TO"]:
                stretch_bones.append(bone)
        return PropCollection(stretch_bones)

    @property  # TODO make cached
    def pose(self) -> PoseSettings:
        return PoseSettings(self)

    @property  # TODO make cached
    def outfit(self) -> OutfitSettings:
        return OutfitSettings(self)

    @property  # TODO make cached
    def footwear(self) -> FootwearSettings:
        return FootwearSettings(self)

    @property  # TODO make cached
    def expression(self) -> ExpressionSettings:
        return ExpressionSettings(self)

    @property
    def process(self) -> ProcessSettings:
        return ProcessSettings(self)

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
    def lower_teeth_obj(self) -> Object:
        """Returns the lower teeth Blender object"""
        return next(
            obj
            for obj in self.children
            if "hg_teeth" in obj and "lower" in obj.name.lower()
        )

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
        delete_list = [
            self.rig_obj,
        ]
        for child in self.rig_obj.children:
            delete_list.append(child)
            for sub_child in child.children:
                delete_list.append(sub_child)

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

    @injected_context
    def render_thumbnail(
        self,
        folder=None,
        name="temp_thumbnail",
        focus: str = "full_body_front",
        context=None,
        resolution=256,
    ) -> PathLike:
        if not folder:
            folder = os.path.join(get_prefs().filepath, "temp_data")
        hg_rig = self.rig_obj
        type_sett = self._get_settings_dict_by_thumbnail_type(focus)

        hg_thumbnail_scene = bpy.data.scenes.new("HG_Thumbnail_Scene")
        old_scene = context.window.scene
        context.window.scene = hg_thumbnail_scene

        camera_data = bpy.data.cameras.new(name="Camera")
        camera_object = bpy.data.objects.new("Camera", camera_data)
        hg_thumbnail_scene.collection.objects.link(camera_object)

        camera_object.location = (
            Vector(
                (
                    type_sett["camera_x"],
                    type_sett["camera_y"],
                    hg_rig.dimensions[2],
                )
            )
            + hg_rig.location
        )

        hg_thumbnail_scene.camera = camera_object
        hg_thumbnail_scene.render.engine = "CYCLES"
        hg_thumbnail_scene.cycles.samples = 16
        try:
            hg_thumbnail_scene.cycles.use_denoising = True
        except Exception:
            pass

        new_coll = hg_thumbnail_scene.collection
        new_coll.objects.link(hg_rig)
        for child in hg_rig.children:
            new_coll.objects.link(child)

        hg_thumbnail_scene.render.resolution_y = resolution
        hg_thumbnail_scene.render.resolution_x = resolution

        self._make_camera_look_at_human(
            camera_object, hg_rig, type_sett["look_at_correction"]
        )
        camera_data.lens = type_sett["focal_length"]

        lights = []
        light_settings_enum = [
            (100, (-0.3, -1, 2.2)),
            (10, (0.38, 0.7, 1.83)),
            (50, (0, -1.2, 0)),
        ]
        for energy, location in light_settings_enum:
            point_light = bpy.data.lights.new(name=f"light_{energy}W", type="POINT")
            point_light.energy = energy
            point_light_object = bpy.data.objects.new("Light", point_light)
            point_light_object.location = Vector(location) + self.location
            hg_thumbnail_scene.collection.objects.link(point_light_object)
            lights.append(point_light_object)

        if not os.path.isdir(folder):
            os.makedirs(folder)

        hg_thumbnail_scene.render.image_settings.file_format = "JPEG"
        full_image_path = os.path.join(folder, f"{name}.jpg")
        hg_thumbnail_scene.render.filepath = full_image_path

        bpy.ops.render.render(write_still=True)

        for light in lights:
            hg_delete(light)

        hg_delete(camera_object)

        context.window.scene = old_scene

        bpy.data.scenes.remove(hg_thumbnail_scene)

        img = bpy.data.images.load(full_image_path)
        context.scene.HG3D.custom_content.preset_thumbnail = img
        return img.name

    def _get_settings_dict_by_thumbnail_type(self, thumbnail_type) -> dict:
        """Returns a dict with settings of how to configure the camera for this
        automatic thumbnail

        Args:
            thumbnail_type (str): key to the dict inside this function

        Returns:
            dict[str, float]:
                str: name of this property
                float: setting for camera property
        """
        type_settings_dict = {
            "head": {
                "camera_x": -1.0,
                "camera_y": -1.0,
                "focal_length": 135,
                "look_at_correction": 0.14,
            },
            "full_body_front": {
                "camera_x": 0,
                "camera_y": -2.0,
                "focal_length": 50,
                "look_at_correction": 0.9,
            },
            "full_body_side": {
                "camera_x": -2.0,
                "camera_y": -2.0,
                "focal_length": 50,
                "look_at_correction": 0.9,
            },
        }

        type_sett = type_settings_dict[thumbnail_type]
        return type_sett

    def make_camera_look_at_human(self, obj_camera, look_at_correction=0.9):
        """Makes the passed camera point towards a preset point on the human

        Args:
            obj_camera (bpy.types.Object): Camera object
            hg_rig (Armature): Armature object of human
            look_at_correction (float): Correction based on how much lower to
                point the camera compared to the top of the armature
        """

        hg_loc = self.location
        height_adjustment = (
            self.rig_obj.dimensions[2]
            - look_at_correction * 0.55 * self.rig_obj.dimensions[2]
        )
        hg_rig_loc_adjusted = Vector(
            (hg_loc[0], hg_loc[1], hg_loc[2] + height_adjustment)
        )
        loc_camera = obj_camera.location

        direction = hg_rig_loc_adjusted - loc_camera
        rot_quat = direction.to_track_quat("-Z", "Y")

        obj_camera.rotation_euler = rot_quat.to_euler()
