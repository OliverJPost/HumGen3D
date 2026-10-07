# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Runs the process system: settings in, processed humans or files out.

The source human is never changed. Every LOD level is a fresh duplicate of the
source, processed on its own with the quality of that level, so a level is a
pure function of the source and its settings. Levels share the textures baked
for the first level, except the hair cards and the eyes, whose UVs differ per
quality. For a file export the levels are joined under one skeleton and written
together.

The work is a generator of progress fractions, see `HumGen3D.common.progress`,
so the modal operator can show a progress bar and `run` can do it in one go.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Iterator, List, Optional, Tuple

import bpy
from HumGen3D.backend.logging import hg_log
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.common import is_legacy
from HumGen3D.common.collections import add_to_collection
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.object_finding import PROCESSED_KEY
from HumGen3D.common.progress import ProgressCallback, Steps
from HumGen3D.common.progress import run as run_steps
from HumGen3D.human.process.lod import CLOTHING_DECIMATE_RATIOS
from mathutils import Vector

from . import animations, masks, naming, scripts, textures
from .game_rig import CUSTOM_PRESET, preset_for_names
from .settings import EXPORT_STAGES, ExportSettings, QualitySettings, ShapeKeySettings
from .shape_keys import driven_groups_kept

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

EXPORT_KEY = "hg_export"
LEVEL_KEY = "hg_export_level"
RESULTS_COLLECTION = "Processing Results"
DEFAULT_EXPORT_FOLDER = "export_results"
TEXTURES_FOLDER = "Textures"
# Texture sets that every LOD level bakes itself, see textures.share_textures
PER_LEVEL_SETS = ("eyes", "hair")
# Distance between the in-file results, along Y
RESULT_SPACING = 2.0


@dataclass
class Preflight:
    """What would go wrong before anything is changed."""

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class ExportResult:
    """What the process system made."""

    settings: ExportSettings
    name: str
    humans: List["Human"] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # Triangles per LOD level, hair included
    triangles: List[int] = field(default_factory=list)
    seconds: float = 0.0

    def summary(self) -> str:
        """A few lines for the report after processing."""
        lines = []
        if self.files:
            lines.append(f"Written {len(self.files)} file(s) to {os.path.dirname(self.files[0])}")
        if self.humans:
            lines.append(f"{len(self.humans)} processed human(s) added to this file")
        for level, tris in enumerate(self.triangles):
            label = f"LOD{level}: " if len(self.triangles) > 1 else ""
            lines.append(f"{label}~{tris:,} triangles")
        lines.extend(f"Warning: {warning}" for warning in self.warnings)
        return "\n".join(lines)


def output_folder(settings: ExportSettings) -> str:
    """The folder the files go to, the export folder of the content folder when
    the settings leave it empty."""
    folder = settings.output.folder
    if folder.startswith("//"):
        folder = bpy.path.abspath(folder)
    if not folder:
        folder = os.path.join(get_prefs().filepath, DEFAULT_EXPORT_FOLDER)
    return os.path.abspath(folder)


