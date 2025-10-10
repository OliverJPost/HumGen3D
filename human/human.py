# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements main Human class, the starting point for all human related operations."""

from __future__ import annotations

import contextlib
import json
import os
import random
import time
from typing import Any, Iterable, List, Literal, Optional, Tuple, Union, cast

import bpy
from bpy.props import FloatVectorProperty  # type:ignore
from bpy.types import Object  # type:ignore
from bpy.types import Context, Image, bpy_prop_collection  # type:ignore
from HumGen3D.backend import preview_collections
from HumGen3D.backend.content.content_saving import save_thumb
from HumGen3D.backend.preferences.preference_func import get_addon_root
from HumGen3D.backend.properties.object_props import HG_OBJECT_PROPS
from HumGen3D.common import find_hg_rig, is_legacy
from HumGen3D.common.context import context_override
from HumGen3D.common.type_aliases import BpyEnum, C, GenderStr
from HumGen3D.human.age import AgeSettings
from HumGen3D.human.materials import MaterialSettings
from HumGen3D.user_interface.documentation.feedback_func import ShowMessageBox
from mathutils import Vector

from .process.export import ExportBuilder
from ..backend import get_prefs, hg_delete, remove_broken_drivers
from ..common.collections import add_to_collection
from ..common.decorators import injected_context, verify_addon
from ..common.exceptions import HumGenException
from ..common.materials import verify_no_undefined_nodes_in_mat
from ..common.render import set_eevee_ao_and_strip
from .body.body import BodySettings
from .clothing.clothing import ClothingSettings
from .expression.expression import ExpressionSettings
from .eyes.eyes import EyeSettings
from .face.face import FaceSettings
from .hair.hair import HairSettings
from .height.height import HeightSettings
from .keys.keys import KeySettings
from .objects import ObjectCollection
from .pose.pose import PoseSettings, remove_broken_constraints  # type:ignore
from .process.process import ProcessSettings
from .skin.skin import SkinSettings

import HumGen3D

