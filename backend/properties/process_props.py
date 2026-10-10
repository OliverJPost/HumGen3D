# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Blender properties of the Process tab, a view on `ExportSettings`.

The property groups mirror the settings schema field for field, see
`props_to_settings` and `settings_to_props`. The interface edits these, the
process operator turns them into settings, a recipe is the settings saved.
"""

import os
from typing import Any, Dict, List, Optional, Tuple

import bpy
from bpy.props import (  # type:ignore
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from HumGen3D.backend.logging import hg_log
from HumGen3D.human.process import scripts as script_tools
from HumGen3D.human.process.game_rig import INFLUENCE_LIMITS, REST_POSE_ITEMS, UNIT_ITEMS
from HumGen3D.human.process.quality import (
    CUSTOM_TIER,
    RESOLUTIONS,
    TEXTURE_TIERS,
    quality_of_tier,
    resolution_of_tier,
    texture_tier_of,
    tier_of,
)
from HumGen3D.human.process.settings import (
    CLIP_LAYOUTS,
    CLIP_SOURCES,
    FBX_AXES,
    FBX_SMOOTHING,
    GLTF_IMAGE_FORMATS,
    NAMING_SCHEMES,
    NORMAL_MAP_DIRECTIONS,
    OUTPUT_FORMATS,
    ROOT_MOTION_OPTIONS,
    SCRIPT_ERROR_POLICIES,
    SCRIPT_STAGES,
    TEXTURE_FORMATS,
    TEXTURE_PASSES,
    TEXTURE_PLACEMENTS,
    TEXTURE_SETS,
    TEXTURE_WORKFLOWS,
    AnimationClipSettings,
    ExportSettings,
    FbxSettings,
    GltfSettings,
    HaircardSettings,
    MeshSettings,
    OutputSettings,
    QualitySettings,
    ScriptSettings,
    ScriptsSettings,
    ShapeKeySettings,
    SkeletonSettings,
    TextureBakeSettings,
    recipe_items,
)
from HumGen3D.human.process.shape_keys import (
    GROUP_ACTIONS,
    KEY_ACTIONS,
    KEY_GROUPS,
    keep_options,
)
from HumGen3D.user_interface.icons.icons import get_hg_icon

MAX_LOD_LEVELS = 4
# Tier of each level added after the first, so a new level is lower than the last
NEXT_TIERS = {"original": "high", "ultra": "high", "high": "medium", "medium": "low", "low": "mobile", "mobile": "mobile", "custom": "low"}

# Blender keeps pointers to the strings of dynamic enum items, so keep them alive
_recipe_enum_items: List[Tuple[Any, ...]] = []
_haircard_quality_items: List[Tuple[Any, ...]] = []
_script_enum_items: List[Tuple[Any, ...]] = []
_clip_enum_items: List[Tuple[Any, ...]] = []
# Set while a recipe is loaded into the properties, so updates don't react
_loading = False


def _enum(items: List[Tuple[str, str, str]]) -> List[Tuple[str, str, str, int]]:
    return [(ident, label, desc, i) for i, (ident, label, desc) in enumerate(items)]


# Identifier, name, description and stored value of the haircard qualities. The
# value of "high" is 0, which makes it the default of the dynamic enum.
HAIRCARD_QUALITIES = [
    ("ultra", "Ultra", "Up to 24,000 triangles for the scalp hair, 10,000 for face hair", 1),
    ("high", "High", "Up to 12,000 triangles for the scalp hair, 7,000 for face hair", 0),
    ("medium", "Medium", "Up to 7,000 triangles for the scalp hair, 5,000 for face hair", 2),
    ("low", "Low", "Up to 4,500 triangles for the scalp hair, 3,500 for face hair", 3),
    ("haircap_only", "Haircap", "Only a hair texture on the skin, no cards", 4),
]


def get_haircard_quality_items(self, context):
    """Haircard qualities with their thumbnails, which are loaded after registration."""
    _haircard_quality_items.clear()
    _haircard_quality_items.extend(
        (identifier, name, description, get_hg_icon(f"haircards_{identifier}"), value)
        for identifier, name, description, value in HAIRCARD_QUALITIES
    )
    return _haircard_quality_items


class QualityLevelProps(bpy.types.PropertyGroup):
    """Detail of the meshes of one LOD level, see QualitySettings."""

    _register_priority = 2

    body: EnumProperty(
        name="Body",
        items=[
            ("0", "Original", "Keep the body mesh as it is, about 50,500 triangles", 0),
            ("1", "Lower face", "Reduce the polycount of the face only, about 36,000 triangles", 1),
            ("2", "1/4th", "Reduce the polycount of the whole body to a quarter, about 9,600 triangles", 2),
        ],
        default="0",
    )
    clothing: EnumProperty(
        name="Clothing",
        items=[
            ("original", "Original", "Keep the clothing meshes as they are", 0),
            ("high", "High", "Decimate the clothing to half of the triangles", 1),
            ("medium", "Medium", "Decimate the clothing to a quarter of the triangles", 2),
            ("low", "Low", "Decimate the clothing to a tenth of the triangles", 3),
        ],
        default="high",
    )
    eyes: EnumProperty(
        name="Eyes",
        items=[
            ("original", "Original", "Layered eyes with a transparent cornea, about 10,600 triangles", 0),
            ("high", "High", "Game eyes with a single opaque layer, about 3,600 triangles", 1),
            ("medium", "Medium", "Game eyes with a single opaque layer, about 900 triangles", 2),
            ("low", "Low", "Game eyes with a single opaque layer, about 200 triangles", 3),
        ],
        default="high",
    )
    teeth: EnumProperty(
        name="Teeth",
        items=[
            ("0", "Original", "About 12,400 triangles", 0),
            ("1", "Medium", "About 4,600 triangles", 1),
            ("2", "Low", "About 3,300 triangles", 2),
        ],
        default="1",
    )
    haircards: EnumProperty(name="Hair cards", items=get_haircard_quality_items)
    bones_per_vertex: EnumProperty(
        name="Bones per vertex",
        description="Maximum number of bones that deform a single vertex",
        items=INFLUENCE_LIMITS,
        default="4",
    )


def quality_from_props(props: QualityLevelProps) -> QualitySettings:
    return QualitySettings(
        body=int(props.body),
        clothing=props.clothing,
        eyes=props.eyes,
        teeth=int(props.teeth),
        haircards=props.haircards,
        bones_per_vertex=int(props.bones_per_vertex),
    )


def quality_to_props(props: QualityLevelProps, quality: QualitySettings) -> None:
    props.body = str(quality.body)
    props.clothing = quality.clothing
    props.eyes = quality.eyes
    props.teeth = str(quality.teeth)
    props.haircards = quality.haircards
    props.bones_per_vertex = str(quality.bones_per_vertex)


class MeshProps(bpy.types.PropertyGroup):
    _register_priority = 2

    enabled: BoolProperty(
        name="Optimize Meshes",
        description="Reduce the meshes for the engine, otherwise every mesh"
        " stays as it is, with the layered eyes that only render in Blender",
        default=True,
    )
    remove_hidden_skin: BoolProperty(
        name="Remove skin under clothing",
        description="Delete the parts of the body the clothing hides, which"
        " exporters otherwise keep as the modifiers are not applied",
        default=True,
    )
    remove_clothing_subdiv: BoolProperty(name="Remove clothing subdivision", default=True)
    remove_clothing_solidify: BoolProperty(name="Remove clothing solidify", default=True)
    show_advanced: BoolProperty(name="Advanced", default=False)


class HaircardProps(bpy.types.PropertyGroup):
    _register_priority = 2

    enabled: BoolProperty(
        name="Haircards",
        description="Convert the particle hair to hair cards, which files can carry",
        default=True,
    )


SKELETON_NAMES = [
    ("humanoid", "Humanoid", "Names of Unity Humanoid, the Godot humanoid profile and VRM"),
    ("unreal", "Unreal", "Unreal Engine Mannequin names"),
    ("mixamo", "Mixamo", "Mixamo names, for its animation library and tools"),
    ("humgen", "Human Generator", "Keep the Human Generator bone names"),
    ("custom", "Custom file", "Names from a JSON file like game_rig_presets.json"),
]


class SkeletonProps(bpy.types.PropertyGroup):
    _register_priority = 2

    enabled: BoolProperty(
        name="Skeleton",
        description="Convert the rig to a clean skeleton for game engines, otherwise"
        " the full Human Generator rig is exported",
        default=True,
    )
    names: EnumProperty(name="Names", items=_enum(SKELETON_NAMES), default="humanoid")
    names_file: StringProperty(name="Names file", subtype="FILE_PATH")
    rest_pose: EnumProperty(name="Rest pose", items=REST_POSE_ITEMS, default="t_pose")
    root_bone: BoolProperty(
        name="Root bone",
        description="Add a bone at the origin above the hips, which carries the movement of the character",
        default=True,
    )
    root_bone_name: StringProperty(name="Name", default="Root")
    keep_eyes: BoolProperty(name="Eyes", description="Keep the eye bones, otherwise the eyes follow the head", default=True)
    keep_jaw: BoolProperty(name="Jaw", description="Keep the jaw bones that move the teeth", default=True)
    keep_breasts: BoolProperty(name="Breasts", description="Keep the breast bones", default=True)
    keep_metacarpals: BoolProperty(
        name="Metacarpals",
        description="Keep the palm bones between the hand and the fingers, otherwise their weights go to the hand",
        default=False,
    )
    units: EnumProperty(name="Units", description="Units of the exported FBX file", items=UNIT_ITEMS, default="meters")
    show_advanced: BoolProperty(name="Advanced", default=False)


def _key_group_prop(group: str, default: str):
    """The keep, bake or remove choice for a group of shape keys, see KEY_GROUPS."""
    _, label, description = next(item for item in KEY_GROUPS if item[0] == group)
    allowed = GROUP_ACTIONS.get(group)
    items = [item for item in KEY_ACTIONS if allowed is None or item[0] in allowed]
    return EnumProperty(name=label, description=description, items=items, default=default)


class KeyItemProps(bpy.types.PropertyGroup):
    """A key a user can choose to keep, in the lists of the Shape Keys section."""

    _register_priority = 2

    enabled: BoolProperty(default=True)


def _keep_props() -> Dict[str, Any]:
    """Per group the list of keys to tick, whether the list is open and whether
    it holds a selection of a recipe rather than every key, see `_tick`."""
    props: Dict[str, Any] = {}
    for group, *_ in KEY_GROUPS:
        props[f"items_{group}"] = CollectionProperty(type=KeyItemProps)
        props[f"open_{group}"] = BoolProperty(default=False)
        props[f"explicit_{group}"] = BoolProperty(default=False)
    return props


class ShapeKeyProps(bpy.types.PropertyGroup):
    _register_priority = 3

    __annotations__.update(_keep_props())  # noqa

    enabled: BoolProperty(
        name="Shape Keys",
        description="Keep shape keys on the processed human, otherwise all of"
        " them are removed and the sliders are baked in",
        default=True,
    )
    face_rig: _key_group_prop("face_rig", "keep")
    expressions: _key_group_prop("expressions", "keep")
    correctives: _key_group_prop("correctives", "keep")
    body: _key_group_prop("body", "bake")
    face: _key_group_prop("face", "bake")
    age: _key_group_prop("age", "bake")
    lod0_only: BoolProperty(
        name="Only on LOD0",
        description="Lower levels get no shape keys, their values are baked in",
        default=True,
    )


def _texture_tier_items(self, context):
    return [(ident, label, "", i) for i, (ident, label, _) in enumerate(TEXTURE_TIERS)] + [
        (CUSTOM_TIER[0], CUSTOM_TIER[1], "Changed per texture set", len(TEXTURE_TIERS))
    ]


def _get_texture_tier(self) -> int:
    tier = texture_tier_of(_resolution_from_props(self))
    identifiers = [ident for ident, *_ in TEXTURE_TIERS] + [CUSTOM_TIER[0]]
    return identifiers.index(tier)


def _set_texture_tier(self, value: int) -> None:
    identifiers = [ident for ident, *_ in TEXTURE_TIERS]
    if value >= len(identifiers):
        return
    for set_name, resolution in resolution_of_tier(identifiers[value]).items():
        setattr(self, f"res_{set_name}", str(resolution))


def _resolution_from_props(props) -> Dict[str, int]:  # noqa: ANN001
    return {set_name: int(getattr(props, f"res_{set_name}")) for set_name in TEXTURE_SETS}


RESOLUTION_ITEMS = [(str(r), f"{r} x {r}", "", i) for i, r in enumerate(RESOLUTIONS)]


def _texture_props() -> Dict[str, Any]:
    """Resolution per set and a toggle per pass per set, made in a loop."""
    props: Dict[str, Any] = {}
    for set_name in TEXTURE_SETS:
        props[f"res_{set_name}"] = EnumProperty(
            name=set_name.capitalize(), items=RESOLUTION_ITEMS, default="1024"
        )
        for pass_id, label, description in TEXTURE_PASSES:
            props[f"pass_{set_name}_{pass_id}"] = BoolProperty(
                name=label, description=description, default=False
            )
    return props


class TextureProps(bpy.types.PropertyGroup):
    _register_priority = 2

    __annotations__.update(_texture_props())  # noqa

    enabled: BoolProperty(
        name="Textures",
        description="Bake the materials to textures. Files always need them",
        default=True,
    )
    tier: EnumProperty(
        name="Resolution", items=_texture_tier_items, get=_get_texture_tier, set=_set_texture_tier
    )
    file_format: EnumProperty(name="Format", items=_enum(TEXTURE_FORMATS), default="png")
    workflow: EnumProperty(name="Workflow", items=_enum(TEXTURE_WORKFLOWS), default="separate")
    normal_map: EnumProperty(name="Normal map", items=_enum(NORMAL_MAP_DIRECTIONS), default="opengl")
    pack_hair_alpha: BoolProperty(
        name="Pack hair alpha into color",
        description="Store the transparency of the hair cards in the alpha channel of their color texture, as engines expect",
        default=True,
    )
    samples: EnumProperty(
        name="Samples", items=[("4", "4", "", 0), ("16", "16", "", 1), ("64", "64", "", 2)], default="4"
    )
    show_advanced: BoolProperty(name="Advanced", default=False)


class ClipProps(bpy.types.PropertyGroup):
    """An animation in the clip list: an action on the human or a library preset."""

    _register_priority = 2

    # Action name or preset path, what the settings store
    identifier: StringProperty()
    enabled: BoolProperty(default=True)
    is_hg: BoolProperty(default=False)


class AnimationProps(bpy.types.PropertyGroup):
    _register_priority = 3

    enabled: BoolProperty(name="Animations", description="Export the animations of the human", default=False)
    source: EnumProperty(
        name="Clips", items=_enum(CLIP_SOURCES), default="human", update=lambda self, context: _refresh_clips_of(context)
    )
    clips: CollectionProperty(type=ClipProps)
    clips_open: BoolProperty(default=False)
    # The list holds the selection of a recipe rather than every clip, see _tick
    clips_explicit: BoolProperty(default=False)
    layout: EnumProperty(name="File layout", items=_enum(CLIP_LAYOUTS), default="single_file")
    sample_rate: EnumProperty(
        name="Sample rate",
        description="Frames per second the clips are sampled at in the FBX file, Scene for the frame rate of the scene",
        items=[("0", "Scene", "", 0), ("24", "24", "", 1), ("30", "30", "", 2), ("60", "60", "", 3)],
        default="0",
    )
    root_motion: EnumProperty(name="Root motion", items=_enum(ROOT_MOTION_OPTIONS), default="hips")
    show_advanced: BoolProperty(name="Advanced", default=False)


class ScriptArgProps(bpy.types.PropertyGroup):
    _register_priority = 1

    type: EnumProperty(  # noqa: A003
        items=[("str", "String", "", 0), ("int", "Integer", "", 1), ("float", "Float", "", 2), ("bool", "Boolean", "", 3)]
    )
    value_str: StringProperty()
    value_int: IntProperty(min=-1000000, max=1000000)
    value_float: bpy.props.FloatProperty(min=-1000000, max=1000000)
    value_bool: BoolProperty()

    def draw_prop(self, layout) -> None:  # noqa: ANN001
        layout.prop(self, f"value_{self.type}", text=self.name)

    @property
    def value(self) -> Any:
        return getattr(self, f"value_{self.type}")

    @value.setter
    def value(self, value: Any) -> None:
        setattr(self, f"value_{self.type}", script_tools.ARG_TYPES[self.type](value))


class ScriptProps(bpy.types.PropertyGroup):
    """A script in the list, see ScriptSettings."""

    _register_priority = 2

    path: StringProperty()
    description: StringProperty()
    stage: EnumProperty(name="Stage", items=_enum(SCRIPT_STAGES), default="after_processing")
    on_error: EnumProperty(name="On error", items=_enum(SCRIPT_ERROR_POLICIES), default="stop")
    args: CollectionProperty(type=ScriptArgProps)
    takes_files: BoolProperty(default=False)
    menu_open: BoolProperty(default=True)


class ScriptsProps(bpy.types.PropertyGroup):
    _register_priority = 3

    enabled: BoolProperty(
        name="Scripts",
        description="Run the scripts of the list at their stage of the process",
        default=False,
    )
    items: CollectionProperty(type=ScriptProps)


class FbxProps(bpy.types.PropertyGroup):
    _register_priority = 2

    axis_forward: EnumProperty(name="Forward", items=_enum(FBX_AXES), default="-Z")
    axis_up: EnumProperty(name="Up", items=_enum(FBX_AXES), default="Y")
    primary_bone_axis: EnumProperty(name="Primary bone axis", items=_enum(FBX_AXES), default="Y")
    secondary_bone_axis: EnumProperty(name="Secondary bone axis", items=_enum(FBX_AXES), default="X")
    leaf_bones: BoolProperty(name="Leaf bones", description="Add bones at the end of every chain, engines see them as extra bones", default=False)
    custom_properties: BoolProperty(name="Custom properties", default=False)
    triangulate: BoolProperty(name="Triangulate", default=False)
    smoothing: EnumProperty(name="Smoothing", items=_enum(FBX_SMOOTHING), default="FACE")


class GltfProps(bpy.types.PropertyGroup):
    _register_priority = 2

    tangents: BoolProperty(name="Tangents", default=False)
    image_format: EnumProperty(name="Images", items=_enum(GLTF_IMAGE_FORMATS), default="AUTO")
    draco: BoolProperty(name="Draco compression", default=False)


def _make_path_absolute(self, prop_name: str) -> None:  # noqa: ANN001
    current_path = self[prop_name]
    if current_path.startswith("//"):
        self[prop_name] = os.path.abspath(bpy.path.abspath(current_path))


class OutputProps(bpy.types.PropertyGroup):
    _register_priority = 3

    format: EnumProperty(name="Output", items=_enum(OUTPUT_FORMATS), default="fbx")  # noqa: A003
    folder: StringProperty(
        name="Folder",
        subtype="DIR_PATH",
        description="Where the files go, the export folder of the content folder when empty",
        update=lambda self, _: _make_path_absolute(self, "folder"),
    )
    name: StringProperty(
        name="Name",
        description="Name of the files and prefix of every object, material and texture. {name} is the name of the human",
        default="{name}",
    )
    naming: EnumProperty(name="Naming", items=_enum(NAMING_SCHEMES), default="plain")
    template_rig: StringProperty(name="Rig", default="{name}")
    template_mesh: StringProperty(name="Mesh", default="{name}_{part}")
    template_material: StringProperty(name="Material", default="{name}_{part}")
    template_texture: StringProperty(name="Texture", default="{name}_{part}_{pass}")
    textures: EnumProperty(name="Textures", items=_enum(TEXTURE_PLACEMENTS), default="folder")
    keep_copy: BoolProperty(
        name="Keep copy in this file",
        description="Keep the processed human in this file after writing it",
        default=False,
    )
    fbx: PointerProperty(type=FbxProps)
    gltf: PointerProperty(type=GltfProps)
    show_advanced: BoolProperty(name="Advanced", default=False)


def get_recipe_items(self, context):
    """Shipped recipes and the ones of the user, grouped."""
    _recipe_enum_items.clear()
    previous_group = None
    index = 0
    try:
        items = recipe_items()
    except OSError as e:
        hg_log(f"Could not list recipes: {e}", level="WARNING")
        items = []
    modified = self.loaded_recipe if context and is_modified(self) else None
    for identifier, label, group in items:
        if group != previous_group:
            _recipe_enum_items.append(("", group, ""))
            previous_group = group
        if identifier == modified:
            label += " (modified)"
        _recipe_enum_items.append((identifier, label, "", index))
        index += 1
    return _recipe_enum_items


def _load_recipe(self, context) -> None:
    """Loads the chosen recipe into the properties."""
    if _loading or not self.recipe:
        return
    try:
        settings = ExportSettings.from_recipe(self.recipe)
    except (OSError, ValueError) as e:
        hg_log(f"Could not load recipe {self.recipe}: {e}", level="WARNING")
        return
    settings_to_props(self, settings)


def _set_lod_count(self, context) -> None:
    """Adds or removes LOD levels to match the count."""
    if _loading:
        return
    while len(self.lods) < self.lod_count:
        previous = self.lods[-1] if self.lods else None
        level = self.lods.add()
        if previous:
            tier = NEXT_TIERS.get(tier_of(quality_from_props(previous)), "low")
            quality_to_props(level, quality_of_tier(tier))
        else:
            quality_to_props(level, quality_of_tier("high"))
    while len(self.lods) > max(self.lod_count, 1):
        self.lods.remove(len(self.lods) - 1)


def get_script_items(self, context):
    """The scripts of the content folder and the shipped ones, for the add menu."""
    _script_enum_items.clear()
    for index, path in enumerate(script_tools.available_scripts()):
        _script_enum_items.append((path, os.path.basename(path), path, index))
    return _script_enum_items


def add_script(props: "ProcessProps", path: str) -> bool:
    """Adds a script to the list, with its arguments, and turns the scripts on.

    Returns:
        bool: False if the script could not be read, which is logged.
    """
    try:
        info = script_tools.inspect_script(path)
    except script_tools.ScriptError as e:
        hg_log(str(e), level="WARNING")
        return False
    item = props.scripts.items.add()
    item.name = info.name
    item.path = path
    item.description = info.description
    item.takes_files = info.takes_files
    if info.stage:
        item.stage = info.stage
    elif info.takes_files:
        item.stage = "after_export"
    for arg in info.args:
        arg_item = item.args.add()
        arg_item.name = arg.name
        arg_item.type = arg.type
        if arg.default is not None:
            arg_item.value = arg.default
    props.scripts.enabled = True
    return True


class ProcessProps(bpy.types.PropertyGroup):
    _register_priority = 4

    recipe: EnumProperty(name="Recipe", items=get_recipe_items, update=_load_recipe)
    # The recipe the properties were loaded from, and its settings as JSON to
    # see whether anything was changed since
    loaded_recipe: StringProperty()
    loaded_json: StringProperty()

    lod_count: IntProperty(
        name="LOD levels",
        description="Number of levels of detail, each a reduced copy of the character",
        min=1,
        max=MAX_LOD_LEVELS,
        default=1,
        update=_set_lod_count,
    )
    lods: CollectionProperty(type=QualityLevelProps)
    meshes: PointerProperty(type=MeshProps)
    haircards: PointerProperty(type=HaircardProps)
    skeleton: PointerProperty(type=SkeletonProps)
    shape_keys: PointerProperty(type=ShapeKeyProps)
    textures: PointerProperty(type=TextureProps)
    animations: PointerProperty(type=AnimationProps)
    scripts: PointerProperty(type=ScriptsProps)
    output: PointerProperty(type=OutputProps)

    human_list_isopen: BoolProperty(default=False)


def ensure_initialized(props: ProcessProps) -> None:
    """Loads the first recipe when the scene has no process settings yet."""
    if props.lods:
        return
    items = get_recipe_items(props, None)
    first = next((ident for ident, *_ in items if ident), None)
    if first:
        props.recipe = first
    else:
        settings_to_props(props, ExportSettings())


def props_to_settings(props: ProcessProps) -> ExportSettings:  # noqa: CCR001
    """The settings the properties describe."""
    output_props = props.output
    output = OutputSettings(
        format=output_props.format,
        folder=output_props.folder,
        name=output_props.name,
        naming=output_props.naming,
        naming_templates={
            "rig": output_props.template_rig,
            "mesh": output_props.template_mesh,
            "material": output_props.template_material,
            "texture": output_props.template_texture,
        },
        textures=output_props.textures,
        keep_copy=output_props.keep_copy,
        fbx=FbxSettings(
            axis_forward=output_props.fbx.axis_forward,
            axis_up=output_props.fbx.axis_up,
            primary_bone_axis=output_props.fbx.primary_bone_axis,
            secondary_bone_axis=output_props.fbx.secondary_bone_axis,
            leaf_bones=output_props.fbx.leaf_bones,
            custom_properties=output_props.fbx.custom_properties,
            triangulate=output_props.fbx.triangulate,
            smoothing=output_props.fbx.smoothing,
        ),
        gltf=GltfSettings(
            tangents=output_props.gltf.tangents,
            image_format=output_props.gltf.image_format,
            draco=output_props.gltf.draco,
        ),
    )
    skeleton_props = props.skeleton
    skeleton = SkeletonSettings(
        enabled=skeleton_props.enabled,
        names=skeleton_props.names,
        names_file=bpy.path.abspath(skeleton_props.names_file) if skeleton_props.names_file else "",
        rest_pose=skeleton_props.rest_pose,
        root_bone=skeleton_props.root_bone,
        root_bone_name=skeleton_props.root_bone_name,
        keep_eyes=skeleton_props.keep_eyes,
        keep_jaw=skeleton_props.keep_jaw,
        keep_breasts=skeleton_props.keep_breasts,
        keep_metacarpals=skeleton_props.keep_metacarpals,
        units=skeleton_props.units,
    )
    keys_props = props.shape_keys
    shape_keys = ShapeKeySettings(
        enabled=keys_props.enabled,
        face_rig=keys_props.face_rig,
        expressions=keys_props.expressions,
        correctives=keys_props.correctives,
        body=keys_props.body,
        face=keys_props.face,
        age=keys_props.age,
        # A list with everything ticked means all, so the recipe fits any human
        keep={
            group: selection
            for group, *_ in KEY_GROUPS
            if (
                selection := _ticked(
                    getattr(keys_props, f"items_{group}"),
                    explicit=getattr(keys_props, f"explicit_{group}"),
                )
            )
            is not None
        },
        lod0_only=keys_props.lod0_only,
    )
    tex_props = props.textures
    textures = TextureBakeSettings(
        enabled=tex_props.enabled,
        resolution=_resolution_from_props(tex_props),
        passes={
            set_name: [
                pass_id
                for pass_id, *_ in TEXTURE_PASSES
                if getattr(tex_props, f"pass_{set_name}_{pass_id}")
            ]
            for set_name in TEXTURE_SETS
        },
        file_format=tex_props.file_format,
        workflow=tex_props.workflow,
        normal_map=tex_props.normal_map,
        pack_hair_alpha=tex_props.pack_hair_alpha,
        samples=int(tex_props.samples),
    )
    anim_props = props.animations
    animations = AnimationClipSettings(
        enabled=anim_props.enabled,
        source=anim_props.source,
        clips=_ticked(anim_props.clips, "identifier", anim_props.clips_explicit),
        layout=anim_props.layout,
        sample_rate=int(anim_props.sample_rate),
        root_motion=anim_props.root_motion,
    )
    scripts = ScriptsSettings(
        enabled=props.scripts.enabled,
        items=[
            ScriptSettings(
                path=item.path,
                stage=item.stage,
                args={arg.name: arg.value for arg in item.args},
                on_error=item.on_error,
            )
            for item in props.scripts.items
        ],
    )
    return ExportSettings(
        recipe=props.loaded_recipe,
        output=output,
        lods=[quality_from_props(level) for level in props.lods] or [QualitySettings()],
        meshes=MeshSettings(
            enabled=props.meshes.enabled,
            remove_hidden_skin=props.meshes.remove_hidden_skin,
            remove_clothing_subdiv=props.meshes.remove_clothing_subdiv,
            remove_clothing_solidify=props.meshes.remove_clothing_solidify,
        ),
        haircards=HaircardSettings(enabled=props.haircards.enabled),
        skeleton=skeleton,
        shape_keys=shape_keys,
        textures=textures,
        animations=animations,
        scripts=scripts,
    )


def settings_to_props(props: ProcessProps, settings: ExportSettings) -> None:  # noqa: CCR001
    """Puts the settings in the properties, as loading a recipe does."""
    global _loading
    _loading = True
    try:
        _settings_to_props(props, settings)
    finally:
        _loading = False


def _settings_to_props(props: ProcessProps, settings: ExportSettings) -> None:  # noqa: CCR001
    output, output_props = settings.output, props.output
    output_props.format = output.format
    output_props.folder = output.folder
    output_props.name = output.name
    output_props.naming = output.naming
    output_props.template_rig = output.naming_templates.get("rig", "{name}")
    output_props.template_mesh = output.naming_templates.get("mesh", "{name}_{part}")
    output_props.template_material = output.naming_templates.get("material", "{name}_{part}")
    output_props.template_texture = output.naming_templates.get("texture", "{name}_{part}_{pass}")
    output_props.textures = output.textures
    output_props.keep_copy = output.keep_copy
    for name in ("axis_forward", "axis_up", "primary_bone_axis", "secondary_bone_axis", "leaf_bones", "custom_properties", "triangulate", "smoothing"):
        setattr(output_props.fbx, name, getattr(output.fbx, name))
    for name in ("tangents", "image_format", "draco"):
        setattr(output_props.gltf, name, getattr(output.gltf, name))

    props.lods.clear()
    for quality in settings.lods or [QualitySettings()]:
        quality_to_props(props.lods.add(), quality)
    props.lod_count = len(props.lods)

    for name in ("enabled", "remove_hidden_skin", "remove_clothing_subdiv", "remove_clothing_solidify"):
        setattr(props.meshes, name, getattr(settings.meshes, name))
    props.haircards.enabled = settings.haircards.enabled
    for name in ("enabled", "names", "names_file", "rest_pose", "root_bone", "root_bone_name", "keep_eyes", "keep_jaw", "keep_breasts", "keep_metacarpals", "units"):
        setattr(props.skeleton, name, getattr(settings.skeleton, name))
    for name in ("enabled", "face_rig", "expressions", "correctives", "body", "face", "age", "lod0_only"):
        setattr(props.shape_keys, name, getattr(settings.shape_keys, name))
    for group, *_ in KEY_GROUPS:
        selection = settings.shape_keys.keep.get(group)
        _tick(getattr(props.shape_keys, f"items_{group}"), selection)
        setattr(props.shape_keys, f"explicit_{group}", selection is not None)

    textures, tex_props = settings.textures, props.textures
    tex_props.enabled = textures.enabled
    for set_name in TEXTURE_SETS:
        resolution = textures.resolution.get(set_name, 1024)
        setattr(tex_props, f"res_{set_name}", str(min(RESOLUTIONS, key=lambda r: abs(r - resolution))))
        passes = textures.passes.get(set_name, [])
        for pass_id, *_ in TEXTURE_PASSES:
            setattr(tex_props, f"pass_{set_name}_{pass_id}", pass_id in passes)
    tex_props.file_format = textures.file_format
    tex_props.workflow = textures.workflow
    tex_props.normal_map = textures.normal_map
    tex_props.pack_hair_alpha = textures.pack_hair_alpha
    tex_props.samples = str(textures.samples) if str(textures.samples) in ("4", "16", "64") else "4"

    animations, anim_props = settings.animations, props.animations
    anim_props.enabled = animations.enabled
    anim_props.source = animations.source
    _tick(anim_props.clips, animations.clips, "identifier")
    anim_props.clips_explicit = animations.clips is not None
    anim_props.layout = animations.layout
    anim_props.sample_rate = str(animations.sample_rate) if str(animations.sample_rate) in ("0", "24", "30", "60") else "0"
    anim_props.root_motion = animations.root_motion

    props.scripts.enabled = settings.scripts.enabled
    props.scripts.items.clear()
    for script in settings.scripts.items:
        item = props.scripts.items.add()
        item.name = os.path.splitext(os.path.basename(script.path))[0]
        item.path = script.path
        item.stage = script.stage
        item.on_error = script.on_error
        try:
            info = script_tools.inspect_script(script.path)
        except script_tools.ScriptError as e:
            item.description = str(e)
            continue
        item.description = info.description
        item.takes_files = info.takes_files
        for arg in info.args:
            arg_item = item.args.add()
            arg_item.name = arg.name
            arg_item.type = arg.type
            value = script.args.get(arg.name, arg.default)
            if value is not None:
                arg_item.value = value

    props.loaded_recipe = settings.recipe
    props.loaded_json = settings.to_json()
    if settings.recipe and props.recipe != settings.recipe:
        try:
            props.recipe = settings.recipe
        except TypeError:
            pass


def _ticked(items, attribute: str = "name", explicit: bool = False) -> Optional[List[str]]:  # noqa: ANN001
    """The ticked entries of a list, None when every entry is ticked.

    An explicit list holds the selection of a recipe and not every entry, so
    it is a selection even when all of it is ticked, or when it is empty.
    """
    if not explicit and all(item.enabled for item in items):
        return None
    return [getattr(item, attribute) for item in items if item.enabled]


def _tick(items, selection: Optional[List[str]], attribute: str = "name") -> None:  # noqa: ANN001
    """Ticks the entries of a selection, every entry for None.

    Selected entries that are not listed yet are added, so a recipe loaded
    before the lists are filled keeps its selection. The list is then explicit
    until it is refreshed, see `_ticked`.
    """
    if selection is None:
        for item in items:
            item.enabled = True
        return
    listed = {getattr(item, attribute) for item in items}
    for name in selection:
        if name not in listed:
            item = items.add()
            item.name = name
            setattr(item, attribute, name)
    for item in items:
        item.enabled = getattr(item, attribute) in selection


def select_list(items, select: bool) -> None:  # noqa: ANN001
    """Ticks or unticks every entry of a list."""
    for item in items:
        item.enabled = select


def is_modified(props: ProcessProps) -> bool:
    """Whether the properties differ from the recipe they were loaded from."""
    if not props.loaded_json:
        return False
    try:
        loaded = ExportSettings.from_json(props.loaded_json)
    except ValueError:
        return False
    return props_to_settings(props).differs_from(loaded)


def _refresh_clips_of(context) -> None:  # noqa: ANN001
    from HumGen3D.human.human import Human

    if _loading or not context:
        return
    human = Human.from_existing(context.object, strict_check=False)
    if human:
        refresh_clips(context.scene.HG3D.process, human, context)


def refresh_clips(props: ProcessProps, human, context) -> None:  # noqa: ANN001
    """Fills the clip list: the actions on the human or the clips of the library."""
    from HumGen3D.human.process.animations import clip_names, library_clips

    anim_props = props.animations
    enabled = _refreshed_ticks(anim_props.clips, "identifier", anim_props.clips_explicit)
    anim_props.clips_explicit = False
    anim_props.clips.clear()
    if anim_props.source == "library":
        entries = [(name, preset, True) for preset, name in library_clips(human, context)]
    else:
        entries = [(name, name, is_hg) for name, is_hg in clip_names(human)]
    for name, identifier, is_hg in entries:
        clip = anim_props.clips.add()
        clip.name = name
        clip.identifier = identifier
        clip.is_hg = is_hg
        clip.enabled = enabled(identifier)


def refresh_key_lists(props: ProcessProps, human, context) -> None:  # noqa: ANN001
    """Fills the lists of keys to keep, per group, for this human."""
    keys_props = props.shape_keys
    for group, names in keep_options(human, context).items():
        items = getattr(keys_props, f"items_{group}")
        enabled = _refreshed_ticks(items, "name", getattr(keys_props, f"explicit_{group}"))
        setattr(keys_props, f"explicit_{group}", False)
        items.clear()
        for name in names:
            item = items.add()
            item.name = name
            item.enabled = enabled(name)


def _refreshed_ticks(items, attribute: str, explicit: bool):  # noqa: ANN001, ANN202
    """Whether an entry of a refreshed list is ticked, by its identifier.

    Entries keep their tick. New entries are ticked, unless the list held the
    selection of a recipe, which they are not part of.
    """
    ticks = {getattr(item, attribute): item.enabled for item in items}
    return lambda identifier: ticks.get(identifier, not explicit)