def preflight(  # noqa: CCR001
    human: "Human", settings: ExportSettings, context: bpy.types.Context
) -> Preflight:
    """Checks the human and the settings without changing anything.

    Errors stop the process, warnings are shown and carried into the result.
    """
    result = Preflight()
    output = settings.output
    rig = human.objects.rig

    if PROCESSED_KEY in rig:
        result.errors.append("This is a processed human, process its original instead")
    if is_legacy(rig):
        result.errors.append("Humans made before version 4 can't be processed")
    if not settings.lods:
        result.errors.append("The settings have no LOD level")
    if output.is_file:
        folder = output_folder(settings)
        # The folder is made when the files are written, here only its closest
        # existing parent is checked, so drawing the interface changes nothing
        parent = folder
        while parent and not os.path.isdir(parent):
            parent = os.path.dirname(parent)
        if not parent or not os.access(parent, os.W_OK):
            result.errors.append(f"Can't write to {folder}")
    if settings.skeleton.enabled and settings.skeleton.names == "custom":
        if not os.path.isfile(settings.skeleton.names_file):
            result.errors.append("The bone names file of the skeleton does not exist")
    for script in settings.scripts.active():
        if not os.path.isfile(script.path):
            result.errors.append(f"Script not found: {script.path}")
        elif script.stage in EXPORT_STAGES and not output.is_file:
            result.warnings.append(
                f"{os.path.basename(script.path)} runs at the export, which"
                " the in-file output has not"
            )

    is_rigify = human.pose.rigify.is_rigify
    if is_rigify and settings.skeleton.enabled:
        result.warnings.append(
            "Rigify human: the skeleton can't be converted, the Rigify rig is"
            " exported as it is"
        )
    has_particle_hair = bool(human.hair.modifiers)
    if has_particle_hair and not settings.haircards.enabled and output.is_file:
        result.warnings.append(
            "The hair is particle hair, which no file format carries. Enable"
            " Haircards or the character is bald"
        )
    if output.is_file and not settings.textures.enabled:
        result.warnings.append("Files need baked textures, Textures is turned on")
    if settings.textures.file_format == "jpeg" and settings.haircards.enabled:
        result.warnings.append("JPEG has no alpha channel, the hair cards lose their transparency")
    if output.is_file and not settings.meshes.enabled:
        result.warnings.append(
            "The eyes are not game ready: the layered eyes with a transparent"
            " cornea only render in Blender. Turn on Optimize Meshes to get game eyes"
        )
    elif output.is_file and settings.lods[0].eyes == "original":
        result.warnings.append(
            "The layered eyes with a transparent cornea only render in Blender,"
            " pick game eyes in Optimize Meshes"
        )
    if len(settings.lods) > 1 and not settings.meshes.enabled:
        result.warnings.append(
            "Optimize Meshes is off, so every LOD level has the original meshes"
        )
    if not output.has_rig and output.is_file:
        result.warnings.append(f"{output.format.upper()} carries no skeleton or animation")
    kept = driven_groups_kept(
        (group, getattr(settings.shape_keys, group))
        for group in ("face_rig", "correctives")
    ) if settings.shape_keys.enabled else []
    if kept and output.is_file:
        result.warnings.append(
            f"{' and '.join(kept)} keys are driven by bones in Blender, reconnect"
            " them in the other program"
        )
    if settings.animations.enabled and output.is_file and not output.has_rig:
        result.warnings.append("Animations need a format with a skeleton, none are exported")
    if settings.animations.enabled:
        # The library is not listed here, that refreshes a preview collection,
        # which is not allowed while the interface draws this
        if settings.animations.source == "library":
            no_clips = settings.animations.clips == []
        else:
            no_clips = not animations.source_clips(human, settings.animations)
        if no_clips:
            result.warnings.append("Animations is on, but no clip is selected")
    if human.is_trial and any(level.body for level in settings.lods):
        result.warnings.append("The body can't be reduced in the trial version")
    return result


def run(
    human: "Human",
    settings: ExportSettings,
    context: bpy.types.Context,
    progress: Optional[ProgressCallback] = None,
) -> ExportResult:
    """Processes a human in one go, see `process_steps`."""
    return run_steps(process_steps(human, settings, context), progress)


class _Tracker:
    """Turns the weights of the steps into one fraction from 0 to 1."""

    def __init__(self, total: float) -> None:
        self.total = max(total, 1e-6)
        self.done = 0.0

    def tick(self, weight: float) -> float:
        self.done += weight
        return min(self.done / self.total, 1.0)

    def phase(self, steps: Steps, weight: float) -> Iterator[float]:  # type:ignore[type-arg]
        start = self.done
        while True:
            try:
                fraction = next(steps)
            except StopIteration as finished:
                self.done = start + weight
                return finished.value
            yield min((start + weight * min(max(fraction, 0.0), 1.0)) / self.total, 1.0)


def _weights(human: "Human", settings: ExportSettings) -> Dict[str, float]:
    """Rough cost of each step, baking dominates."""
    hair_types = sum(
        1
        for hair in (human.hair.regular_hair, human.hair.eyebrows, human.hair.eyelashes, human.hair.face_hair)
        if hair.modifiers
    )
    clothing = len(human.clothing.outfit.objects) + len(human.clothing.footwear.objects)
    passes = sum(len(p) for p in settings.textures.passes.values())
    return {
        "duplicate": 1.0,
        "shape_keys": 2.0,
        "haircards": 4.0 * hair_types if settings.haircards.enabled else 0.0,
        "eyes_teeth": 1.0,
        "textures": 2.5 * (3 + clothing + hair_types) * max(passes / 5, 1),
        "textures_level": 2.5 * (1 + hair_types),
        "lod": 1.0 + clothing,
        "masks": 1.0,
        "skeleton": 3.0,
        "naming": 0.3,
        "animations": 2.0,
        "write": 4.0,
    }


