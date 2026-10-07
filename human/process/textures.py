# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Bakes the materials of a processed human to textures for other programs.

The skin, hair and eye materials are node trees exporters can't read, so every
material is baked to images and replaced by a plain Principled BSDF with image
nodes. The maps are written the way the chosen engine expects them: roughness
and metallic packed into one image for Unreal (ORM), Unity (metallic in RGB,
smoothness in A) or glTF, the normal map with a flipped green channel for
DirectX engines, and the alpha of the hair cards inside their color texture.

The materials in Blender get the same packed images, through Separate Color
nodes, so the processed copy renders in Blender and the glTF exporter finds the
channels.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import bpy
import numpy as np
from HumGen3D.backend.logging import hg_log
from HumGen3D.common.context import context_override
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.progress import Steps
from HumGen3D.human.hair.compatibility import SPECULAR_INPUT_NAME

from .game_eyes import ROUGHNESS as GAME_EYE_ROUGHNESS
from .naming import Namer, material_part, part_names
from .settings import TextureSettings

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

# Principled BSDF input of each pass
PASS_INPUTS = {
    "base_color": "Base Color",
    "roughness": "Roughness",
    "metallic": "Metallic",
    "alpha": "Alpha",
}
# Passes that are packed into one image per workflow, with the channel of each
PACKED_PASSES = {
    "orm": ("orm", {"occlusion": 0, "roughness": 1, "metallic": 2}),
    "metallic_roughness": (
        "metallic_roughness",
        {"occlusion": 0, "roughness": 1, "metallic": 2},
    ),
    "metallic_smoothness": ("metallic_smoothness", {"metallic": 0, "smoothness": 3}),
}
# Position of the image nodes in the baked material
NODE_LOCATIONS = {
    "base_color": (-700, 400),
    "normal": (-700, -300),
    "roughness": (-700, 100),
    "metallic": (-1100, 200),
    "alpha": (-1100, -100),
    "packed": (-1100, 100),
}
HAIRCARD_KEY = "hg_haircard"


@dataclass
class TextureSet:
    """One material of the human that gets its own textures."""

    obj: bpy.types.Object
    slot: int
    set_name: str  # body, clothing, eyes, teeth, hair
    part: str  # Part name for the file names, see naming.py
    passes: List[str]
    resolution: int
    # Baked images per pass, a float for passes whose input is a plain value
    baked: Dict[str, object] = field(default_factory=dict)

    @property
    def material(self) -> bpy.types.Material:
        return self.obj.material_slots[self.slot].material  # type:ignore[index]


def plan_texture_sets(human: "Human", settings: TextureSettings) -> List[TextureSet]:
    """Which materials get baked, with their passes and resolution.

    Args:
        human (Human): The processed copy.
        settings (TextureSettings): Passes and resolution per texture set.

    Returns:
        List[TextureSet]: The body, the eyes, the teeth, every clothing object
            and every hair card object, in that order.
    """
    objects = human.objects
    parts = part_names(human)
    sets: List[TextureSet] = []

    planned = set()

    def add(obj: bpy.types.Object, slot: int, set_name: str) -> None:
        if slot >= len(obj.material_slots) or not obj.material_slots[slot].material:
            return
        # A material shared by parts, like the one of the teeth, is baked once
        material = obj.material_slots[slot].material
        if material in planned:
            return
        planned.add(material)
        part = material_part(human, obj, slot, parts.get(obj, "Part"))
        sets.append(
            TextureSet(
                obj,
                slot,
                set_name,
                part,
                list(settings.passes.get(set_name, ["base_color"])),
                int(settings.resolution.get(set_name, 1024)),
            )
        )

    add(objects.body, 0, "body")
    add(objects.eyes, human.materials.eye_inner_slot, "eyes")
    add(objects.upper_teeth, 0, "teeth")
    add(objects.lower_teeth, 0, "teeth")
    for cloth_obj in human.clothing.outfit.objects + human.clothing.footwear.objects:
        add(cloth_obj, 0, "clothing")
    for hair_obj in objects.haircards:
        add(hair_obj, 0, "hair")
        add(hair_obj, 1, "hair")
    return sets


def count_bakes(sets: List[TextureSet]) -> int:
    """Number of bake passes, for progress estimates."""
    return sum(len(texture_set.passes) for texture_set in sets)


