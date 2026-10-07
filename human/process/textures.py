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
channels. A map whose inputs are all plain values is not written, the values go
on the Principled BSDF instead. The caps of the hair, eyebrows and eyelashes
are cut from one atlas, so they are baked into one set of images and get one
material, see naming.SHARED_CAP_TAGS.

Every bake call starts a Cycles session, which costs more than the pixels do,
so a pass is baked for all materials in one call: Blender writes every selected
object into the active image node of each of its materials. The passes are
emission bakes of the inputs (and a normal bake), which need no other geometry,
so everything but the baked objects is hidden from the render meanwhile.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Tuple

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

# Order the passes are baked in, see planned_passes
PASS_ORDER = ("normal", "base_color", "roughness", "metallic", "alpha")
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
# Set on the rig once the materials are baked
BAKED_KEY = "hg_baked"


@dataclass
class TextureSet:
    """The materials of the human that get one set of textures.

    Usually one material. The caps of the hair, eyebrows and eyelashes are
    one set of several materials: they share an atlas without overlapping, so
    they are baked into the same images and get one material.
    """

    obj: bpy.types.Object
    slot: int
    set_name: str  # body, clothing, eyes, teeth, hair
    part: str  # Part name for the file names, see naming.py
    passes: List[str]
    resolution: int
    # Further (object, slot) pairs baked into the same images
    others: List[Tuple[bpy.types.Object, int]] = field(default_factory=list)
    # Baked images per pass, a float for passes whose input is a plain value
    baked: Dict[str, object] = field(default_factory=dict)

    @property
    def material(self) -> bpy.types.Material:
        return self.obj.material_slots[self.slot].material  # type:ignore[index]

    @property
    def slots(self) -> List[Tuple[bpy.types.Object, int]]:
        return [(self.obj, self.slot)] + self.others

    @property
    def objects(self) -> List[bpy.types.Object]:
        return list(dict.fromkeys(obj for obj, _ in self.slots))

    @property
    def materials(self) -> List[bpy.types.Material]:
        return list(
            dict.fromkeys(obj.material_slots[slot].material for obj, slot in self.slots)
        )


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
        shared = next((s for s in sets if s.set_name == set_name and s.part == part), None)
        if shared:
            shared.others.append((obj, slot))
            return
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


def planned_passes(sets: List[TextureSet]) -> List[str]:
    """The passes any of the sets needs, in bake order.

    The normal pass comes first: it bakes the materials as they are, the
    emission passes rewire them.
    """
    wanted = {pass_id for texture_set in sets for pass_id in texture_set.passes}
    return [pass_id for pass_id in PASS_ORDER if pass_id in wanted]


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

    See `HumGen3D.common.progress`. Yields after every baked pass, which is
    one bake call for all materials.

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

    objects = list(dict.fromkeys(obj for texture_set in sets for obj in texture_set.objects))
    passes = planned_passes(sets)
    with _render_settings(context, settings.samples), _bake_visibility(context, objects):
        was_solidified = _hide_solidify(objects)
        try:
            for index, pass_id in enumerate(passes):
                targets: Dict[bpy.types.Material, bpy.types.Image] = {}
                for texture_set in sets:
                    if pass_id not in texture_set.passes:
                        continue
                    baked = _prepare_pass(texture_set, pass_id)
                    texture_set.baked[pass_id] = baked
                    if isinstance(baked, bpy.types.Image):
                        for material in texture_set.materials:
                            targets[material] = baked
                _bake(objects, targets, pass_id, context)
                yield (index + 1) / len(passes)
        finally:
            _show_solidify(was_solidified)

    images = []
    for texture_set in sets:
        images.extend(_build_material(human, texture_set, settings, namer, folder, per_level))
    for texture_set in sets:
        for image in texture_set.baked.values():
            if isinstance(image, bpy.types.Image) and image.users == 0:
                bpy.data.images.remove(image)
    human.objects.rig[BAKED_KEY] = True
    return images


class _render_settings:
    """Cycles on the CPU with few samples for the bakes, the scene settings
    restored after.

    The bakes are many short sessions, and a GPU session loads its kernels
    every time: on the GPU the same bakes take two to three times as long.
    """

    def __init__(self, context: bpy.types.Context, samples: int) -> None:
        self.context = context
        self.samples = samples

    def __enter__(self) -> None:
        scene = self.context.scene
        self.engine = scene.render.engine
        self.device = scene.cycles.device
        self.old_samples = scene.cycles.samples
        self.use_denoising = scene.cycles.use_denoising
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = self.samples
        scene.cycles.use_denoising = False

    def __exit__(self, *_: object) -> None:
        scene = self.context.scene
        scene.cycles.device = self.device
        scene.cycles.samples = self.old_samples
        scene.cycles.use_denoising = self.use_denoising
        try:
            scene.render.engine = self.engine
        except TypeError:
            hg_log(f"Could not restore render engine {self.engine}", level="WARNING")


class _bake_visibility:
    """Only the baked objects render while the block runs.

    Emission and normal bakes need no other geometry, and Cycles syncs the
    whole scene for every bake call: the particle hair of the human the copy
    was made from alone costs seconds per call.
    """

    def __init__(self, context: bpy.types.Context, objects: List[bpy.types.Object]) -> None:
        self.context = context
        self.objects = set(objects)
        self.render_hidden: List[Tuple[bpy.types.Object, bool]] = []
        self.particles: List[bpy.types.Modifier] = []

    def __enter__(self) -> None:
        for obj in self.context.scene.objects:
            baked = obj in self.objects
            if obj.hide_render == baked:
                self.render_hidden.append((obj, obj.hide_render))
                obj.hide_render = not baked
        for obj in self.objects:
            for mod in obj.modifiers:
                if mod.type == "PARTICLE_SYSTEM" and mod.show_render:
                    self.particles.append(mod)
                    mod.show_render = False

    def __exit__(self, *_: object) -> None:
        for obj, hidden in self.render_hidden:
            obj.hide_render = hidden
        for mod in self.particles:
            mod.show_render = True