def process_steps(  # noqa: CCR001
    human: "Human", settings: ExportSettings, context: bpy.types.Context
) -> Steps[ExportResult]:
    """Processes a human by the settings, yielding the fraction that is done.

    Args:
        human (Human): The source human, it is not changed.
        settings (ExportSettings): What to make.
        context (bpy.types.Context): Blender context.

    Returns:
        ExportResult: The humans added to the file or the files written.

    Raises:
        HumGenException: If the preflight finds an error, or a step fails. The
            copies made so far are removed.
    """
    started = time.monotonic()
    settings = _effective_settings(settings)
    check = preflight(human, settings, context)
    if not check.ok:
        raise HumGenException("\n".join(check.errors))

    name = settings.resolved_name(human.name)
    levels = len(settings.lods)
    output = settings.output
    folder = output_folder(settings) if output.is_file else None
    if folder:
        os.makedirs(folder, exist_ok=True)
    texture_folder, scratch_folder = _texture_folder(settings, folder)
    result = ExportResult(settings=settings, name=name, warnings=list(check.warnings))

    weights = _weights(human, settings)
    per_level = sum(
        weights[key] for key in ("duplicate", "shape_keys", "haircards", "eyes_teeth", "lod", "masks", "skeleton", "naming")
    )
    textures_on = settings.textures.enabled
    total = per_level * levels
    if textures_on:
        total += weights["textures"] + weights["textures_level"] * (levels - 1)
    if settings.animations.enabled and output.has_rig:
        total += weights["animations"]
    if output.is_file:
        total += weights["write"]
    tracker = _Tracker(total)

    copies: List["Human"] = []
    images: List[bpy.types.Image] = []
    try:
        for level, quality in enumerate(settings.lods):
            namer = naming.Namer(output, name, level, levels)
            copy = yield from tracker.phase(
                _level_steps(
                    human, settings, quality, level, namer, texture_folder, copies, images, context, weights, result
                ),
                per_level + (0 if not textures_on else (weights["textures"] if level == 0 else weights["textures_level"])),
            )
            copies.append(copy)

        if settings.animations.enabled and output.has_rig and copies:
            clips, warnings = animations.prepare_clips(copies[0], human, settings.animations, context)
            result.warnings.extend(warnings)
            yield tracker.tick(weights["animations"])
        else:
            clips = []

        if output.is_file:
            assert folder is not None
            if len(copies) > 1:
                _merge_levels(copies)
                copies = copies[:1]
            result.files = yield from tracker.phase(
                _write_steps(copies[0], clips, settings, name, folder, context, result),
                weights["write"],
            )
            if output.keep_copy:
                _keep_in_file(copies, human, settings, result)
            else:
                _delete_copy(copies[0])
                copies = []
        else:
            _keep_in_file(copies, human, settings, result)
    except BaseException:
        for copy in copies:
            _delete_copy(copy)
        raise
    finally:
        if scratch_folder:
            shutil.rmtree(scratch_folder, ignore_errors=True)
        for image in images:
            try:
                if image.users == 0:
                    bpy.data.images.remove(image)
            except ReferenceError:
                pass

    result.seconds = time.monotonic() - started
    hg_log(f"Processed {name} in {result.seconds:.1f}s", level="DEBUG")
    return result