def bake_steps(  # noqa: CCR001
    human: "Human",
    settings: TextureSettings,
    namer: Namer,
    folder: Optional[str],
    context: bpy.types.Context,
    only_sets: Optional[Tuple[str, ...]] = None,
    per_level: bool = False,
) -> Steps[List[bpy.types.Image]]:
    """Bakes every material of the human and replaces it, in resumable steps.

    See `HumGen3D.common.progress`. Yields after every baked pass.

    Args:
        human (Human): The processed copy, its materials must not be shared
            with the original human.
        settings (TextureSettings): What to bake and how to pack it.
        namer (Namer): Names of the images and materials.
        folder (Optional[str]): Folder to write the images to, None keeps them
            packed in the blend file.
        context (bpy.types.Context): Blender context.
        only_sets (Optional[Tuple[str, ...]]): Bake only these texture sets,
            for LOD levels that share the other textures with the first level.
        per_level (bool): Name the images and materials for this level only,
            see Namer.

    Returns:
        List[bpy.types.Image]: The images of the new materials.
    """
    sets = plan_texture_sets(human, settings)
    if only_sets is not None:
        sets = [texture_set for texture_set in sets if texture_set.set_name in only_sets]
    if folder:
        os.makedirs(folder, exist_ok=True)

    with _render_settings(context, settings.samples):
        for texture_set in sets:
            was_solidified = _hide_solidify(texture_set.obj)
            try:
                for pass_id in texture_set.passes:
                    texture_set.baked[pass_id] = _bake_pass(
                        texture_set, pass_id, context
                    )
                    yield 0.0
            finally:
                _show_solidify(texture_set.obj, was_solidified)

    images = []
    for texture_set in sets:
        images.extend(_build_material(human, texture_set, settings, namer, folder, per_level))
    for texture_set in sets:
        for image in texture_set.baked.values():
            if isinstance(image, bpy.types.Image) and image.users == 0:
                bpy.data.images.remove(image)
    human.objects.rig["hg_baked"] = True
    return images


class _render_settings:
    """Cycles with few samples for the bakes, the scene settings restored after."""

    def __init__(self, context: bpy.types.Context, samples: int) -> None:
        self.context = context
        self.samples = samples

    def __enter__(self) -> None:
        scene = self.context.scene
        cycles_addon = self.context.preferences.addons["cycles"]  # type:ignore[index]
        self.device = cycles_addon.preferences.compute_device_type
        self.engine = scene.render.engine
        self.old_samples = scene.cycles.samples
        self.use_denoising = scene.cycles.use_denoising
        # OptiX can't bake
        if self.device == "OPTIX":
            cycles_addon.preferences.compute_device_type = "CUDA"
        scene.render.engine = "CYCLES"
        scene.cycles.samples = self.samples
        scene.cycles.use_denoising = False

    def __exit__(self, *_: object) -> None:
        scene = self.context.scene
        cycles_addon = self.context.preferences.addons["cycles"]  # type:ignore[index]
        cycles_addon.preferences.compute_device_type = self.device
        scene.cycles.samples = self.old_samples
        scene.cycles.use_denoising = self.use_denoising
        try:
            scene.render.engine = self.engine
        except TypeError:
            hg_log(f"Could not restore render engine {self.engine}", level="WARNING")


def _hide_solidify(obj: bpy.types.Object) -> List[bpy.types.Modifier]:
    """Hides the solidify modifiers, which would bake the inside of the cloth."""
    hidden = []
    for mod in obj.modifiers:
        if mod.type == "SOLIDIFY" and (mod.show_viewport or mod.show_render):
            hidden.append(mod)
            mod.show_viewport = mod.show_render = False
    return hidden


def _show_solidify(obj: bpy.types.Object, modifiers: List[bpy.types.Modifier]) -> None:
    for mod in modifiers:
        mod.show_viewport = mod.show_render = True