class Human:
    """Python representation of a Human Generator human.

    This class with its subclasses can be used to modify the
    Human Generator human inside Blender.
    """

    def __init__(self, rig_obj: Object, strict_check: bool = True):
        """Internal use only. Use .from_preset or .from_existing classmethods instead.

        Args:
            rig_obj (Object): Blender Armature object that is part of an existing human.
            strict_check (bool): If True, an exception will be thrown if the
                rig_obj is incorrect. Defaults to True.

        Raises:
            HumGenException: Raised if the rig_obj is incorrect and strict_check is
                False.
        """
        if strict_check and not rig_obj.HG.ishuman:
            raise HumGenException("Did not pass a valid HG rig object")

        self._rig_obj = rig_obj

    @staticmethod
    @verify_addon
    @injected_context
    def get_preset_options(
        gender: GenderStr, category: str = "All", context: C = None
    ) -> List[str]:
        """
        Return a list of human possible presets for the given gender.

        Choose one of the options to pass to Human.from_preset() constructor.

        Args:
            gender (GenderStr): string in ('male', 'female')
            category (str): Category to find presets for. Defaults to 'All'. You can
                get a list of all categories by calling Human.get_categories()
            context (C): Blender context, uses bpy.context if not passed

        Returns:
            A list of starting human presets you can choose from
        """
        preview_collections["humans"].populate(context, gender, subcategory=category)
        return [
            option[0] for option in preview_collections["humans"].pcoll["humans"][1:]
        ]

    # Do not remove unused arguments
    @staticmethod
    def _get_full_options(_self: Any, context: C = None) -> BpyEnum:
        """Internal method for getting preview collection items.

        Args:
            _self (Any): Unused, necessary for Blender callback pattern
            context (C): Unused, necessary for Blender callback pattern

        Returns:
            BpyEnum: Enum of preview collection items
        """
        pcoll = preview_collections.get("humans").pcoll
        if not pcoll:
            return [
                ("none", "Reload category below", "", 0),
            ]

        return cast(BpyEnum, pcoll["humans"])

    @classmethod
    @verify_addon
    def from_existing(
        cls, existing_human: Object, strict_check: bool = True
    ) -> Human | None:
        """New instance from a passed Blender object that is part of an existing human.

        Args:
            existing_human (Object): Object that is part of the human you want to get.
            strict_check (bool): If True, the method will raise an exception if the
                passed object is not part of a human. If False, it will return None
                instead. Defaults to True

        Returns:
            A Human instance or None

        Raises:
            TypeError: Raised if the passed object is not a Blender object.
            HumGenException: Raised if the passed object is not part of a human and
                strict_check is True. This will also raise if the passed object is
                part of a legacy human.
        """
        if strict_check and not isinstance(existing_human, Object):
            raise TypeError(f"Expected a Blender object, got {type(existing_human)}")

        rig_obj = find_hg_rig(existing_human, include_legacy=True)

        if rig_obj:
            if not is_legacy(rig_obj):
                return cls(rig_obj, strict_check=strict_check)
            # Cancel for legacy humans
            else:
                if strict_check:
                    raise HumGenException(
                        "Passed human created with a version of HG older than 4.0.0"
                    )
                return None

        elif strict_check:
            raise HumGenException(
                f"Passed object '{existing_human.name}' is not part of an existing human"  # noqa E501
            )
        else:
            return None

    @classmethod
    @verify_addon
    @injected_context
    def from_preset(
        cls,
        preset: str,
        context: C = None,
        prettify_eevee: bool = True,
        from_batch_generator: bool = False,
    ) -> Human:
        """Creates human in Blender based on passed preset and returns Human instance.

        Args:
            preset (str): The name of the preset, as retrieved from
                Human.get_preset_options()
            context (C): The Blender context. Defaults to bpy.context if None
            prettify_eevee (bool): If True, the AO and Strip settings will be set to
                settings that look nicer. Defaults to True
            from_batch_generator (bool): If True, some settings will be skipped as they
                are defined in the batch generator. Defaults to False

        Returns:
            Human: A Human instance
        """
        preset_path = os.path.join(
            get_prefs().filepath, preset.replace("jpg", "json")  # TODO
        )

        if prettify_eevee:
            set_eevee_ao_and_strip(context)

        with open(preset_path) as json_file:
            preset_data = json.load(json_file)

        gender = preset.split(os.sep)[1]

        human = cls._import_human(context, gender)

        def scrub(obj: dict[Any, Any], bad_key: str) -> None:
            if isinstance(obj, dict):
                for key in list(obj.keys()):
                    if key == bad_key:
                        obj[key] = None
                    else:
                        scrub(obj[key], bad_key)
            elif isinstance(obj, list):
                for i in reversed(range(len(obj))):
                    if obj[i] == bad_key:
                        obj[i] = None
                    else:
                        scrub(obj[i], bad_key)
            else:
                pass

        # Set human settings from preset dictionary
        errors = []
        for attr, data in preset_data.items():
            if attr == 'height':
                continue
            # Do not set hairstyles or clothes if we are in batch generator mode
            if from_batch_generator and attr not in ("skin", "age", "height"):
                scrub(data, "set")

            from_dict_method = getattr(human, attr).set_from_dict
            try:
                occurred_errors = from_dict_method(data, context=context)
            except TypeError:
                occurred_errors = from_dict_method(data)

            errors.extend(occurred_errors)
        human._set_random_name()

        from HumGen3D import bl_info

        human.props.version = HumGen3D.__version__
        human.props.hashes["$pose"] = str(hash(human.pose))
        human.props.hashes["$outfit"] = str(hash(human.clothing.outfit))
        human.props.hashes["$footwear"] = str(hash(human.clothing.footwear))
        human.props.hashes["$hair"] = str(hash(human.hair.regular_hair))

        human._active = preset

        if errors:
            error_lines = "\n".join(errors)
            ShowMessageBox(f"Occurred errors: {error_lines}", "Error")

        return human

    @staticmethod
    def get_categories(gender: GenderStr) -> list[str]:
        """Get a list of categories the human presets are divided into.

        Args:
            gender (GenderStr): Gender to find categories for

        Returns:
            list[str]: List of categories, choose one to pass to get_preset_options()
        """
        return [option[0] for option in Human._get_categories(gender)]

    @staticmethod
    def _get_categories(gender: GenderStr, include_all: bool = True) -> BpyEnum:  # noqa
        return preview_collections["humans"].find_folders(
            gender, include_all=include_all
        )

    # endregion
    # region Properties

    @property
    def body(self) -> BodySettings:
        """Points to the body settings of the human.

        Returns:
            BodySettings: Class instance for changing body proportions
        """
        return BodySettings(self)

    @property
    def height(self) -> HeightSettings:
        """Points to the height settings of the human.

        Returns:
            HeightSettings: Class instance for changing height of human
        """
        return HeightSettings(self)

    @property
    def face(self) -> FaceSettings:
        """Points to the face settings of the human.

        Returns:
            FaceSettings: Class instance for changing face proportions of human
        """
        return FaceSettings(self)

    @property
    def age(self) -> AgeSettings:
        """Points to the age settings of the human.

        Returns:
            AgeSettings: Class instance for changing age of human
        """
        return AgeSettings(self)

    @property
    def pose(self) -> PoseSettings:
        """Points to the pose settings of the human.

        Returns:
            PoseSettings: Class instance for changing pose of human
        """
        return PoseSettings(self)

    @property
    def clothing(self) -> ClothingSettings:
        """Points to the clothing settings of the human.

        Returns:
            ClothingSettings: Class instance for changing clothing of human
        """
        return ClothingSettings(self)

    @property
    def expression(self) -> ExpressionSettings:
        """Points to the expression settings of the human.

        Returns:
            ExpressionSettings: Class instance for changing expression of human
        """
        return ExpressionSettings(self)

    @property
    def process(self) -> ProcessSettings:
        """Points to the class used by the process tab of HumGen.

        Returns:
            ProcessSettings: Class instance for processing the human
        """
        return ProcessSettings(self)

    @property
    def materials(self) -> MaterialSettings:
        """Points to the class giving access to different materials of human.

        Returns:
            MaterialSettings: Class instance for accessing materials of human
        """
        return MaterialSettings(self)

    @property
    def objects(self) -> ObjectCollection:
        """Get a collection of all objects that are part of the human.

        Returns:
            ObjectCollection: Collection of Blender objects that make up the human, with
                properties for accessing specific ones.
        """
        return ObjectCollection(self._rig_obj)

    @property
    def children(self) -> Iterable[Object]:
        """A generator of all children of the rig object of the human.

        Does NOT yield subchildren.

        Yields:
            Object: A Blender object that is a child of the rig object of the human
        """
        yield from self.objects.rig.children

    @property
    def gender(self) -> GenderStr:
        """Gender of this human in ("male", "female").

        Returns:
            GenderStr: Gender of this human in ("male", "female")
        """
        return cast(str, self.objects.rig.HG.gender)

    @property
    def pose_bones(self) -> "bpy_prop_collection":
        """Pose bones of the human rig.

        Returns:
            bpy_prop_collection: Pose bones of the human rig
        """
        return cast("bpy_prop_collection", self.objects.rig.pose.bones)

    @property
    def props(self) -> HG_OBJECT_PROPS:
        """Custom object properties of the human.

        Used by the add-on for storing metadata like gender, backup_human pointer,
        current phase, body_obj pointer. Points to rig_obj.HG

        Returns:
            HG_OBJECT_PROPS: Custom object properties of the human stored on
                human.objects.rig.HG
        """
        return cast(HG_OBJECT_PROPS, self.objects.rig.HG)

    @property
    def skin(self) -> SkinSettings:
        """Subclass used to change the skin material of the human body.

        Returns:
            SkinSettings: Class instance for changing skin material of human
        """
        return SkinSettings(self)

    @property
    def keys(self) -> KeySettings:
        """Subclass used to access and change the shape keys of the body object.

        Iterating yields key_blocks.

        Returns:
            KeySettings: Class instance for accessing and changing both shape keys and
                live keys of human.
        """
        return KeySettings(self)

    @property
    def eyes(self) -> EyeSettings:
        """Subclass used to access and change the eye object and material.

        Returns:
            EyeSettings: Class instance for accessing and changing eye object and
                material.
        """
        return EyeSettings(self)

    @property
    def hair(self) -> HairSettings:
        """Subclass used to access and change the hair systems and materials.

        Returns:
            HairSettings: Class instance for accessing and changing hair systems and
                materials.
        """
        return HairSettings(self)

    @property
    def export(self) -> ExportBuilder:
        """Subclass used to export the human.

        Returns:
            ExportBuilder: Class instance for exporting the human
        """
        return ExportBuilder(self)

    @property
    def location(self) -> FloatVectorProperty:
        """Location of the human in Blender global space.

        Retrieved from rig_obj.location

        Returns:
            FloatVectorProperty: Location of the human in Blender global space
        """
        return self.objects.rig.location

    @location.setter
    def location(self, location: Tuple[float, float, float]) -> None:  # noqa
        """Set the location of the human in Blender global space.

        Args:
            location (Tuple[float, float, float]): Location to set the human to
        """
        self.objects.rig.location = location

    @property
    def rotation_euler(self) -> FloatVectorProperty:
        """Euler rotation of the human in Blender global space.

        Retrieved from rig_obj.rotation_euler

        Returns:
            FloatVectorProperty: Euler rotation of the human in Blender global space
        """
        return self.objects.rig.rotation_euler

    @rotation_euler.setter
    def rotation_euler(self, rotation: Tuple[float, float, float]) -> None:  # noqa
        """Set the Euler rotation of the human in Blender global space.

        Args:
            rotation (Tuple[float, float, float]): Euler rotation to set the human to
        """
        self.objects.rig.rotation_euler = rotation

    @property
    def name(self) -> str:
        """Name of this human. Takes name of rig object and removes HG_ prefix.

        Returns:
            str: Name of this human
        """
        return cast(str, self.objects.rig.name.replace("HG_", ""))

    @name.setter
    def name(self, name: str) -> None:  # noqa
        """Set the name of this human. Sets name of rig object.

        Args:
            name (str): Name to set the human to
        """
        self.objects.rig.name = name

    @property
    def is_trial(self) -> bool:
        """Whether this human is a trial human.

        Returns:
            bool: Whether this human is a trial human
        """
        return "HG_TRIAL" in self.objects.rig

    @property
    def _active(self) -> str:
        return self.objects.rig.HG.active_human_preset  # type: ignore[index]

    @_active.setter
    def _active(self, value: str) -> None:
        self.objects.rig.HG.active_human_preset = value

    def delete(self) -> None:
        """Delete the human from Blender.

        Will delete all meshes and objects that this human consists of, including
        the backup human.
        """
        delete_list = [
            self.objects.rig,
        ]
        for child in self.objects.rig.children:
            delete_list.append(child)
            for sub_child in child.children:
                delete_list.append(sub_child)

        for obj in delete_list:
            hg_delete(obj)

    # TODO this method is too broad
    @classmethod
    def _import_human(cls, context: Context, gender: str) -> Human:
        """Import human from HG_HUMAN.blend.

        It imports the human model from the HG_Human.blend file, sets it up correctly,
        and returns a Human instance # TODO split up

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
        human.keys._set_gender_specific(human)
        human.hair._delete_opposite_gender_specific()

        human.skin._set_gender_specific()
        human.skin._remove_opposite_gender_specific()

        # new hair shader?
        human.hair._add_quality_props()

        for mod in human.objects.body.modifiers:
            mod.show_expanded = False

        remove_broken_drivers()
        remove_broken_constraints(hg_rig)

        return human

    def hide_set(self, state: bool) -> None:
        """Switch between visible and hidden state for all objects of this human.

        Args:
            state: Use True for hidden, False for visible
        """
        for obj in self.objects:
            obj.hide_set(state)
            obj.hide_viewport = state

    def make_camera_look_at_human(
        self, obj_camera: Object, look_at_correction: float = 0.9
    ) -> None:
        """Makes the passed camera point towards a preset point on the human.

        Args:
            obj_camera (Object): Camera object
            look_at_correction (float): Correction based on how much lower to
                point the camera compared to the top of the armature
        """
        hg_loc = self.location
        height_adjustment = (
            self.objects.rig.dimensions[2]
            - look_at_correction * 0.55 * self.objects.rig.dimensions[2]
        )
        hg_rig_loc_adjusted = Vector(
            (hg_loc[0], hg_loc[1], hg_loc[2] + height_adjustment)  # type:ignore[index]
        )

        direction = hg_rig_loc_adjusted - obj_camera.location  # type:ignore[operator]
        rot_quat = direction.to_track_quat("-Z", "Y")

        obj_camera.rotation_euler = rot_quat.to_euler()  # type:ignore

    @injected_context
    def save_to_library(
        self,
        name: str,
        category: str = "Custom",
        thumbnail: Optional[Image] = None,
        context: C = None,
    ) -> None:
        """Save the human with it's current settings as a starting human preset.

        Will add it to the content library.

        Args:
            name (str): Name of the preset
            category (str): Category of the preset, defaults to "Custom". Creates
                new category if it doesn't exist yet.
            thumbnail (Image): Image to use as thumbnail for the preset. If None no
                thumbnail will be added.
            context (C): The context of the current scene.
        """
        folder = os.path.join(get_prefs().filepath, "models", self.gender, category)

        if not os.path.isdir(folder):
            os.makedirs(folder)

        if thumbnail:
            save_thumb(folder, thumbnail.name, name)

        preset_data = self.as_dict()

        with open(os.path.join(folder, f"{name}.json"), "w") as f:
            json.dump(preset_data, f, indent=4)

        context.scene.HG3D.content_saving_ui = False

        preview_collections["humans"].refresh(context)

    def as_dict(self) -> dict[str, Any]:
        """Returns a dictionary representation of this human.

        This is used for saving the human to a JSON file.

        Returns:
            A dictionary representation of this human.
        """
        return_dict = {}

        for attr in ("age", "keys", "skin", "eyes", "height", "hair", "clothing"):
            return_dict[attr] = getattr(self, attr).as_dict()

        return return_dict

    @injected_context
    def duplicate(self, context: C = None) -> Human:
        """Make a copy of this human. Will both duplicate in Blender and Python.

        All relations will be corrected:

        Args:
            context (C): The context of the current scene.

        Returns:
            The duplicated human as Python instance.
        """
        rig_copy = self.objects.rig.copy()
        rig_copy.data = self.objects.rig.data.copy()
        context.collection.objects.link(rig_copy)
        add_to_collection(context, rig_copy)

        for obj in self.children:
            obj_copy = obj.copy()
            obj_copy.data = obj.data.copy()
            obj_copy.parent = rig_copy
            for mod in obj_copy.modifiers:
                if mod.type == "ARMATURE":
                    mod.object = rig_copy

            # Reassign body_obj pointerproperty
            if obj == self.objects.body:
                body_copy = obj_copy
                rig_copy.HG.body_obj = body_copy

            context.collection.objects.link(obj_copy)
            add_to_collection(context, obj_copy)

        new_human = Human.from_existing(obj_copy)
        jaw_bone = new_human.pose.get_posebone_by_original_name("jaw")
        damped_track_modifier = jaw_bone.constraints["Damped Track"].target = body_copy

        return new_human

    @injected_context
    def render_thumbnail(
        self,
        folder: Optional[str] = None,
        name: str = "temp_thumbnail",
        focus: str = "full_body_front",
        context: C = None,
        resolution: int = 256,
        white_material: bool = False,
    ) -> str:
        """Render a thumbnail of this human.

        Args:
            folder (str): Folder to save the thumbnail to. If None the default
                folder will be used.
            name (str): Name of the thumbnail. Will be used as filename.
            focus (str): Focus of the thumbnail. Can be one of: "full_body_front",
                "full_body_side", "head_front", "head_side".
            context (C): The context of the current scene.
            resolution (int): Resolution of the thumbnail. Defaults to 256.
            white_material (bool): Use a white material for the human. Defaults to
                False.

        Returns:
            Path to the rendered thumbnail.
        """
        if not folder:
            folder = os.path.join(get_prefs().filepath, "temp_data")
        hg_rig = self.objects.rig
        type_sett = self._get_settings_dict_by_thumbnail_type(focus)

        hg_thumbnail_scene = bpy.data.scenes.new("HG_Thumbnail_Scene")
        old_scene = context.window.scene
        context.window.scene = hg_thumbnail_scene

        camera_data = bpy.data.cameras.new(name="Camera")
        camera_object = bpy.data.objects.new(
            "Camera", camera_data  # type:ignore[arg-type]
        )
        hg_thumbnail_scene.collection.objects.link(camera_object)

        camera_object.location = (
            Vector(
                (
                    type_sett["camera_x"],
                    type_sett["camera_y"],
                    hg_rig.dimensions[2],
                )
            )
            + hg_rig.location  # type:ignore[operator]
        )

        hg_thumbnail_scene.camera = camera_object
        hg_thumbnail_scene.render.engine = "CYCLES"
        hg_thumbnail_scene.cycles.samples = 32

        with contextlib.suppress(AttributeError):
            hg_thumbnail_scene.cycles.use_denoising = True

        new_coll = hg_thumbnail_scene.collection
        new_coll.objects.link(hg_rig)
        for child in hg_rig.children:
            new_coll.objects.link(child)

        hg_thumbnail_scene.render.resolution_y = resolution
        hg_thumbnail_scene.render.resolution_x = resolution

        self.make_camera_look_at_human(camera_object, type_sett["look_at_correction"])
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

        if white_material:
            old_material = self.objects.body.data.materials[0]
            self.objects.body.data.materials[0] = None
            old_eye_material = self.objects.eyes.data.materials[1]
            self.objects.eyes.data.materials[1] = None

        if not os.path.isdir(folder):
            os.makedirs(folder)

        hg_thumbnail_scene.render.image_settings.file_format = "JPEG"
        full_image_path = os.path.join(folder, f"{name}.jpg")
        hg_thumbnail_scene.render.filepath = full_image_path

        bpy.ops.render.render(write_still=True)

        for light in lights:
            hg_delete(light)

        hg_delete(camera_object)

        if white_material:
            self.objects.body.data.materials[0] = old_material
            self.objects.eyes.data.materials[1] = old_eye_material

        context.window.scene = old_scene

        bpy.data.scenes.remove(hg_thumbnail_scene)

        img = bpy.data.images.load(full_image_path)
        context.scene.HG3D.custom_content.preset_thumbnail = img
        img.preview_ensure()
        return cast(str, img.name)

    def _set_random_name(self) -> None:
        """Randomizes name of human. Will add "HG_" prefix."""
        taken_names = []
        for obj in bpy.data.objects:
            if not obj.HG.ishuman:
                continue
            taken_names.append(obj.name[4:])

        name_json_path = os.path.join(get_addon_root(), "human", "names.json")
        with open(name_json_path, "r") as f:
            names = json.load(f)[self.gender]

        name = random.choice(names)

        # get new name if it's already taken
        i = 0
        while name in taken_names and i < 10:
            name = random.choice(names)
            i += 1

        self.name = "HG_" + name

    def _verify_body_object(self) -> None:
        """Update HG.body_obj if it's not a child of the rig.

        This would happen if the user duplicated the human manually
        """
        # TODO clean up this mess
        if self.props.body_obj not in self.objects and not self.props.batch:
            new_body = (
                [obj for obj in self.objects.rig.children if "hg_rig" in obj]
                if self.objects.rig.children
                else None
            )

            if new_body:
                self.props.body_obj = new_body[0]
                if "no_body" in self.objects.rig:  # type:ignore[operator]
                    del self.objects.rig["no_body"]
            else:
                self.objects.rig["no_body"] = 1  # type:ignore[index]
        else:
            if "no_body" in self.objects.rig:  # type:ignore[operator]
                del self.objects.rig["no_body"]

    def _get_settings_dict_by_thumbnail_type(
        self, thumbnail_type: str
    ) -> dict[str, Union[int, float]]:  # noqa
        """Returns a dict with settings of how to configure the camera for this  # noqa
        automatic thumbnail

        Args:
            thumbnail_type (str): key to the dict inside this function

        Returns:
            dict[str, float]:
                str: name of this property
                float: setting for camera property
        """
        type_settings_dict = {
            "foot": {
                "camera_x": -1.5,
                "camera_y": -0.5,
                "focal_length": 240,
                "look_at_correction": 2.1,
            },
            "head_side": {
                "camera_x": -1.0,
                "camera_y": -1.0,
                "focal_length": 135,
                "look_at_correction": 0.14,
            },
            "head_front": {
                "camera_x": 0,
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

    def _verify_integrity(self):
        for mat in [mat for mat in self.materials if mat]:
            verify_no_undefined_nodes_in_mat(mat)

    def __repr__(self) -> str:
        """Return a string representation of this object.

        Returns:
            str: string representation of this object
        """
        return f"Human '{self.name}' [{self.gender.capitalize()}] instance."