def _effective_settings(settings: ExportSettings) -> ExportSettings:
    """The settings with the choices a file format forces."""
    settings = settings.copy()
    if settings.output.is_file:
        settings.textures.enabled = True
    if not settings.output.has_rig:
        settings.animations.enabled = False
    if not settings.meshes.enabled:
        # Every mesh as it is, the levels only differ in their hair cards
        for quality in settings.lods:
            quality.body, quality.clothing, quality.eyes, quality.teeth = 0, "original", "original", 0
        meshes = settings.meshes
        meshes.remove_hidden_skin = meshes.remove_clothing_subdiv = meshes.remove_clothing_solidify = False
    if not settings.shape_keys.enabled:
        keys = settings.shape_keys
        keys.face_rig = keys.expressions = keys.correctives = "remove"
        for group in ("body", "face", "age"):
            if getattr(keys, group) == "keep":
                setattr(keys, group, "bake")
    return settings


def _texture_folder(
    settings: ExportSettings, folder: Optional[str]
) -> Tuple[Optional[str], Optional[str]]:
    """Where the baked images are written, None keeps them packed in the file.

    Returns:
        Tuple[Optional[str], Optional[str]]: The folder, and the same folder
            again when it is a scratch folder to remove after the export.
    """
    if folder is None:
        return settings.output.folder or None, None
    placement = settings.output.textures
    if placement == "next_to_file":
        return folder, None
    if placement == "embedded":
        # The FBX exporter embeds files, the glTF exporter packed images
        if settings.output.format == "fbx":
            scratch = tempfile.mkdtemp(prefix="hg_textures_")
            return scratch, scratch
        return None, None
    return os.path.join(folder, TEXTURES_FOLDER), None


def _level_steps(  # noqa: CCR001
    human: "Human",
    settings: ExportSettings,
    quality: QualitySettings,
    level: int,
    namer: naming.Namer,
    texture_folder: Optional[str],
    copies: List["Human"],
    images: List[bpy.types.Image],
    context: bpy.types.Context,
    weights: Dict[str, float],
    result: ExportResult,
) -> Steps["Human"]:
    """Makes one LOD level: a processed duplicate of the source human."""
    copy = human.duplicate(context)
    textures.copy_materials(copy)
    for obj in copy.objects:
        add_to_collection(context, obj, RESULTS_COLLECTION)
    copy.objects.rig[LEVEL_KEY] = level
    _run_scripts(settings, "start", context, copy, result)
    yield 0.02

    # First, so the other steps only carry the keys that stay
    keys = _level_shape_keys(settings.shape_keys, level)
    copy.process.set_shape_keys(
        face_rig=keys.face_rig,
        expressions=keys.expressions,
        correctives=keys.correctives,
        body=keys.body,
        face=keys.face,
        age=keys.age,
        keep=keys.keep,
        context=context,
    )
    _run_scripts(settings, "before_haircards", context, copy, result)
    yield 0.08

    if settings.haircards.enabled and not copy.process.has_haircards:
        for hair in (copy.hair.regular_hair, copy.hair.eyebrows, copy.hair.eyelashes, copy.hair.face_hair):
            if hair.modifiers:
                hair.convert_to_haircards(quality.haircards, context)
                yield 0.1 + 0.05 * len(copy.objects.haircards)
        copy.objects.rig["haircards"] = True
        # The particle hair is not exported and the cards replaced it
        body = copy.objects.body
        for mod in list(copy.hair.modifiers):
            body.modifiers.remove(mod)
    yield 0.3

    if quality.eyes != "original" and not copy.process.has_game_eyes:
        copy.process.convert_to_game_eyes(quality.eyes)
    if quality.teeth:
        copy.process.lod.set_teeth_lod(quality.teeth, context=context)
    _run_scripts(settings, "before_baking", context, copy, result)
    yield 0.35

    if settings.textures.enabled:
        if level == 0 or not copies:
            baked = yield from _subphase(
                textures.bake_steps(copy, settings.textures, namer, texture_folder, context),
                0.35,
                0.75,
            )
        else:
            textures.share_textures(copies[0], copy)
            baked = yield from _subphase(
                textures.bake_steps(
                    copy, settings.textures, namer, texture_folder, context, PER_LEVEL_SETS, per_level=True
                ),
                0.35,
                0.75,
            )
        images.extend(baked)
    _run_scripts(settings, "before_meshes", context, copy, result)
    yield 0.75

    if quality.body and not human.is_trial:
        copy.process.lod.set_body_lod(quality.body, context=context)
    copy.process.lod.set_clothing_lod(
        CLOTHING_DECIMATE_RATIOS[quality.clothing],
        settings.meshes.remove_clothing_subdiv,
        settings.meshes.remove_clothing_solidify,
        keep_shape_keys=True,
        context=context,
    )
    if quality.body:
        copy.objects.rig["lod"] = True
    yield 0.82

    if settings.meshes.remove_hidden_skin:
        masks.remove_hidden_skin(copy, context)
    _run_scripts(settings, "before_skeleton", context, copy, result)
    yield 0.85

    skeleton = settings.skeleton
    if skeleton.enabled and not copy.pose.rigify.is_rigify:
        if skeleton.rest_pose == "t_pose" and not copy.process.has_t_pose_rest:
            copy.process.set_t_pose_as_rest(context)
        if not copy.process.has_game_rig:
            copy.process.convert_to_game_rig(
                preset=preset_for_names(skeleton.names, skeleton.rest_pose),
                keep_eyes=skeleton.keep_eyes,
                keep_jaw=skeleton.keep_jaw,
                keep_breasts=skeleton.keep_breasts,
                keep_metacarpals=skeleton.keep_metacarpals,
                max_influences=quality.bones_per_vertex,
                root_bone=skeleton.root_bone,
                root_bone_name=skeleton.root_bone_name,
                names_file=skeleton.names_file if skeleton.names == CUSTOM_PRESET else None,
                context=context,
            )
    yield 0.95

    naming.apply_names(copy, namer)
    copy.objects.rig[EXPORT_KEY] = settings.to_json()
    _run_scripts(settings, "after_processing", context, copy, result)
    result.triangles.append(_triangles(copy))
    yield 1.0
    return copy