def _hide_solidify(objects: List[bpy.types.Object]) -> List[bpy.types.Modifier]:
    """Hides the solidify modifiers, which would bake the inside of the cloth."""
    hidden = []
    for obj in objects:
        for mod in obj.modifiers:
            if mod.type == "SOLIDIFY" and (mod.show_viewport or mod.show_render):
                hidden.append(mod)
                mod.show_viewport = mod.show_render = False
    return hidden


def _show_solidify(modifiers: List[bpy.types.Modifier]) -> None:
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


def _prepare_pass(texture_set: TextureSet, pass_id: str) -> object:
    """Readies the materials of a set for the bake of one pass: a new target
    image, active in every node tree, with the input of the pass wired to the
    output.

    A pass whose input is a plain value in every material gets no image, the
    value is returned. The materials are changed for the bake and not
    restored: they are replaced by the baked material afterwards.
    """
    materials = texture_set.materials
    if pass_id != "normal":
        sources = [_input_source(_principled(material), pass_id) for material in materials]
        if all(source is None for source, _ in sources):
            return sources[0][1]

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

    for index, material in enumerate(materials):
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        output = next(n for n in nodes if n.bl_idname == "ShaderNodeOutputMaterial")
        if pass_id == "normal":
            links.new(_principled(material).outputs[0], output.inputs[0])  # type:ignore[index]
        else:
            # A plain value in one material of a shared set is baked as well,
            # so the shared image is complete
            source, value = sources[index]
            emission = nodes.new("ShaderNodeEmission")
            if source is not None:
                links.new(source, emission.inputs[0])  # type:ignore[index]
            else:
                emission.inputs[0].default_value = (value, value, value, 1.0)  # type:ignore[index]
            links.new(emission.outputs[0], output.inputs[0])  # type:ignore[index]
        target = nodes.new("ShaderNodeTexImage")
        target.image = image
        for node in nodes:
            node.select = False
        target.select = True
        nodes.active = target
    return image


def _bake(
    objects: List[bpy.types.Object],
    targets: Dict[bpy.types.Material, bpy.types.Image],
    pass_id: str,
    context: bpy.types.Context,
) -> None:
    """Bakes one pass of every target material.

    Blender writes each material of a baked object into its active image node;
    materials on the object without a target get no active node, which Blender
    skips. Every object is a Cycles session of its own and a session uploads
    the textures of every visible material, so an object is baked with only
    itself visible: the skin textures are not loaded for the eyes. Objects
    that share a target image are baked in one call, which clears the image
    once and writes every object into it.
    """
    baked = [
        obj
        for obj in objects
        if any(slot.material in targets for slot in obj.material_slots)
    ]
    if not baked:
        return
    for obj in baked:
        for slot in obj.material_slots:
            material = slot.material
            if material and material not in targets and material.node_tree:
                material.node_tree.nodes.active = None
    bake_type = "NORMAL" if pass_id == "normal" else "EMIT"
    hidden = [obj for obj in baked if obj.hide_get()]
    for obj in hidden:
        obj.hide_set(False)
    try:
        for group in _sharing_groups(baked, targets):
            for other in objects:
                other.hide_render = other not in group
            with context_override(context, group[0], group):
                bpy.ops.object.bake(type=bake_type)  # type:ignore[misc, arg-type]
    finally:
        for obj in objects:
            obj.hide_render = False
        for obj in hidden:
            obj.hide_set(True)


def _sharing_groups(
    objects: List[bpy.types.Object], targets: Dict[bpy.types.Material, bpy.types.Image]
) -> List[List[bpy.types.Object]]:
    """The objects grouped by the target images they share, in their order."""
    groups: List[List[bpy.types.Object]] = []
    images_of: List[set] = []
    for obj in objects:
        images = {
            targets[slot.material] for slot in obj.material_slots if slot.material in targets
        }
        for group, group_images in zip(groups, images_of):
            if images & group_images:
                group.append(obj)
                group_images |= images
                break
        else:
            groups.append([obj])
            images_of.append(images)
    return groups


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
    # A packed map of plain values only is not worth a file, the values go on
    # the material like in the separate workflow
    has_map = any(isinstance(source, bpy.types.Image) for source in (roughness, metallic))
    if workflow in PACKED_PASSES and has_map:
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

    # A material shared by parts, like the one of the teeth, was baked once for
    # all of them; the materials of a shared set all become the one material
    olds = texture_set.materials
    for obj in human.objects:
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            if slot.material in olds:
                slot.material = material
    for old in olds:
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


def copy_materials(
    human: "Human", objects: Optional[Iterable[bpy.types.Object]] = None
) -> None:
    """Gives the human its own copy of every material, so baking and renaming
    can't reach the human it was duplicated from.

    Materials that nothing outside this human uses are kept, so this can run
    more than once without leaving orphan copies behind.

    Args:
        human (Human): The human to give its own materials.
        objects (Optional[Iterable[Object]]): Only the materials of these
            objects of the human, all of them when None.
    """
    slots: Dict[bpy.types.Material, List[bpy.types.MaterialSlot]] = {}
    for obj in objects if objects is not None else human.objects:
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            if slot.material:
                slots.setdefault(slot.material, []).append(slot)
    for material, own_slots in slots.items():
        outside_users = material.users - int(material.use_fake_user) - len(own_slots)
        if outside_users <= 0:
            continue
        copy = material.copy()
        for slot in own_slots:
            slot.material = copy


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
