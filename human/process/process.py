# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements class for the process system of HumGen3D."""
import uuid
from typing import TYPE_CHECKING, Literal, Optional

from HumGen3D.common.decorators import injected_context
from HumGen3D.common.object_finding import (
    HUMAN_ID_KEY,
    ORIGINAL_ID_KEY,
    PROCESSED_KEY,
)
from HumGen3D.common.progress import ProgressCallback, Steps
from HumGen3D.common.type_aliases import C

from .lod import LodSettings

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from .bake import BakeSettings
from .game_eyes import convert_to_game_eyes
from .game_rig import GAME_RIG_KEY, convert_to_game_rig
from .masks import remove_hidden_skin
from .pipeline import ExportResult, Preflight
from .rest_pose import set_t_pose_as_rest
from .settings import ExportSettings
from .shape_keys import KeepSelection, KeyAction, process_shape_keys


class ProcessSettings:
    """Class for accessing methods and subclasses for processing the human.

    `run` does everything the Process tab does, from an `ExportSettings`:

        settings = ExportSettings.from_recipe("unity")
        settings.output.folder = "/path/to/project/Assets/Characters"
        result = human.process.run(settings)
        print(result.files)

    The other methods are the single steps, which change this human in place.
    """

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

    @injected_context
    def preflight(self, settings: ExportSettings, context: C = None) -> Preflight:
        """Checks what `run` with these settings would complain about.

        Args:
            settings (ExportSettings): The settings to check.
            context (C): Blender context. bpy.context if not provided.

        Returns:
            Preflight: Errors that stop the run and warnings that don't.
        """
        from .pipeline import preflight

        return preflight(self._human, settings, context)

    @injected_context
    def run(
        self,
        settings: ExportSettings,
        context: C = None,
        progress: Optional[ProgressCallback] = None,
    ) -> ExportResult:
        """Processes this human by the settings, as the Process tab does.

        This human is not changed. Every LOD level of the settings becomes a
        processed duplicate, which is added to the file or written to the files
        of the output format and removed again.

        Args:
            settings (ExportSettings): What to make, see `ExportSettings.from_recipe`.
            context (C): Blender context. bpy.context if not provided.
            progress (Optional[ProgressCallback]): Called with the fraction done.

        Returns:
            ExportResult: The humans added to the file or the files written,
                with warnings and triangle counts.

        Raises:
            HumGenException: If the preflight finds an error or a step fails.
        """
        from .pipeline import run

        return run(self._human, settings, context, progress)

    @injected_context
    def run_steps(self, settings: ExportSettings, context: C = None) -> Steps[ExportResult]:
        """The work of `run` as resumable steps, see `HumGen3D.common.progress`."""
        from .pipeline import process_steps

        return process_steps(self._human, settings, context)

    @property
    def settings(self) -> Optional[ExportSettings]:
        """The settings a processed human was made with, None for other humans."""
        from .pipeline import settings_of

        return settings_of(self._human)

    @property
    def has_haircards(self) -> bool:
        """Checks if haircards are present.

        Returns:
            bool: True if haircards are present.
        """
        return bool(self._human.objects.haircards)

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
    def has_t_pose_rest(self) -> bool:
        """Checks if the T-pose was baked into the rest pose.

        Returns:
            bool: True if the rest pose is the T-pose.
        """
        return "t_pose_rest" in self._human.objects.rig

    @injected_context
    def set_t_pose_as_rest(self, context: C = None) -> None:
        """Bakes the T-pose into the rest pose of the meshes and armature.

        Discards the current pose and removes the shoulder side raise corrective
        shape keys. Features that rely on the A-pose rest pose, like changing the
        pose, height, proportions or clothing, won't work on this human anymore.

        Args:
            context (C): The Blender context. Defaults to None.
        """
        set_t_pose_as_rest(self._human, context)

    @property
    def has_game_eyes(self) -> bool:
        """Checks if the eyes were converted to single layer eyes.

        Returns:
            bool: True if the human has game eyes.
        """
        return "game_eyes" in self._human.objects.rig

    def convert_to_game_eyes(
        self, detail: Literal["high", "medium", "low"] = "medium"
    ) -> None:
        """Replaces the layered eyes by single layer eyes for game engines.

        Only the front of the cornea is kept, with the eye color as opaque
        material on it. Applies the shape keys of the eyes, so changing the height
        or proportions won't work on this human anymore.

        Args:
            detail (Literal["high", "medium", "low"]): Resolution of the eye mesh.
                Medium has a quarter of the triangles of high, low about a sixteenth.
        """
        convert_to_game_eyes(self._human, detail)

    @property
    def has_game_rig(self) -> bool:
        """Checks if the rig was converted to a game engine skeleton.

        Returns:
            bool: True if the human has a game rig.
        """
        return GAME_RIG_KEY in self._human.objects.rig

    @property
    def game_rig_preset(self) -> Optional[str]:
        """The preset the rig was converted with, None if it has no game rig.

        Returns:
            Optional[str]: Identifier of the preset, see game_rig.PRESETS, or the
                path of the names file of a custom preset.
        """
        return self._human.objects.rig.get(GAME_RIG_KEY)

    @injected_context
    def convert_to_game_rig(
        self,
        preset: str = "generic_a",
        keep_eyes: bool = True,
        keep_jaw: bool = True,
        keep_breasts: bool = True,
        keep_metacarpals: bool = False,
        max_influences: int = 4,
        root_bone: Optional[bool] = None,
        root_bone_name: Optional[str] = None,
        names_file: Optional[str] = None,
        context: C = None,
    ) -> None:
        """Converts the rig to a skeleton for game engines.

        Removes the bones that deform nothing, like the face rig controls and the
        eye targets, and bakes the shape keys they drove at their current value.
        Merges the weights of the bones that are not kept into their parents, adds
        a root bone at the origin, bakes the constraints into the pose, removes the
        vertex groups that are neither bones nor used by a modifier, limits the
        number of bones per vertex and renames the bones for the preset. The face
        rig, poses and animations of Human Generator won't work on this human
        anymore. Combine with set_t_pose_as_rest for the presets that expect a
        T-pose, the process system does this automatically.

        Args:
            preset (str): Engine to name the bones for: "generic_a" and
                "generic_t" keep the Human Generator names, "humanoid" uses the
                names of Unity, Godot and VRM, "unreal" the Mannequin names,
                "mixamo" the Mixamo names and "custom" the names of names_file.
                The rest pose of the preset is not applied here, see
                set_t_pose_as_rest.
            keep_eyes (bool): Keep the eye bones, otherwise the eyes follow the head.
            keep_jaw (bool): Keep the jaw bones that move the teeth.
            keep_breasts (bool): Keep the breast bones.
            keep_metacarpals (bool): Keep the palm bones between hand and fingers.
            max_influences (int): Maximum number of bones per vertex, 0 for no limit.
            root_bone (Optional[bool]): Add a root bone at the origin, None uses the
                choice of the preset. Mixamo has none, the others do.
            root_bone_name (Optional[str]): Name of the root bone, None uses the
                name of the preset.
            names_file (Optional[str]): JSON file with "names" and "sides" like
                game_rig_presets.json, for the "custom" preset.
            context (C): Blender context. bpy.context if not provided.
        """
        convert_to_game_rig(
            self._human,
            context,
            preset=preset,
            keep_eyes=keep_eyes,
            keep_jaw=keep_jaw,
            keep_breasts=keep_breasts,
            keep_metacarpals=keep_metacarpals,
            max_influences=max_influences,
            root_bone=root_bone,
            root_bone_name=root_bone_name,
            names_file=names_file,
        )

    @injected_context
    def set_shape_keys(
        self,
        face_rig: KeyAction = "keep",
        expressions: KeyAction = "keep",
        correctives: KeyAction = "keep",
        body: KeyAction = "bake",
        face: KeyAction = "bake",
        age: KeyAction = "bake",
        keep: Optional[KeepSelection] = None,
        context: C = None,
    ) -> None:
        """Decides which shape keys stay on the human, per group of keys.

        Each group is kept as shape keys, baked into the mesh at its current value
        or removed. Keeping livekeys converts them to shape keys, so for example
        the body sliders can be exported as blend shapes. The livekeys and the
        gender key are always baked afterwards, as is the fit of the clothing.
        Kept keys that bones drive, the face rig and the correctives, need their
        drivers reconnected after exporting.

        Args:
            face_rig (KeyAction): "keep" loads the FACS face rig if the human has
                none yet, "remove" removes it. Baking is not possible.
            expressions (KeyAction): The 1-click expressions.
            correctives (KeyAction): Keys driven by bones that fix the joints and
                the eyelids, also on the clothing.
            body (KeyAction): The body proportion sliders, including the muscles.
            face (KeyAction): The face proportion sliders, face presets and eyes.
            age (KeyAction): The age sliders.
            keep (Optional[KeepSelection]): Per group the names of the keys to
                keep, see shape_keys.keep_options. Missing groups keep all.
            context (C): Blender context. bpy.context if not provided.
        """
        process_shape_keys(
            self._human,
            face_rig=face_rig,
            expressions=expressions,
            correctives=correctives,
            body=body,
            face=face,
            age=age,
            keep=keep,
            context=context,
        )

    @injected_context
    def remove_hidden_skin(self, context: C = None) -> int:
        """Deletes the vertices of the body that the clothing hides.

        Applies the mask modifiers of the clothing to the body mesh itself,
        with the shape keys carried along. Exporters skip modifiers, so
        without this the body is complete under every garment.

        Args:
            context (C): Blender context. bpy.context if not provided.

        Returns:
            int: Number of vertices removed.
        """
        return remove_hidden_skin(self._human, context)

    @property
    def is_processed(self) -> bool:
        """Checks if this human is a frozen result of the process system.

        Returns:
            bool: True if the human is a processed human.
        """
        return PROCESSED_KEY in self._human.objects.rig

    def mark_as_processed(self, original_human: "Human") -> None:
        """Marks this human as the frozen, processed result of another human.

        The Human Generator interface doesn't allow editing processed humans, it
        refers to the original human instead.

        Args:
            original_human (Human): The editable human this human was made from.
        """
        original_rig = original_human.objects.rig
        if HUMAN_ID_KEY not in original_rig:
            original_rig[HUMAN_ID_KEY] = uuid.uuid4().hex

        rig = self._human.objects.rig
        rig[ORIGINAL_ID_KEY] = original_rig[HUMAN_ID_KEY]
        rig[PROCESSED_KEY] = True
        # Copied along when this human was duplicated from the original
        if HUMAN_ID_KEY in rig:
            del rig[HUMAN_ID_KEY]