def _subphase(steps: Steps, start: float, end: float) -> Iterator[float]:  # type:ignore[type-arg]
    span = end - start
    while True:
        try:
            fraction = next(steps)
        except StopIteration as finished:
            return finished.value
        yield start + span * min(max(fraction, 0.0), 1.0)


def _level_shape_keys(keys: ShapeKeySettings, level: int) -> ShapeKeySettings:
    """The key actions of a level, lower levels bake everything when asked."""
    if level == 0 or not keys.lod0_only:
        return keys
    baked = keys.copy()
    for group in ("face_rig", "expressions", "correctives"):
        baked_group = "remove"
        setattr(baked, group, baked_group)
    for group in ("body", "face", "age"):
        if getattr(baked, group) == "keep":
            setattr(baked, group, "bake")
    return baked


def _triangles(human: "Human") -> int:
    total = 0
    for obj in human.objects:
        if obj.type == "MESH":
            total += len(obj.data.loops) - 2 * len(obj.data.polygons)
    return total


def _run_scripts(
    settings: ExportSettings,
    stage: str,
    context: bpy.types.Context,
    human: "Human",
    result: ExportResult,
    files: Optional[List[str]] = None,
) -> None:
    for script in settings.scripts.active():
        if script.stage != stage:
            continue
        warning = scripts.run_script(script, context, human, files)
        if warning:
            result.warnings.append(warning)


