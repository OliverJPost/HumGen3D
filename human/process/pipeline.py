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
from mathutils import Vector

from . import animations, naming, scripts, textures
from .game_rig import check_names_file
from .settings import EXPORT_STAGES, ExportSettings, QualitySettings
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
    the settings leave it empty.

    A folder starting with "//" is relative to the blend file, the settings keep
    it that way and it is resolved here.
    """
    folder = settings.output.folder
    if folder.startswith("//"):
        folder = bpy.path.abspath(folder)
    if not folder:
        folder = os.path.join(get_prefs().filepath, DEFAULT_EXPORT_FOLDER)
    return os.path.abspath(folder)


def result_name(settings: ExportSettings, human_name: str) -> str:
    """The name of the result: the files and the {name} of every datablock.

    The name of the human is cleaned like the datablock names, without the
    number suffix of Blender, spaces or odd characters, before the tokens of
    the output name go around it: "Jake Smith.001" becomes "Jake_Smith".
    """
    return naming.clean(settings.resolved_name(naming.clean(human_name)))


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
        if output.folder.startswith("//") and not bpy.data.filepath:
            result.errors.append("Save the blend file first, the folder is relative to it")
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
        else:
            try:
                check_names_file(settings.skeleton.names_file)
            except HumGenException as e:
                result.errors.append(str(e))
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
    """Rough cost of each step, about seconds on a fast machine.

    Baking dominates: every object is a Cycles session per pass, close to a
    second each, see textures.py. The hair is one object per hair type.
    """
    hair_types = sum(1 for hair in human.hair.hair_types if hair.modifiers)
    clothing = len(human.clothing.outfit.objects) + len(human.clothing.footwear.objects)
    passes_per_set = sum(len(p) for p in settings.textures.passes.values()) / 5
    objects = 3 + clothing + hair_types
    return {
        "duplicate": 0.5,
        "shape_keys": 4.0,
        "haircards": 2.5 * hair_types if settings.haircards.enabled else 0.0,
        "eyes_teeth": 0.3,
        "textures": 1.0 * objects * passes_per_set,
        "textures_level": 0.6 * (1 + hair_types) * passes_per_set,
        "lod": 1.0 + 0.35 * clothing,
        "masks": 0.3,
        "skeleton": 2.5,
        "naming": 0.1,
        "animations": 0.5,
        "write": 5.0,
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

    name = result_name(settings, human.name)
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
    existing = _datablocks()
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
                copies[0].process.merge_levels(copies[1:])
                copies = copies[:1]
            result.files = yield from tracker.phase(
                _write_steps(copies[0], clips, settings, name, folder, context, result),
                weights["write"],
            )
            if output.keep_copy:
                _keep_in_file(copies, human, result)
            else:
                _delete_copy(copies[0])
                copies = []
        else:
            _keep_in_file(copies, human, result)
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
        _remove_orphans(existing)

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
    """Makes one LOD level: a processed duplicate of the source human.

    The steps are the public methods of `ProcessSettings`, in the order its
    docstring gives; this adds the scripts, the progress and the sharing of
    textures between levels. The copy is removed when a step fails or the
    steps are closed before the level is done.
    """
    copy = human.duplicate(context)
    try:
        return (
            yield from _process_level(
                copy, human, settings, quality, level, namer, texture_folder, copies, images, context, result
            )
        )
    except BaseException:
        _delete_copy(copy)
        raise


def _process_level(  # noqa: CCR001
    copy: "Human",
    human: "Human",
    settings: ExportSettings,
    quality: QualitySettings,
    level: int,
    namer: naming.Namer,
    texture_folder: Optional[str],
    copies: List["Human"],
    images: List[bpy.types.Image],
    context: bpy.types.Context,
    result: ExportResult,
) -> Steps["Human"]:
    # Renaming and baking must not reach the materials of the source human
    textures.copy_materials(copy)
    for obj in copy.objects:
        add_to_collection(context, obj, RESULTS_COLLECTION)
    copy.objects.rig[LEVEL_KEY] = level
    _run_scripts(settings, "start", context, copy, result)
    yield 0.02

    copy.process.set_shape_keys(settings.shape_keys, level, context=context)
    _run_scripts(settings, "before_haircards", context, copy, result)
    yield 0.08

    if settings.haircards.enabled and not copy.process.has_haircards:
        copy.process.convert_to_haircards(quality.haircards, context)
    yield 0.3

    # The eyes and teeth before baking, they change the materials
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
            copy.process.share_textures(copies[0])
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

    # The eyes and teeth are done already, this reduces the body and clothing
    copy.process.set_quality(quality, settings.meshes, context=context)
    _run_scripts(settings, "before_skeleton", context, copy, result)
    yield 0.85

    if settings.skeleton.enabled and not copy.pose.rigify.is_rigify and not copy.process.has_game_rig:
        copy.process.convert_to_game_rig(
            settings=settings.skeleton,
            max_influences=quality.bones_per_vertex,
            context=context,
        )
    yield 0.95

    naming.apply_names(copy, namer)
    copy.objects.rig[EXPORT_KEY] = settings.to_json()
    # The hair cards are made after the copy moved to the results collection
    results = bpy.data.collections.get(RESULTS_COLLECTION)
    for obj in copy.objects:
        if not results or obj.name not in results.objects:
            add_to_collection(context, obj, RESULTS_COLLECTION)
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
    units = settings.skeleton.units
    sample_rate = settings.animations.sample_rate
    clips_with_mesh = bool(clips) and settings.animations.layout == "with_mesh"
    animation = "strips" if clips_with_mesh else "none"

    path = os.path.join(folder, name)
    files.append(
        human.export.write(path, output, units, animation, sample_rate=sample_rate, context=context)
    )
    yield 0.6

    if clips and not clips_with_mesh:
        if settings.animations.layout == "single_file":
            clip_path = os.path.join(folder, f"{name}_Animations")
            files.append(
                human.export.write(
                    clip_path, output, units, "strips", armature_only=True, sample_rate=sample_rate, context=context
                )
            )
        else:
            for clip in clips:
                clip_path = os.path.join(folder, animations.clip_file_name(name, clip))
                with animations.active_clip(human, clip):
                    files.append(
                        human.export.write(
                            clip_path, output, units, "active", armature_only=True, sample_rate=sample_rate, context=context
                        )
                    )
    yield 0.9

    _run_scripts(settings, "after_export", context, human, result, files)
    return [path for path in files if path]


def _keep_in_file(copies: List["Human"], source: "Human", result: ExportResult) -> None:
    """Marks the copies as frozen results and places them next to the source
    human, a copy kept after a file export as well."""
    for index, copy in enumerate(copies):
        copy.process.mark_as_processed(source)
        copy.location = source.location + Vector((0, RESULT_SPACING * (index + 1), 0))
        result.humans.append(copy)


# Datablocks a run makes that can end up without users, see _remove_orphans
ORPHAN_COLLECTIONS = ("materials", "node_groups", "images", "armatures", "meshes", "actions")


def _datablocks() -> Dict[str, set]:
    """Pointers of the datablocks in the file, removed ones can't be compared."""
    return {
        name: {block.as_pointer() for block in getattr(bpy.data, name)}
        for name in ORPHAN_COLLECTIONS
    }


def _remove_orphans(existing: Dict[str, set]) -> None:
    """Removes what the run made that nothing uses anymore.

    The copies of the particle hair materials lose their slots, the levels
    after the first replace their materials by those of the first and removed
    copies leave their data. Removing a node group can free an image, so this
    repeats until nothing is left. What was in the file before is not touched.
    """
    removed = True
    while removed:
        removed = False
        for name in ORPHAN_COLLECTIONS:
            data = getattr(bpy.data, name)
            for block in list(data):
                if block.users == 0 and block.as_pointer() not in existing[name]:
                    data.remove(block)
                    removed = True


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