def _principled(material: bpy.types.Material) -> bpy.types.ShaderNode:
    node = next(
        (n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"),
        None,
    )
    if node is None:
        raise HumGenException(f"Material {material.name} has no Principled BSDF to bake")
    return node


def _input_source(
    principled: bpy.types.ShaderNode, pass_id: str
) -> Tuple[Optional[bpy.types.NodeSocket], float]:
    """The socket linked to the input of a pass, or its plain value."""
    name = PASS_INPUTS[pass_id]
    if pass_id == "specular":
        name = SPECULAR_INPUT_NAME
    socket = principled.inputs[name]  # type:ignore[index]
    if socket.links:
        return socket.links[0].from_socket, 0.0
    value = socket.default_value
    return None, float(value if not hasattr(value, "__len__") else value[0])


def _bake_pass(  # noqa: CCR001
    texture_set: TextureSet, pass_id: str, context: bpy.types.Context
) -> object:
    """Bakes one pass of a material to a new image.

    A pass whose input is a plain value is not baked, the value is returned.
    The material is changed for the bake and not restored: it is replaced by
    the baked material afterwards.
    """
    material = texture_set.material
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    principled = _principled(material)
    output = next(n for n in nodes if n.bl_idname == "ShaderNodeOutputMaterial")

    if pass_id == "normal":
        links.new(principled.outputs[0], output.inputs[0])  # type:ignore[index]
        bake_type = "NORMAL"
    else:
        source, value = _input_source(principled, pass_id)
        if source is None:
            return value
        emission = nodes.new("ShaderNodeEmission")
        links.new(source, emission.inputs[0])  # type:ignore[index]
        links.new(emission.outputs[0], output.inputs[0])  # type:ignore[index]
        bake_type = "EMIT"

    is_color = pass_id == "base_color"
    image = bpy.data.images.new(
        f"hg_bake_{texture_set.part}_{pass_id}",
        width=texture_set.resolution,
        height=texture_set.resolution,
        alpha=False,
        float_buffer=not is_color,
    )
    if not is_color:
        image.colorspace_settings.name = "Non-Color"
    target = nodes.new("ShaderNodeTexImage")
    target.image = image
    for node in nodes:
        node.select = False
    target.select = True
    nodes.active = target

    obj = texture_set.obj
    with context_override(context, obj, [obj]):
        hidden = obj.hide_get()
        obj.hide_set(False)
        try:
            bpy.ops.object.bake(type=bake_type)  # type:ignore[misc, arg-type]
        finally:
            obj.hide_set(hidden)
    return image


def _pixels(image: bpy.types.Image) -> np.ndarray:
    pixels = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(pixels)
    return pixels.reshape(-1, 4)


def _channel(source: object, size: int, invert: bool = False) -> np.ndarray:
    """One channel of a baked pass as array, a plain value fills the channel."""
    if isinstance(source, bpy.types.Image):
        values = _pixels(source)[:, 0]
    else:
        values = np.full(size * size, float(source), dtype=np.float32)  # type:ignore[arg-type]
    return 1.0 - values if invert else values


def _new_image(
    name: str, size: int, pixels: np.ndarray, color: bool, alpha: bool
) -> bpy.types.Image:
    image = bpy.data.images.new(name, size, size, alpha=alpha)
    if not color:
        image.colorspace_settings.name = "Non-Color"
    image.pixels.foreach_set(pixels.ravel())
    if alpha:
        # Prevents Blender from multiplying the color with the alpha
        image.alpha_mode = "CHANNEL_PACKED"
    return image


def _save(image: bpy.types.Image, folder: Optional[str], file_format: str) -> None:
    if folder:
        extension = "jpg" if file_format == "jpeg" else "png"
        image.filepath_raw = os.path.join(folder, f"{image.name}.{extension}")
        image.file_format = file_format.upper()
        image.save()
        image.reload()
    else:
        image.pack()


def _build_material(  # noqa: CCR001
    human: "Human",
    texture_set: TextureSet,
    settings: TextureSettings,
    namer: Namer,
    folder: Optional[str],
    per_level: bool = False,
) -> List[bpy.types.Image]:
    """Writes the final images of a texture set and puts them in a new material."""
    size = texture_set.resolution
    baked = texture_set.baked
    part = texture_set.part
    is_hair = HAIRCARD_KEY in texture_set.obj
    images: Dict[str, bpy.types.Image] = {}
    constants: Dict[str, float] = {}

    base = baked.get("base_color")
    alpha = baked.get("alpha")
    if isinstance(base, bpy.types.Image):
        pixels = _pixels(base)
        pack_alpha = (
            is_hair
            and settings.pack_hair_alpha
            and settings.file_format != "jpeg"
            and alpha is not None
        )
        if pack_alpha:
            pixels[:, 3] = _channel(alpha, size)
        images["base_color"] = _new_image(
            namer.texture(part, "base_color", per_level), size, pixels, True, pack_alpha
        )
    if isinstance(alpha, bpy.types.Image) and "base_color" not in images:
        images["alpha"] = _new_image(
            namer.texture(part, "alpha", per_level), size, _pixels(alpha), False, False
        )
    elif isinstance(alpha, bpy.types.Image) and not images["base_color"].alpha_mode == "CHANNEL_PACKED":
        images["alpha"] = _new_image(
            namer.texture(part, "alpha", per_level), size, _pixels(alpha), False, False
        )

    normal = baked.get("normal")
    if isinstance(normal, bpy.types.Image):
        pixels = _pixels(normal)
        if settings.normal_map == "directx":
            pixels[:, 1] = 1.0 - pixels[:, 1]
        images["normal"] = _new_image(
            namer.texture(part, "normal", per_level), size, pixels, False, False
        )

    roughness = baked.get("roughness")
    metallic = baked.get("metallic")
    workflow = settings.workflow
    if workflow in PACKED_PASSES and (roughness is not None or metallic is not None):
        pass_id, channels = PACKED_PASSES[workflow]
        pixels = np.ones((size * size, 4), dtype=np.float32)
        sources = {
            "occlusion": 1.0,
            "roughness": roughness if roughness is not None else 0.5,
            "metallic": metallic if metallic is not None else 0.0,
        }
        if workflow == "metallic_smoothness":
            metal = _channel(sources["metallic"], size)
            pixels[:, 0] = pixels[:, 1] = pixels[:, 2] = metal
            pixels[:, 3] = _channel(sources["roughness"], size, invert=True)
        else:
            for channel_name, index in channels.items():
                pixels[:, index] = _channel(sources[channel_name], size)
        images[pass_id] = _new_image(
            namer.texture(part, pass_id, per_level), size, pixels, False, workflow == "metallic_smoothness"
        )
    else:
        for pass_id, source in (("roughness", roughness), ("metallic", metallic)):
            if isinstance(source, bpy.types.Image):
                images[pass_id] = _new_image(
                    namer.texture(part, pass_id, per_level), size, _pixels(source), False, False
                )
            elif source is not None:
                constants[pass_id] = float(source)  # type:ignore[arg-type]

    for image in images.values():
        _save(image, folder, settings.file_format)

    material = bpy.data.materials.new(namer.material(part, per_level))
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    principled = nodes["Principled BSDF"]  # type:ignore[index]
    for pass_id, value in constants.items():
        principled.inputs[PASS_INPUTS[pass_id]].default_value = value  # type:ignore[index]
    if texture_set.obj == human.objects.eyes and human.process.has_game_eyes:
        principled.inputs["Roughness"].default_value = GAME_EYE_ROUGHNESS  # type:ignore[index]

    for pass_id, image in images.items():
        node = nodes.new("ShaderNodeTexImage")
        node.image = image
        node.name = node.label = pass_id
        node.location = NODE_LOCATIONS.get(pass_id, NODE_LOCATIONS["packed"])
        if pass_id == "base_color":
            links.new(node.outputs["Color"], principled.inputs["Base Color"])  # type:ignore[index]
            if image.alpha_mode == "CHANNEL_PACKED":
                links.new(node.outputs["Alpha"], principled.inputs["Alpha"])  # type:ignore[index]
        elif pass_id == "normal":
            normal_node = nodes.new("ShaderNodeNormalMap")
            normal_node.location = (-350, -300)
            if settings.normal_map == "directx":
                # Flip the green channel back, so Blender shows it right
                _link_directx_normal(nodes, links, node, normal_node)
            else:
                links.new(node.outputs["Color"], normal_node.inputs["Color"])  # type:ignore[index]
            links.new(normal_node.outputs["Normal"], principled.inputs["Normal"])  # type:ignore[index]
        elif pass_id in ("roughness", "metallic", "alpha"):
            links.new(node.outputs["Color"], principled.inputs[PASS_INPUTS[pass_id]])  # type:ignore[index]
        else:
            _link_packed(nodes, links, node, principled, workflow)

    if any(image.alpha_mode == "CHANNEL_PACKED" for image in images.values()) or "alpha" in images:
        if bpy.app.version < (4, 3, 0):
            material.blend_method = "BLEND"
            material.shadow_method = "CLIP"
        else:
            material.surface_render_method = "BLENDED"

    old = texture_set.material
    texture_set.obj.material_slots[texture_set.slot].material = material  # type:ignore[index]
    if old.users == 0:
        bpy.data.materials.remove(old)
    return list(images.values())


def _link_directx_normal(nodes, links, image_node, normal_node) -> None:  # noqa: ANN001
    separate = nodes.new("ShaderNodeSeparateColor")
    separate.location = (-550, -300)
    invert = nodes.new("ShaderNodeMath")
    invert.operation = "SUBTRACT"
    invert.inputs[0].default_value = 1.0  # type:ignore[index]
    invert.location = (-450, -400)
    combine = nodes.new("ShaderNodeCombineColor")
    combine.location = (-350, -450)
    links.new(image_node.outputs["Color"], separate.inputs["Color"])  # type:ignore[index]
    links.new(separate.outputs["Red"], combine.inputs["Red"])  # type:ignore[index]
    links.new(separate.outputs["Green"], invert.inputs[1])  # type:ignore[index]
    links.new(invert.outputs[0], combine.inputs["Green"])  # type:ignore[index]
    links.new(separate.outputs["Blue"], combine.inputs["Blue"])  # type:ignore[index]
    links.new(combine.outputs["Color"], normal_node.inputs["Color"])  # type:ignore[index]


def _link_packed(nodes, links, image_node, principled, workflow: str) -> None:  # noqa: ANN001
    """Wires a packed roughness/metallic image to the Principled BSDF."""
    separate = nodes.new("ShaderNodeSeparateColor")
    separate.location = (-800, 100)
    links.new(image_node.outputs["Color"], separate.inputs["Color"])  # type:ignore[index]
    if workflow == "metallic_smoothness":
        links.new(separate.outputs["Red"], principled.inputs["Metallic"])  # type:ignore[index]
        invert = nodes.new("ShaderNodeMath")
        invert.operation = "SUBTRACT"
        invert.inputs[0].default_value = 1.0  # type:ignore[index]
        invert.location = (-600, 0)
        links.new(image_node.outputs["Alpha"], invert.inputs[1])  # type:ignore[index]
        links.new(invert.outputs[0], principled.inputs["Roughness"])  # type:ignore[index]
    else:
        links.new(separate.outputs["Green"], principled.inputs["Roughness"])  # type:ignore[index]
        links.new(separate.outputs["Blue"], principled.inputs["Metallic"])  # type:ignore[index]


def copy_materials(human: "Human") -> None:
    """Gives the human its own copy of every material, so baking and renaming
    can't reach the human it was duplicated from."""
    copies: Dict[bpy.types.Material, bpy.types.Material] = {}
    for obj in human.objects:
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            material = slot.material
            if not material:
                continue
            if material not in copies:
                copies[material] = material.copy()
            slot.material = copies[material]


def is_baked(human: "Human") -> bool:
    """Whether the materials of the human were baked by the process system."""
    return "hg_baked" in human.objects.rig


def share_textures(source: "Human", target: "Human") -> None:
    """Gives the materials of one processed human to another, per part.

    LOD levels share their textures: the meshes keep their UV layout when they
    are reduced, so the images baked for the first level fit every level. Hair
    cards and eyes are the exception, their UVs differ per quality.

    Args:
        source (Human): Human with baked materials.
        target (Human): Human to assign the materials to.
    """
    source_parts = {part: obj for obj, part in part_names(source).items()}
    for obj, part in part_names(target).items():
        if HAIRCARD_KEY in obj or obj == target.objects.eyes:
            continue
        source_obj = source_parts.get(part)
        if not source_obj:
            continue
        for slot_index, slot in enumerate(obj.material_slots):
            if slot_index < len(source_obj.material_slots):
                slot.material = source_obj.material_slots[slot_index].material