def _write_steps(  # noqa: CCR001
    human: "Human",
    clips: List[bpy.types.Action],
    settings: ExportSettings,
    name: str,
    folder: str,
    context: bpy.types.Context,
    result: ExportResult,
) -> Steps[List[str]]:
    """Writes the character, with the meshes of every level, and the clips."""
    output = settings.output
    _run_scripts(settings, "before_export", context, human, result)
    yield 0.1

    files: List[str] = []
    embedded = output.textures == "embedded"
    fbx = output.fbx
    fbx_kwargs = {
        "axis_forward": fbx.axis_forward,
        "axis_up": fbx.axis_up,
        "primary_bone_axis": fbx.primary_bone_axis,
        "secondary_bone_axis": fbx.secondary_bone_axis,
        "use_leaf_bones": fbx.leaf_bones,
        "export_custom_props": fbx.custom_properties,
        "triangulate": fbx.triangulate,
        "mesh_smooth_type": fbx.smoothing,
        "apply_scale_options": "FBX_SCALE_ALL" if settings.skeleton.units == "centimeters" else "FBX_SCALE_NONE",
        "path_mode": "COPY" if embedded else "RELATIVE",
        "embed_textures": embedded,
        "context": context,
    }
    gltf_kwargs = {
        "image_format": output.gltf.image_format,
        "tangents": output.gltf.tangents,
        "draco": output.gltf.draco,
        "context": context,
    }
    clips_with_mesh = bool(clips) and settings.animations.layout == "with_mesh"
    animation = "strips" if clips_with_mesh else "none"

    with naming.exact_names(naming.datablocks(human) + list(clips)):
        path = os.path.join(folder, name)
        if output.format == "fbx":
            files.append(human.export.to_fbx(path, animation=animation, **fbx_kwargs))
        elif output.format == "glb":
            files.append(human.export.to_glb(path, animation=animation, **gltf_kwargs))
        elif output.format == "gltf":
            files.append(human.export.to_gltf_separate(path, animation=animation, **gltf_kwargs))
        elif output.format == "obj":
            files.append(human.export.to_obj(path, context=context))
        elif output.format == "abc":
            files.append(human.export.to_abc(path, context=context))
        yield 0.6

        if clips and not clips_with_mesh:
            if settings.animations.layout == "single_file":
                clip_path = os.path.join(folder, f"{name}_Animations")
                files.append(_write_clips(human, output.format, clip_path, "strips", fbx_kwargs, gltf_kwargs))
            else:
                for clip in clips:
                    clip_path = os.path.join(folder, animations.clip_file_name(name, clip))
                    with animations.active_clip(human, clip):
                        files.append(_write_clips(human, output.format, clip_path, "active", fbx_kwargs, gltf_kwargs))
        yield 0.9

    _run_scripts(settings, "after_export", context, human, result, files)
    return [path for path in files if path]


def _write_clips(human: "Human", file_format: str, path: str, animation: str, fbx_kwargs: dict, gltf_kwargs: dict) -> str:  # type:ignore[type-arg]
    if file_format == "fbx":
        return human.export.to_fbx(path, animation=animation, armature_only=True, **fbx_kwargs)
    if file_format == "glb":
        return human.export.to_glb(path, animation=animation, armature_only=True, **gltf_kwargs)
    return human.export.to_gltf_separate(path, animation=animation, armature_only=True, **gltf_kwargs)


def _merge_levels(copies: List["Human"]) -> None:
    """Puts the meshes of every level under the skeleton of the first level.

    The skeletons are identical, they were converted from the same source with
    the same settings, so the meshes of the other levels can use the first one.
    The other rigs are removed.
    """
    rig = copies[0].objects.rig
    for copy in copies[1:]:
        old_rig = copy.objects.rig
        for obj in list(old_rig.children):
            matrix = obj.matrix_world.copy()
            obj.parent = rig
            obj.matrix_world = matrix
            for mod in obj.modifiers:
                if mod.type == "ARMATURE" and mod.object == old_rig:
                    mod.object = rig
            key = obj.data.shape_keys if obj.type == "MESH" else None
            if key and key.animation_data:
                for fcurve in key.animation_data.drivers:
                    for variable in fcurve.driver.variables:
                        for target in variable.targets:
                            if target.id == old_rig:
                                target.id = rig
        animations.remove_clips(copy)
        bpy.data.objects.remove(old_rig)


def _keep_in_file(
    copies: List["Human"], source: "Human", settings: ExportSettings, result: ExportResult
) -> None:
    """Marks the copies as frozen results next to the source human."""
    for index, copy in enumerate(copies):
        copy.process.mark_as_processed(source)
        if not settings.output.is_file:
            copy.location = source.location + Vector((0, RESULT_SPACING * (index + 1), 0))
        result.humans.append(copy)


def _delete_copy(copy: "Human") -> None:
    try:
        animations.remove_clips(copy)
        copy.delete()
    except (ReferenceError, RuntimeError) as e:
        hg_log(f"Could not remove processed copy: {e}", level="WARNING")


def settings_of(human: "Human") -> Optional[ExportSettings]:
    """The settings a processed human was made with, None for other humans."""
    text = human.objects.rig.get(EXPORT_KEY)
    if not text:
        return None
    try:
        return ExportSettings.from_json(str(text))
    except (ValueError, TypeError) as e:
        hg_log(f"Could not read the export settings of {human.name}: {e}", level="WARNING")
        return None
