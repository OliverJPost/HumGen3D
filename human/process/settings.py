# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Settings of the process system, one schema for every way they are used.

A recipe file on disk, the interface, the argument of `ProcessSettings.run` and
the metadata on a processed human all hold the same `ExportSettings`. Every
field has a control in the interface and every control is a field here, so a
recipe is nothing more than the serialized state of the panel.

The built-in recipes hold the knowledge about each engine: bone names, rest
pose, texture packing, normal map direction and file layout. Adding an engine is
adding a recipe, not code. They come with the HG_Export content pack, in the
`process/recipes` folder of the content folder, see `export_pack`.
"""

from __future__ import annotations

import dataclasses
import json
import os
import typing
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple, Type, TypeVar

from ...backend.logging import hg_log
from ...backend.preferences.preference_func import get_prefs

from . import export_pack

SCHEMA_VERSION = 2
RECIPE_EXTENSION = ".json"
# Folder in the content folder with the recipes of the user, kept from older versions
USER_RECIPE_FOLDER = "process_templates"


def shipped_recipe_folder() -> str:
    """Folder with the built-in recipes, raises `ExportPackMissing` without the pack."""
    return export_pack.data_path("recipes")


# Identifier, label and description of the enum settings. The interface draws
# these, the settings store the identifier.
OUTPUT_FORMATS = [
    ("in_file", "In this file", "Add the processed human to this file as a frozen copy"),
    ("fbx", "FBX", "Autodesk FBX, for Unity, Unreal and most other programs"),
    ("glb", "glTF Binary (.glb)", "One file with the textures inside, for Godot and the web"),
    ("gltf", "glTF + textures", "glTF with the textures as files next to it"),
    ("obj", "OBJ (no rig)", "Wavefront OBJ, meshes only, without skeleton or animation"),
    ("abc", "Alembic (no rig)", "Alembic cache, meshes only, without skeleton"),
]
FILE_FORMATS = tuple(identifier for identifier, *_ in OUTPUT_FORMATS[1:])
RIGGED_FORMATS = ("in_file", "fbx", "glb", "gltf")
NAMING_SCHEMES = [
    ("plain", "Plain", "Jake_Body, Jake_Skin, Jake_Body_BaseColor"),
    (
        "unreal",
        "Unreal prefixes",
        "SK_Jake_Body, M_Jake_Skin, T_Jake_Body_BC, as the Unreal style guide",
    ),
    ("custom", "Custom", "Templates with {name}, {part} and {pass} tokens"),
]
TEXTURE_PLACEMENTS = [
    ("folder", "Textures folder", "In a Textures folder next to the file"),
    ("next_to_file", "Next to file", "In the same folder as the file"),
    ("embedded", "Embedded", "Inside the FBX or glb file"),
]
TEXTURE_WORKFLOWS = [
    ("separate", "Separate maps", "One grayscale file per map"),
    (
        "metallic_roughness",
        "Metallic-Roughness",
        "Roughness in G, metallic in B, as glTF and Godot expect",
    ),
    ("orm", "ORM", "Occlusion in R, roughness in G, metallic in B, as Unreal expects"),
    (
        "metallic_smoothness",
        "Metallic-Smoothness",
        "Metallic in RGB, smoothness in A, as the Unity Standard and URP shaders expect",
    ),
]
NORMAL_MAP_DIRECTIONS = [
    ("opengl", "OpenGL (Y+)", "Blender, Unity, Godot, glTF and Unreal materials made for it"),
    ("directx", "DirectX (Y−)", "Unreal by default"),
]
TEXTURE_FORMATS = [
    ("png", "PNG", "Lossless, keeps the alpha of the haircards"),
    ("jpeg", "JPEG", "Smaller files, no alpha channel"),
]
TEXTURE_SETS = ("body", "clothing", "eyes", "teeth", "hair")
TEXTURE_PASSES = [
    ("base_color", "Base color", ""),
    ("normal", "Normal", ""),
    ("roughness", "Roughness", ""),
    ("metallic", "Metallic", ""),
    ("alpha", "Alpha", "Transparency, the hair cards need it"),
    ("flow", "Flow", "Direction of the strands and a noise per strand on the hair cards, for the hair shaders of the Companions"),
]
CLIP_SOURCES = [
    ("human", "On this human", "The animations set on the human, active and in the NLA"),
    ("library", "From library", "Animations of the library, retargeted to the character"),
]
CLIP_LAYOUTS = [
    ("single_file", "One file with all clips", "Every clip as a take in one file"),
    ("per_clip", "One file per clip", "Jake@Run.fbx, the convention of Unity"),
    ("with_mesh", "In the mesh file", "The clips as takes of the exported character"),
]
ROOT_MOTION_OPTIONS = [
    ("hips", "Keep on hips", "The hips carry the movement, as in Blender"),
    ("root", "Move to root bone", "The root bone carries the movement, the hips stay"),
]
# The points of the pipeline a script can run at, in the order of the steps.
# The first six run on every LOD level, the last two once on the character.
SCRIPT_STAGES = [
    (
        "start",
        "Start",
        "On the fresh copy of the human, before anything is changed",
    ),
    (
        "before_haircards",
        "Before haircards",
        "After the shape keys are kept, baked or removed",
    ),
    (
        "before_baking",
        "Before baking",
        "After the hair cards, game eyes and teeth, before the materials are baked",
    ),
    (
        "before_meshes",
        "Before mesh optimization",
        "After the textures are baked, before the meshes are reduced",
    ),
    (
        "before_skeleton",
        "Before skeleton",
        "After the meshes are reduced, before the rig is converted",
    ),
    (
        "after_processing",
        "After processing",
        "On the finished level, with its final names",
    ),
    (
        "before_export",
        "Before export",
        "Once on the character with every level, right before the file is written",
    ),
    ("after_export", "After export", "After the files are written, gets their paths"),
]
# Stages that only exist when a file is written
EXPORT_STAGES = ("before_export", "after_export")
SCRIPT_ERROR_POLICIES = [
    ("stop", "Stop", "Stop processing when the script fails"),
    ("skip", "Skip", "Report the failure and continue"),
]
FBX_AXES = [(axis, axis, "") for axis in ("X", "Y", "Z", "-X", "-Y", "-Z")]
FBX_SMOOTHING = [
    ("FACE", "Face", "Smoothing groups per face"),
    ("EDGE", "Edge", "Smoothing per edge"),
    ("OFF", "Off", "Normals only"),
]
GLTF_IMAGE_FORMATS = [("AUTO", "Auto", "PNG, JPEG where no alpha is needed"), ("JPEG", "JPEG", "")]


T = TypeVar("T", bound="Settings")

# The level of `LodSettings.set_body_lod` and `set_teeth_lod` of each option
BODY_LEVELS: Dict[str, int] = {"original": 0, "lower_face": 1, "quarter": 2}
TEETH_LEVELS: Dict[str, int] = {"original": 0, "medium": 1, "low": 2}


@dataclass
class Settings:
    """Base of the settings dataclasses, JSON in and out."""

    def to_dict(self) -> Dict[str, Any]:
        """The settings as plain dict, nested settings included."""
        return _to_plain(self)

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Settings from a dict, missing fields get their default.

        Unknown keys are logged and ignored, so recipes of a newer version still
        load as far as possible.
        """
        return _from_plain(cls, data)

    def copy(self: T) -> T:
        """A deep copy."""
        return self.from_dict(self.to_dict())

    @classmethod
    def _upgrade(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """The data with values of earlier versions turned into current ones."""
        return data


@dataclass
class QualitySettings(Settings):
    """Detail of the meshes of one LOD level, see quality.py for the tiers."""

    # "lower_face" reduces the face only, "quarter" the whole body to a quarter
    body: Literal["original", "lower_face", "quarter"] = "original"
    clothing: Literal["original", "high", "medium", "low"] = "high"
    # "original" keeps the layered eyes, which are not game ready
    eyes: Literal["original", "high", "medium", "low"] = "high"
    teeth: Literal["original", "medium", "low"] = "medium"
    haircards: Literal["ultra", "high", "medium", "low", "haircap_only"] = "high"
    bones_per_vertex: int = 4  # 0 for no limit

    @classmethod
    def _upgrade(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Body and teeth were numbers before they were names."""
        for key, levels in (("body", BODY_LEVELS), ("teeth", TEETH_LEVELS)):
            value = data.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                data[key] = next((name for name, level in levels.items() if level == value), value)
        return data

    @classmethod
    def from_tier(cls, tier: str) -> "QualitySettings":
        """The settings of a quality tier, see `quality.QUALITY_TIERS`.

        Args:
            tier (str): "original", "ultra", "high", "medium", "low" or "mobile".

        Raises:
            ValueError: If the tier does not exist.
        """
        from .quality import quality_of_tier

        return quality_of_tier(tier)


@dataclass
class MeshSettings(Settings):
    """Changes to the meshes that apply to every level.

    When disabled every mesh stays as it is: the body, clothing, eyes and teeth
    quality of the levels is ignored and nothing below applies. The hair cards
    and the bones per vertex are their own sections.
    """

    enabled: bool = True
    # Apply the mask modifiers that hide the skin under the clothing
    remove_hidden_skin: bool = True
    remove_clothing_subdiv: bool = True
    remove_clothing_solidify: bool = True


@dataclass
class HaircardSettings(Settings):
    """Whether the particle hair becomes hair cards. The quality is per level."""

    enabled: bool = True


@dataclass
class SkeletonSettings(Settings):
    """Conversion of the rig to a skeleton for game engines, see game_rig.py."""

    enabled: bool = True
    names: str = "humanoid"  # humanoid, unreal, mixamo, humgen, custom
    names_file: str = ""  # path of a names profile for "custom", see game_rig.py
    rest_pose: str = "t_pose"  # a_pose, t_pose
    root_bone: bool = True
    root_bone_name: str = "Root"
    keep_eyes: bool = True
    keep_jaw: bool = True
    keep_breasts: bool = True
    keep_metacarpals: bool = False
    units: str = "meters"  # meters, centimeters. FBX only.


@dataclass
class ShapeKeySettings(Settings):
    """Keep, bake or remove per group of keys, see shape_keys.py.

    When disabled no shape keys are kept: the driven groups are removed and the
    sliders are baked at their current value.
    """

    enabled: bool = True
    face_rig: str = "keep"
    expressions: str = "keep"
    correctives: str = "keep"
    body: str = "bake"
    face: str = "bake"
    age: str = "bake"
    # Per group the display names of the keys to keep, see shape_keys.keep_options.
    # A group that is missing or None keeps everything available, so a recipe
    # that keeps every key applies to any human.
    keep: Dict[str, Optional[List[str]]] = field(default_factory=dict)
    # Engines want the face blend shapes on the first level only
    lod0_only: bool = True


@dataclass
class TextureBakeSettings(Settings):
    """Baking of the materials to textures, see textures.py."""

    # Only a choice for the in-file output, every file format needs the textures
    enabled: bool = True
    resolution: Dict[str, int] = field(
        default_factory=lambda: {
            "body": 2048,
            "clothing": 2048,
            "eyes": 512,
            "teeth": 512,
            "hair": 1024,
        }
    )
    passes: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "body": ["base_color", "normal", "roughness", "metallic"],
            "clothing": ["base_color", "normal", "roughness", "metallic"],
            "eyes": ["base_color", "normal"],
            "teeth": ["base_color", "normal", "roughness"],
            "hair": ["base_color", "normal", "roughness", "alpha", "flow"],
        }
    )
    file_format: str = "png"  # png, jpeg
    workflow: str = "separate"  # see TEXTURE_WORKFLOWS
    normal_map: str = "opengl"  # opengl, directx
    pack_hair_alpha: bool = True
    # Paint the haircaps of the scalp hair, face hair and eyebrows into the skin
    # textures and leave their meshes out, see haircap_skin.py
    haircap_in_skin: bool = True
    samples: int = 4

    def set_resolution_tier(self, tier: str) -> None:
        """Sets the resolution of every texture set to a tier, "4k", "2k", "1k" or "512".

        Raises:
            ValueError: If the tier does not exist.
        """
        from .quality import resolution_of_tier

        self.resolution = resolution_of_tier(tier)


@dataclass
class AnimationClipSettings(Settings):
    """Export of the animations on the human, see animations.py."""

    enabled: bool = False
    # "human": the animations on the human, "library": clips from the library
    source: str = "human"
    # Action names (human) or preset paths (library) to export, None for all
    clips: Optional[List[str]] = None
    layout: str = "single_file"  # see CLIP_LAYOUTS
    sample_rate: int = 0  # Frames per second, 0 for the scene frame rate. FBX only.
    root_motion: str = "hips"  # hips, root


@dataclass
class ScriptSettings(Settings):
    """A script to run at a stage of the process, see scripts.py."""

    path: str = ""
    stage: str = "after_processing"  # see SCRIPT_STAGES
    args: Dict[str, Any] = field(default_factory=dict)
    on_error: str = "stop"  # stop, skip


@dataclass
class ScriptsSettings(Settings):
    """The scripts to run, in order, and whether they run at all."""

    enabled: bool = False
    items: List[ScriptSettings] = field(default_factory=list)

    def active(self) -> List[ScriptSettings]:
        """The scripts that run, none when disabled."""
        return list(self.items) if self.enabled else []


@dataclass
class FbxSettings(Settings):
    """Settings of the FBX exporter, see export.py."""

    axis_forward: str = "-Z"
    axis_up: str = "Y"
    primary_bone_axis: str = "Y"
    secondary_bone_axis: str = "X"
    leaf_bones: bool = False
    custom_properties: bool = False
    triangulate: bool = False
    smoothing: str = "FACE"  # FACE, EDGE, OFF


@dataclass
class GltfSettings(Settings):
    """Settings of the glTF exporter, see export.py."""

    tangents: bool = False
    image_format: str = "AUTO"  # AUTO, JPEG
    draco: bool = False


@dataclass
class OutputSettings(Settings):
    """Where the result goes and how it is named."""

    format: str = "fbx"  # see OUTPUT_FORMATS
    folder: str = ""  # Empty for the export folder of the content folder
    # Name of the files and prefix of the objects, {name} is the name of the human
    name: str = "{name}"
    naming: str = "plain"  # plain, unreal, custom
    naming_templates: Dict[str, str] = field(
        default_factory=lambda: {
            "rig": "{name}",
            "mesh": "{name}_{part}",
            "material": "{name}_{part}",
            "texture": "{name}_{part}_{pass}",
        }
    )
    textures: str = "folder"  # folder, next_to_file, embedded
    # Keep the processed copy in the file after writing it
    keep_copy: bool = False
    fbx: FbxSettings = field(default_factory=FbxSettings)
    gltf: GltfSettings = field(default_factory=GltfSettings)

    @property
    def is_file(self) -> bool:
        """Whether the result is written to a file."""
        return self.format != "in_file"

    @property
    def has_rig(self) -> bool:
        """Whether the format carries a skeleton."""
        return self.format in RIGGED_FORMATS

    def resolved_name(self, human_name: str) -> str:
        """The output name with the tokens filled in.

        Args:
            human_name (str): Name of the source human.
        """
        name = self.name.replace("{name}", human_name).strip()
        return name or human_name


@dataclass
class ExportSettings(Settings):
    """Everything the process system needs to process a human."""

    version: int = SCHEMA_VERSION
    # Recipe this was loaded from, informational
    recipe: str = ""
    output: OutputSettings = field(default_factory=OutputSettings)
    # One entry per LOD level, the first is the full character
    lods: List[QualitySettings] = field(default_factory=lambda: [QualitySettings()])
    meshes: MeshSettings = field(default_factory=MeshSettings)
    haircards: HaircardSettings = field(default_factory=HaircardSettings)
    skeleton: SkeletonSettings = field(default_factory=SkeletonSettings)
    shape_keys: ShapeKeySettings = field(default_factory=ShapeKeySettings)
    textures: TextureBakeSettings = field(default_factory=TextureBakeSettings)
    animations: AnimationClipSettings = field(default_factory=AnimationClipSettings)
    scripts: ScriptsSettings = field(default_factory=ScriptsSettings)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExportSettings":
        """Settings from a dict, see `Settings.from_dict`."""
        scripts = data.get("scripts")
        if isinstance(scripts, list):
            # Before the scripts had a toggle, the list was the setting
            data = dict(data, scripts={"enabled": bool(scripts), "items": scripts})
        return _from_plain(cls, data)

    @classmethod
    def from_recipe(cls, recipe: str) -> "ExportSettings":
        """Settings of a recipe, shipped or from the content folder.

        Args:
            recipe (str): Identifier from `recipe_items`, or a path of a recipe
                file, or of the `.humgen3d.json` file next to an exported
                character for the settings it was made with.

        Returns:
            ExportSettings: The settings of the recipe.

        Raises:
            ExportPackMissing: If the HG_Export content pack, which holds the
                built-in recipes, is not installed.
            FileNotFoundError: If there is no such recipe.
        """
        export_pack.require()
        path = recipe_path(recipe)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"No recipe '{recipe}'")
        with open(path, "r") as f:
            data = json.load(f)
        if "humgen3d_export" in data:
            # The manifest next to an exported character, see manifest.py
            data = data.get("settings", {})
        if data.get("version", 1) < 2:
            from .migrate import migrate_v1

            data = migrate_v1(data)
        settings = cls.from_dict(data)
        settings.version = SCHEMA_VERSION
        settings.recipe = recipe
        return settings

    def save_recipe(self, folder: str, name: str) -> str:
        """Writes the settings as recipe file for the user, in a group folder.

        Args:
            folder (str): Group folder inside the recipe folder of the content
                folder, created if needed.
            name (str): Name of the recipe, becomes the file name.

        Returns:
            str: Path of the written file.
        """
        directory = os.path.join(get_prefs().filepath, USER_RECIPE_FOLDER, folder)
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, name + RECIPE_EXTENSION)
        data = self.to_dict()
        data["recipe"] = ""
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
        return path

    def to_json(self) -> str:
        """The settings as JSON string, for storing on the result."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, text: str) -> "ExportSettings":
        """Settings from a JSON string made by `to_json`."""
        return cls.from_dict(json.loads(text))

    def differs_from(self, other: "ExportSettings") -> bool:
        """Whether any setting other than the recipe name differs."""
        mine, theirs = self.to_dict(), other.to_dict()
        mine.pop("recipe", None)
        theirs.pop("recipe", None)
        return mine != theirs

    def resolved_name(self, human_name: str) -> str:
        """The output name with the tokens filled in, see `OutputSettings.resolved_name`."""
        return self.output.resolved_name(human_name)


def recipe_path(recipe: str) -> str:
    """Path of a recipe file for an identifier from `recipe_items`.

    Shipped recipes are a bare name, user recipes a path relative to the recipe
    folder of the content folder. A path to an existing file is returned as is.
    """
    if os.path.isabs(recipe) and os.path.isfile(recipe):
        return recipe
    shipped = os.path.join(shipped_recipe_folder(), recipe + RECIPE_EXTENSION)
    if os.path.isfile(shipped):
        return shipped
    return os.path.join(get_prefs().filepath, USER_RECIPE_FOLDER, recipe)


def recipe_items() -> List[Tuple[str, str, str]]:
    """Identifier, label and group of every recipe, shipped ones first.

    The order of the shipped recipes is that of `recipes/order.json`.

    Raises:
        ExportPackMissing: If the HG_Export content pack is not installed.
    """
    items = []
    order_path = os.path.join(shipped_recipe_folder(), "order.json")
    with open(order_path, "r") as f:
        for identifier in json.load(f):
            with open(recipe_path(identifier), "r") as recipe_file:
                label = json.load(recipe_file).get("label", identifier)
            items.append((identifier, label, "Built-in"))

    root = os.path.join(get_prefs().filepath, USER_RECIPE_FOLDER)
    if not os.path.isdir(root):
        return items
    for directory, _, files in sorted(os.walk(root)):
        group = os.path.basename(directory) if directory != root else "Saved"
        for file in sorted(files):
            if not file.endswith(RECIPE_EXTENSION):
                continue
            path = os.path.join(directory, file)
            if not _loads(path):
                continue
            relpath = os.path.relpath(path, root)
            items.append((relpath, file[: -len(RECIPE_EXTENSION)], group))
    return items


# Whether a recipe file of the user loads, by path, with the time it was changed
_load_checks: Dict[str, Tuple[float, bool]] = {}


def _loads(path: str) -> bool:
    """Whether a recipe file loads, so files that don't are left out of the list.

    Recipes of older versions that the migration can't read and files that
    are no recipe at all are dropped this way. The answer is kept until the
    file changes, the interface asks for the list on every redraw.
    """
    try:
        changed = os.path.getmtime(path)
    except OSError:
        return False
    known = _load_checks.get(path)
    if known and known[0] == changed:
        return known[1]
    try:
        ExportSettings.from_recipe(path)
        ok = True
    except Exception as e:  # noqa: B902, a broken file must not break the list
        hg_log(f"Leaving out recipe {path}, it can't be loaded: {e}", level="WARNING")
        ok = False
    _load_checks[path] = (changed, ok)
    return ok


def _to_plain(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {
            f.name: _to_plain(getattr(value, f.name)) for f in dataclasses.fields(value)
        }
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_plain(item) for key, item in value.items()}
    return value


def _from_plain(cls: Type[T], data: Dict[str, Any]) -> T:
    data = cls._upgrade(dict(data))
    hints = typing.get_type_hints(cls)
    kwargs = {}
    known = {f.name for f in dataclasses.fields(cls)}
    for key, value in data.items():
        if key not in known:
            hg_log(f"Ignoring unknown setting '{key}' of {cls.__name__}", level="DEBUG")
            continue
        kwargs[key] = _convert(hints[key], value)
    return cls(**kwargs)


def _convert(hint: Any, value: Any) -> Any:
    """Turns a plain value into the type of a field, for nested settings."""
    origin = typing.get_origin(hint)
    args = typing.get_args(hint)
    if origin is typing.Union:
        # Optional[X]: None stays None, anything else converts to X
        if value is None:
            return None
        hint = next(arg for arg in args if arg is not type(None))
        return _convert(hint, value)
    if isinstance(hint, type) and dataclasses.is_dataclass(hint):
        return _from_plain(hint, value) if isinstance(value, dict) else value
    if origin in (list, List) and args and isinstance(value, list):
        return [_convert(args[0], item) for item in value]
    return value
