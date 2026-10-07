# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements class for the process system of HumGen3D."""
import uuid
from typing import TYPE_CHECKING, Dict, Iterable, List, Literal, Optional

import bpy
from HumGen3D.backend.logging import hg_log
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.object_finding import (
    HUMAN_ID_KEY,
    ORIGINAL_ID_KEY,
    PROCESSED_KEY,
)
from HumGen3D.common.progress import ProgressCallback, Steps
from HumGen3D.common.progress import run as run_steps
from HumGen3D.common.type_aliases import C

from .lod import LOD_KEY, LOD_RIG_KEY, LodSettings, merge_levels

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from . import animations, naming, textures
from .apply_modifiers import apply_modifiers
from .bake import BakeSettings
from .game_eyes import GAME_EYES_KEY, convert_to_game_eyes
from .game_rig import GAME_RIG_KEY, CUSTOM_PRESET, convert_to_game_rig, preset_for_names
from .masks import remove_hidden_skin
from .pipeline import ExportResult, Preflight
from .rest_pose import T_POSE_KEY, set_t_pose_as_rest
from .settings import (
    AnimationSettings,
    ExportSettings,
    MeshSettings,
    OutputSettings,
    QualitySettings,
    ShapeKeySettings,
    SkeletonSettings,
    TextureSettings,
)
from .shape_keys import (
    KeepSelection,
    KeyAction,
    actions_for_level,
    keep_options,
    process_shape_keys,
)

# Set on the rig once the particle hair was converted to hair cards
HAIRCARDS_KEY = "haircards"


class ProcessSettings:
    """Class for accessing methods and subclasses for processing the human.

    `run` does everything the Process tab does, from an `ExportSettings`:

        settings = ExportSettings.from_recipe("unity")
        settings.output.folder = "/path/to/project/Assets/Characters"
        result = human.process.run(settings)
        print(result.files)

    The other methods are the single steps of `run`, which change this human in
    place, so call them on a `human.duplicate()`. They take the section of the
    settings they are about, or plain arguments. `run` does them in this order,
    which the steps depend on:

        1. `set_shape_keys`, so the other steps only carry the keys that stay
        2. `convert_to_haircards`
        3. `convert_to_game_eyes` and `lod.set_teeth_lod`, before baking, as
           they change the materials
        4. `bake_textures`, before the meshes are reduced
        5. `set_quality` (or `lod.set_body_lod` and `lod.set_clothing_lod`)
        6. `remove_hidden_skin`
        7. `set_t_pose_as_rest` and `convert_to_game_rig`
        8. `apply_names`
        9. `prepare_clips`, once the skeleton is final
        10. `human.export.write`, or `mark_as_processed` to keep it in the file

    The steps that change the human for good refuse to run twice, see the
    `has_*` and `was_*` properties.
    """

    def __init__(self, human: "Human") -> None:
        self._human = human

    @property
    def baking(self) -> BakeSettings:
        """The baking API of earlier versions, see `bake_textures`."""
        return BakeSettings(self._human)

    @property
    def lod(self) -> LodSettings:
        """Gives access to the LOD settings.

        Returns:
            LodSettings: The LOD settings.
        """
        return LodSettings(self._human)

    # Running the whole pipeline

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

    # Shape keys

    @injected_context
    def set_shape_keys(
        self,
        settings: Optional[ShapeKeySettings] = None,
        level: int = 0,
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
            settings (Optional[ShapeKeySettings]): The actions as a recipe holds
                them. The other arguments are ignored when given.
            level (int): The LOD level this human is, with `settings` only. With
                `ShapeKeySettings.lod0_only` the lower levels keep no keys.
            face_rig (KeyAction): "keep" loads the FACS face rig if the human has
                none yet, "remove" removes it. Baking is not possible.
            expressions (KeyAction): The 1-click expressions.
            correctives (KeyAction): Keys driven by bones that fix the joints and
                the eyelids, also on the clothing.
            body (KeyAction): The body proportion sliders, including the muscles.
            face (KeyAction): The face proportion sliders, face presets and eyes.
            age (KeyAction): The age sliders.
            keep (Optional[KeepSelection]): Per group the names of the keys to
                keep, see `shape_key_options`. Missing groups keep all.
            context (C): Blender context. bpy.context if not provided.

        Raises:
            ValueError: If an action is not possible for a group.
        """
        if settings is not None:
            keys = actions_for_level(settings, level)
            face_rig, expressions, correctives = keys.face_rig, keys.expressions, keys.correctives
            body, face, age, keep = keys.body, keys.face, keys.age, keys.keep
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
    def shape_key_options(self, context: C = None) -> Dict[str, List[str]]:
        """The keys `set_shape_keys` can keep, per group, by display name.

        The face rig and the expressions list everything in the library, the
        other groups what this human has. Use a subset as the `keep` argument
        or `ShapeKeySettings.keep`.

        Args:
            context (C): Blender context. bpy.context if not provided.
        """
        return keep_options(self._human, context)

    # Hair

    @property
    def has_haircards(self) -> bool:
        """Checks if haircards are present.

        Returns:
            bool: True if haircards are present.
        """
        return bool(self._human.objects.haircards)

    @injected_context
    def convert_to_haircards(
        self,
        quality: Literal["ultra", "high", "medium", "low", "haircap_only"] = "high",
        context: C = None,
    ) -> List[bpy.types.Object]:
        """Replaces every particle hair system of this human by hair cards.

        The hair, eyebrows, eyelashes and facial hair each become a mesh object
        with a haircap and cards, skinned to the rig, see
        `human.hair.regular_hair.convert_to_haircards` for one of them. The
        particle systems are removed afterwards, as no file format carries them.

        Args:
            quality (Literal["ultra", "high", "medium", "low", "haircap_only"]):
                Triangle budget of the cards, see `QualitySettings.haircards`.
            context (C): Blender context. bpy.context if not provided.

        Returns:
            List[bpy.types.Object]: The hair card objects that were made.

        Raises:
            HumGenException: If the human has hair cards already.
        """
        if self.has_haircards:
            raise HumGenException("Human already has hair cards.")
        hair = self._human.hair
        made = []
        for hair_type in (hair.regular_hair, hair.eyebrows, hair.eyelashes, hair.face_hair):
            if hair_type.modifiers:
                made.append(hair_type.convert_to_haircards(quality, context))
        body = self._human.objects.body
        for mod in list(hair.modifiers):
            body.modifiers.remove(mod)
        self._human.objects.rig[HAIRCARDS_KEY] = True
        return made

    # Textures

    @property
    def was_baked(self) -> bool:
        """Checks if materials were baked.

        Returns:
            bool: True if materials were baked.
        """
        return textures.BAKED_KEY in self._human.objects.rig

    @injected_context
    def bake_textures(
        self,
        settings: Optional[TextureSettings] = None,
        folder: Optional[str] = None,
        output: Optional[OutputSettings] = None,
        level: int = 0,
        levels: int = 1,
        only_sets: Optional[Iterable[str]] = None,
        context: C = None,
    ) -> List[bpy.types.Image]:
        """Bakes every material of this human to textures and replaces it.

        The skin, hair and eye materials are node trees exporters can't read,
        so every material becomes a Principled BSDF with image nodes, with the
        maps packed and flipped as the settings ask. The materials are copied
        first, so a human this one was duplicated from keeps its own.

        Args:
            settings (Optional[TextureSettings]): Passes, resolution, packing,
                normal map direction and samples. Separate maps at 2k by default.
            folder (Optional[str]): Folder to write the images to, None packs
                them in the blend file.
            output (Optional[OutputSettings]): Naming scheme and name of the
                images and materials, see `apply_names`. The plain scheme with
                the name of the human by default.
            level (int): LOD level of this human, for the names.
            levels (int): Number of LOD levels, for the names.
            only_sets (Optional[Iterable[str]]): Bake only these texture sets
                of `TEXTURE_SETS`, for a level that shares the others, see
                `share_textures`.
            context (C): Blender context. bpy.context if not provided.

        Returns:
            List[bpy.types.Image]: The images of the new materials.

        Raises:
            HumGenException: If the materials were baked already.
        """
        if self.was_baked:
            raise HumGenException("Human was already baked.")
        settings = settings or TextureSettings()
        only = tuple(only_sets) if only_sets is not None else None
        # Only the materials that get baked, the others may be shared with
        # another level on purpose, see share_textures
        planned = textures.plan_texture_sets(self._human, settings)
        textures.copy_materials(
            self._human,
            [
                obj
                for texture_set in planned
                if only is None or texture_set.set_name in only
                for obj in texture_set.objects
            ],
        )
        namer = self._namer(output, level, levels)
        return run_steps(
            textures.bake_steps(
                self._human, settings, namer, folder, context, only, per_level=level > 0
            )
        )

    def share_textures(self, source: "Human") -> None:
        """Gives this human the baked materials of another, per part.

        LOD levels share their textures: the meshes keep their UV layout when
        they are reduced, so the images baked for the first level fit every
        level. The hair cards and the eyes are left alone, their UVs differ per
        quality, bake those with `bake_textures(only_sets=("eyes", "hair"))`.

        Args:
            source (Human): Human with baked materials.
        """
        textures.share_textures(source, self._human)

    # Meshes

    @property
    def is_lod(self) -> bool:
        """Checks if the body of the human has a lower level of detail.

        Returns:
            bool: True if the human is an LOD.
        """
        return LOD_RIG_KEY in self._human.objects.rig

    @property
    def has_game_eyes(self) -> bool:
        """Checks if the eyes were converted to single layer eyes.

        Returns:
            bool: True if the human has game eyes.
        """
        return GAME_EYES_KEY in self._human.objects.rig

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

    @injected_context
    def set_quality(
        self,
        quality: QualitySettings,
        meshes: Optional[MeshSettings] = None,
        context: C = None,
    ) -> None:
        """Reduces the meshes of this human to the detail of a LOD level.

        Converts the eyes, decimates the teeth and the clothing and dissolves
        edges of the body, as `QualitySettings` asks. Hair cards and bones per
        vertex are not part of it, see `convert_to_haircards` and
        `convert_to_game_rig`. Meshes that have their detail already are skipped.

        Args:
            quality (QualitySettings): Detail per mesh, see `QualitySettings.from_tier`.
            meshes (Optional[MeshSettings]): Which modifiers of the clothing to
                remove and whether to remove the skin under it. Defaults apply.
            context (C): Blender context. bpy.context if not provided.
        """
        meshes = meshes or MeshSettings()
        if quality.eyes != "original" and not self.has_game_eyes:
            self.convert_to_game_eyes(quality.eyes)
        if quality.teeth and not any(
            LOD_KEY in obj for obj in (self._human.objects.upper_teeth, self._human.objects.lower_teeth)
        ):
            self.lod.set_teeth_lod(quality.teeth, context=context)
        if quality.body and not self._human.is_trial:
            self.lod.set_body_lod(quality.body, context=context)
        self.lod.set_clothing_lod(
            quality.clothing,
            meshes.remove_clothing_subdiv,
            meshes.remove_clothing_solidify,
            keep_shape_keys=True,
            context=context,
        )
        if meshes.remove_hidden_skin:
            self.remove_hidden_skin(context)

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

    @injected_context
    def apply_modifiers(
        self,
        modifier_types: Iterable[str],
        objects: Optional[Iterable[bpy.types.Object]] = None,
        apply_hidden: bool = False,
        context: C = None,
    ) -> None:
        """Applies modifiers to the meshes of this human, keeping the shape keys.

        Blender refuses to apply a modifier to a mesh with shape keys, this
        applies it to every key. For scripts and anything the other steps don't
        cover; particle systems and decimate modifiers are never applied.

        Args:
            modifier_types (Iterable[str]): Types to apply, like "SUBSURF" or
                "SOLIDIFY".
            objects (Optional[Iterable[bpy.types.Object]]): Meshes to apply to,
                every mesh of the human when None.
            apply_hidden (bool): Also apply modifiers hidden in the viewport.
            context (C): Blender context. bpy.context if not provided.
        """
        apply_modifiers(self._human, modifier_types, objects, apply_hidden, context=context)

    # Skeleton

    @property
    def has_t_pose_rest(self) -> bool:
        """Checks if the T-pose was baked into the rest pose.

        Returns:
            bool: True if the rest pose is the T-pose.
        """
        return T_POSE_KEY in self._human.objects.rig

    @injected_context
    def set_t_pose_as_rest(self, context: C = None) -> None:
        """Bakes the T-pose into the rest pose of the meshes and armature.

        Discards the current pose and removes the shoulder side raise corrective
        shape keys. Features that rely on the A-pose rest pose, like changing the
        pose, height, proportions or clothing, won't work on this human anymore.

        Args:
            context (C): The Blender context. Defaults to None.

        Raises:
            HumGenException: If the rest pose is the T-pose already, or the
                human is a Rigify or legacy human.
        """
        set_t_pose_as_rest(self._human, context)

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
        settings: Optional[SkeletonSettings] = None,
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
        T-pose, which happens by itself when `settings` ask for it.

        Args:
            preset (str): Engine to name the bones for: "generic_a" and
                "generic_t" keep the Human Generator names ("humgen" picks one
                by the rest pose), "humanoid" uses the names of Unity, Godot and
                VRM, "unreal" the Mannequin names, "mixamo" the Mixamo names
                and "custom" the names of names_file. The rest pose of the
                preset is not applied here, see set_t_pose_as_rest.
            keep_eyes (bool): Keep the eye bones, otherwise the eyes follow the head.
            keep_jaw (bool): Keep the jaw bones that move the teeth.
            keep_breasts (bool): Keep the breast bones.
            keep_metacarpals (bool): Keep the palm bones between hand and fingers.
            max_influences (int): Maximum number of bones per vertex, 0 for no
                limit. Also with `settings`, as `QualitySettings.bones_per_vertex`
                holds it per LOD level.
            root_bone (Optional[bool]): Add a root bone at the origin, None uses the
                choice of the preset. Mixamo has none, the others do.
            root_bone_name (Optional[str]): Name of the root bone, None uses the
                name of the preset.
            names_file (Optional[str]): JSON file with "names" and "sides" like
                game_rig_presets.json, for the "custom" preset.
            settings (Optional[SkeletonSettings]): The skeleton as a recipe holds
                it, replaces the arguments above except max_influences. Its rest
                pose is applied first when it is the T-pose.
            context (C): Blender context. bpy.context if not provided.

        Raises:
            HumGenException: If the human has a game rig already, or is a Rigify
                or legacy human.
            ValueError: If the preset does not exist.
        """
        if settings is not None:
            if settings.rest_pose == "t_pose" and not self.has_t_pose_rest:
                self.set_t_pose_as_rest(context)
            preset = preset_for_names(settings.names, settings.rest_pose)
            keep_eyes, keep_jaw = settings.keep_eyes, settings.keep_jaw
            keep_breasts, keep_metacarpals = settings.keep_breasts, settings.keep_metacarpals
            root_bone, root_bone_name = settings.root_bone, settings.root_bone_name
            names_file = settings.names_file if settings.names == CUSTOM_PRESET else None
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

    # Naming, animation and results

    def apply_names(
        self,
        output: Optional[OutputSettings] = None,
        level: int = 0,
        levels: int = 1,
    ) -> None:
        """Names the objects, meshes, materials and images by a naming scheme.

        A copy of a human has names like "HG_Body.001", which engines show.
        This names every datablock after the human and its part instead:
        "Jake_Body", "Jake_Skin" and "Jake_Body_BaseColor", or with the Unreal
        scheme "SK_Jake_Body", "M_Jake_Skin" and "T_Jake_Body_BC". Unused
        material slots are removed. Materials shared with another human, like
        the one this is a duplicate of, are copied first.

        Args:
            output (Optional[OutputSettings]): Scheme, templates and the name,
                `OutputSettings.name` with "{name}" for the name of the human.
                The plain scheme with the name of the human by default.
            level (int): LOD level of this human, added as "_LOD1" suffix to
                the meshes when there is more than one level.
            levels (int): Number of LOD levels.
        """
        textures.copy_materials(self._human)
        naming.apply_names(self._human, self._namer(output, level, levels))

    def _namer(self, output: Optional[OutputSettings], level: int, levels: int) -> naming.Namer:
        output = output or OutputSettings()
        # A duplicate is called "Jake.001", the tokens go around the clean name
        name = output.resolved_name(naming.clean(self._human.name))
        return naming.Namer(output, name, level, levels)

    @injected_context
    def prepare_clips(
        self,
        settings: Optional[AnimationSettings] = None,
        source: Optional["Human"] = None,
        context: C = None,
    ) -> List[bpy.types.Action]:
        """Gives this human its own animation clips, fitted to its skeleton.

        After `convert_to_game_rig` the actions of the source human no longer
        fit: bones are gone or renamed and the rest pose may be the T-pose. The
        Human Generator animations are retargeted onto the converted skeleton,
        other actions are copied as they are with a warning in the log. The
        clips end up as one NLA strip each, so `human.export.write(...,
        animation="strips")` writes every clip as a take. Afterwards the clips
        are the only animation on this human.

        Args:
            settings (Optional[AnimationSettings]): Which clips, from the human
                or the library, and the root motion. Every clip on the source
                human by default.
            source (Optional[Human]): The human the clips come from, this human
                by default. Pass the original when this is its duplicate.
            context (C): Blender context. bpy.context if not provided.

        Returns:
            List[bpy.types.Action]: The clips of this human.
        """
        settings = settings or AnimationSettings(enabled=True)
        clips, warnings = animations.prepare_clips(
            self._human, source or self._human, settings, context
        )
        for warning in warnings:
            hg_log(warning, level="WARNING")
        return clips

    def merge_levels(self, levels: List["Human"]) -> None:
        """Puts the meshes of other LOD levels under the skeleton of this human.

        For one file with every level. The skeletons have to be identical,
        which they are when the levels were made from the same source with the
        same skeleton settings. The rigs of the other levels are removed, so
        they are no humans afterwards.

        Args:
            levels (List[Human]): The other levels, in order of detail.
        """
        merge_levels([self._human] + list(levels))

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
