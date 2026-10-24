# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Bakes the materials of a processed human to textures for other programs.

The skin, hair and eye materials are node trees exporters can't read, so every
material is baked to images and replaced by a plain Principled BSDF with image
nodes. The maps are written the way the chosen engine expects them: roughness
and metallic packed into one image for Unreal (ORM), Unity (metallic in RGB,
smoothness in A) or glTF, the normal map with a flipped green channel for
DirectX engines, and the alpha of the hair cards inside their color texture.
The hair cards also get a flow map (see FLOW_PASS), which no material of the
baked copy reads: it is for the hair shaders of the Companions.

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

import math
import os
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Tuple

import bpy
import numpy as np
from ...backend.logging import hg_log
from ...common.context import context_override
from ...common.exceptions import HumGenException
from ...common.progress import Steps
from ...human.hair.compatibility import SPECULAR_INPUT_NAME
from ...human.hair.haircards import remove_blender_look

from . import haircap_skin
from .game_eyes import ROUGHNESS as GAME_EYE_ROUGHNESS
from .naming import Namer, material_part, part_names
from .settings import TextureBakeSettings

if TYPE_CHECKING:
    from ...human.human import Human

# Order the passes are baked in, see planned_passes
PASS_ORDER = ("normal", "base_color", "roughness", "metallic", "alpha", "specular", "flow")
# The flow map of the hair cards: the direction of the strands in the UV space
# of the card from root to tip (red and green, around 0.5) and a random value
# per strand (blue). It is baked from the flow image of the generated card
# atlas, see card_atlas, and read by no Principled input: the engines' hair
# shaders use it for the anisotropic highlights and the variation between
# strands. The baked material keeps it in an unlinked image node, so an
# export with embedded textures can write it next to the file
FLOW_PASS = "flow"
# Principled BSDF input of each pass
PASS_INPUTS = {
    "base_color": "Base Color",
    "roughness": "Roughness",
    "metallic": "Metallic",
    "alpha": "Alpha",
    "specular": SPECULAR_INPUT_NAME,
}
# Passes every set gets besides the ones of the settings. The specular has
# no map in the engines, so it becomes one value on the baked material: the
# plain value of the materials, or the average of a small bake of it. Without
# it the baked material falls back to 0.5, and flat hair cards with that
# reflect the lights as grey.
IMPLICIT_PASSES = ("specular",)
# Resolution of the bake that is only averaged
SAMPLE_SIZE = 128
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
    "flow": (-700, -650),
}
HAIRCARD_KEY = "hg_haircard"
# The number Blender adds to a name that is taken
SUFFIX = re.compile(r"\.\d{3}$")
# Set on the rig once the materials are baked, and on the baked materials
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
    # The alpha pass is the strand coverage of the hair card atlas, see
    # _atlas_image, and needs the atlas's own encoding back
    atlas_alpha: bool = False

    @property
    def is_hair(self) -> bool:
        """Hair cards or the caps under them, textured by a strand atlas."""
        return HAIRCARD_KEY in self.obj

    @property
    def is_cards(self) -> bool:
        """Hair cards, which engines cut out; the caps are blended."""
        return self.is_hair and self.part.endswith("Cards")

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


def plan_texture_sets(human: "Human", settings: TextureBakeSettings) -> List[TextureSet]:
    """Which materials get baked, with their passes and resolution.

    Args:
        human (Human): The processed copy.
        settings (TextureBakeSettings): Passes and resolution per texture set.

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
        passes = list(settings.passes.get(set_name, ["base_color"]))
        passes.extend(p for p in IMPLICIT_PASSES if p not in passes)
        sets.append(
            TextureSet(
                obj,
                slot,
                set_name,
                part,
                passes,
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
    settings: TextureBakeSettings,
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
        settings (TextureBakeSettings): What to bake and how to pack it.
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
    # The caps that go into the skin are baked first, then mixed over the
    # skin material before its bake, see haircap_skin.py
    cap_sets = [s for s in sets if settings.haircap_in_skin and haircap_skin.has_skin_caps(s)]
    body_set = next((s for s in sets if s.set_name == "body"), None)
    if cap_sets and body_set:
        phases = [cap_sets, [s for s in sets if s not in cap_sets]]
    else:
        phases = [sets]
    total = sum(len(planned_passes(phase)) for phase in phases)
    done = 0
    cap_images: List[bpy.types.Image] = []
    with _render_settings(context, settings.samples), _bake_visibility(context, objects):
        was_solidified = _hide_solidify(objects)
        try:
            for phase_index, phase in enumerate(phases):
                if phase_index == 1:
                    cap_images = haircap_skin.paint_into_skin(human, body_set, cap_sets)  # type:ignore[arg-type]
                for pass_id in planned_passes(phase):
                    _bake_pass(phase, objects, pass_id, context)
                    done += 1
                    yield done / total
        finally:
            _show_solidify(was_solidified)
            haircap_skin.remove_uv_layers(human)

    images = []
    for texture_set in sets:
        if settings.haircap_in_skin and haircap_skin.only_skin_caps(texture_set):
            continue
        images.extend(_build_material(human, texture_set, settings, namer, folder, per_level))
    if settings.haircap_in_skin:
        haircap_skin.remove_caps(human)
    for texture_set in sets:
        for image in texture_set.baked.values():
            if isinstance(image, bpy.types.Image) and image.users == 0:
                bpy.data.images.remove(image)
    for image in cap_images:
        if image.users == 0:
            bpy.data.images.remove(image)
    human.objects.rig[BAKED_KEY] = True
    _SNAPSHOTS.clear()
    return images


def _bake_pass(
    sets: List[TextureSet],
    objects: List[bpy.types.Object],
    pass_id: str,
    context: bpy.types.Context,
) -> None:
    """Bakes one pass of the sets that have it, in one bake call per object."""
    targets: Dict[bpy.types.Material, bpy.types.Image] = {}
    for texture_set in sets:
        if pass_id not in texture_set.passes:
            continue
        baked = _prepare_pass(texture_set, pass_id)
        texture_set.baked[pass_id] = baked
        if isinstance(baked, bpy.types.Image):
            for material in texture_set.materials:
                targets[material] = baked
    if pass_id == "normal":
        with _card_face_normals(sets):
            _bake(objects, targets, pass_id, context)
    else:
        _bake(objects, targets, pass_id, context)
    for texture_set in sets:
        baked = texture_set.baked.get(pass_id)
        if isinstance(baked, bpy.types.Image):
            _snapshot(baked, channels=SNAPSHOT_CHANNELS.get(pass_id, 4))


# Transparent bounces of the bakes: Blender's default, so the textures do not
# depend on the scene. Converting hair to cards raises them for rendering, see
# render.set_cycles_transparent_bounces, which changed the skin normals
BAKE_TRANSPARENT_BOUNCES = 8


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
        self.use_clear = scene.render.bake.use_clear
        self.transparent_bounces = scene.cycles.transparent_max_bounces
        scene.render.engine = "CYCLES"
        scene.cycles.transparent_max_bounces = BAKE_TRANSPARENT_BOUNCES
        scene.cycles.device = "CPU"
        scene.cycles.samples = self.samples
        scene.cycles.use_denoising = False
        # Texels outside the UV islands stay clear, see _average
        scene.render.bake.use_clear = True

    def __exit__(self, *_: object) -> None:
        scene = self.context.scene
        scene.cycles.device = self.device
        scene.cycles.samples = self.old_samples
        scene.cycles.use_denoising = self.use_denoising
        scene.render.bake.use_clear = self.use_clear
        scene.cycles.transparent_max_bounces = self.transparent_bounces
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


class _card_face_normals:
    """The hair cards have the normals of their faces while the block runs.

    The normals of the cards follow the shape of the head, so a card that
    stands on the head or crosses another one has them in its own plane. A
    tangent space bake can't express a normal relative to such a card: it
    baked noise into the parts of the atlas those cards use, which lit them
    and every card that shares their part dark in engines. With the normals
    of the faces the bake writes the normals of the atlas as they are,
    relative to the card, which is how the Companions apply them.
    """

    def __init__(self, sets: List[TextureSet]) -> None:
        self.slots = [
            slot for texture_set in sets if texture_set.is_cards for slot in texture_set.slots
        ]
        # Mesh, its normals per face corner and its sharp edges
        self.original: List[Tuple[bpy.types.Mesh, np.ndarray, np.ndarray]] = []

    def __enter__(self) -> None:
        for obj, slot in self.slots:
            mesh = obj.data
            loop_count = len(mesh.loops)  # type:ignore[union-attr]
            if not loop_count:
                continue
            normals = np.empty(loop_count * 3, dtype=np.float32)
            if hasattr(mesh, "corner_normals"):
                mesh.corner_normals.foreach_get("vector", normals)  # type:ignore[union-attr]
            else:
                mesh.calc_normals_split()  # type:ignore[union-attr]
                mesh.loops.foreach_get("normal", normals)  # type:ignore[union-attr]
            normals = normals.reshape(-1, 3)
            polygon_count = len(mesh.polygons)  # type:ignore[union-attr]
            face_normals = np.empty(polygon_count * 3, dtype=np.float32)
            mesh.polygons.foreach_get("normal", face_normals)  # type:ignore[union-attr]
            material_index = np.empty(polygon_count, dtype=np.int32)
            mesh.polygons.foreach_get("material_index", material_index)  # type:ignore[union-attr]
            loop_total = np.empty(polygon_count, dtype=np.int32)
            mesh.polygons.foreach_get("loop_total", loop_total)  # type:ignore[union-attr]
            loop_start = np.empty(polygon_count, dtype=np.int32)
            mesh.polygons.foreach_get("loop_start", loop_start)  # type:ignore[union-attr]

            polygon_of_loop = np.empty(loop_count, dtype=np.int64)
            polygon_of_loop[np.concatenate([np.arange(s, s + t) for s, t in zip(loop_start, loop_total)])] = (
                np.repeat(np.arange(polygon_count), loop_total)
            )
            of_slot = material_index[polygon_of_loop] == slot
            flat = normals.copy()
            flat[of_slot] = face_normals.reshape(-1, 3)[polygon_of_loop[of_slot]]
            # Setting normals marks the edges sharp that need it to keep them
            sharp = np.empty(len(mesh.edges), dtype=bool)  # type:ignore[union-attr]
            mesh.edges.foreach_get("use_edge_sharp", sharp)  # type:ignore[union-attr]
            self.original.append((mesh, normals, sharp))  # type:ignore[arg-type]
            mesh.normals_split_custom_set(flat.tolist())  # type:ignore[union-attr]

    def __exit__(self, *_: object) -> None:
        for mesh, normals, sharp in self.original:
            mesh.edges.foreach_set("use_edge_sharp", sharp)
            mesh.normals_split_custom_set(normals.tolist())
            mesh.update()
        self.original.clear()


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
    socket = principled.inputs[PASS_INPUTS[pass_id]]  # type:ignore[index]
    if socket.links:
        return socket.links[0].from_socket, 0.0
    value = socket.default_value
    return None, float(value if not hasattr(value, "__len__") else value[0])


# Passes of the hair cards that are baked from the atlas textures of their
# material rather than from the Principled inputs, see _card_source
CARD_ATLAS_PASSES = ("alpha", "roughness", FLOW_PASS)
# Roughness of a hair card texel between the strands, and how much the
# strand specular map of the atlas lowers it on a strand: the Principled
# roughness of the cards is one value, and cut-out cards lit with one
# roughness reflect like plastic. More than 0.15 gave dark hair white
# streaks in engines, a flat card has none of the strand's curvature to
# spread a sharp highlight
CARD_ROUGHNESS = 0.55
CARD_STRAND_GLOSS = 0.15
# Name part of the atlas image that feeds each pass
CARD_ATLAS_IMAGES = {"alpha": "_ALPHA", "roughness": "_SPECULAR", FLOW_PASS: "_FLOW"}
# Passes of the hair that are baked at the size of the strand texture of the
# material and scaled down after, see _prepare_pass. Cycles samples a texture
# once per baked texel, so a 4096 strand texture baked into 1024 texels
# aliased: a strand's normal landed on a random side of the strand, which
# lit half of the texels of the caps from the back, and a strand thinner
# than a texel was lost from the alpha
NATIVE_PASSES = ("alpha", "normal", FLOW_PASS)
# Largest native bake, the atlas of the library is 4096
MAX_NATIVE_SIZE = 4096
# Baked (sRGB encoded) alpha at and above which a hair card texel is solid,
# so that every strand the hair material draws at a fifth of full opacity or
# more is in at the half alpha engines cut out at. Below it the alpha fades to
# zero as drawn. The parts of the atlas the cards use are drawn sparse on
# purpose (a tenth of the texels of the short and fine parts is strand), so
# the cut-out needs every strand; 0.6 lost half of them and the hair looked
# thin next to Blender's translucent cards.
ALPHA_SOLID = 0.2
# Share of the width of a card over which its alpha fades out at each side.
# The parts of the atlas a card uses are cut through strands at their sides,
# which showed as straight edges along every card in a cut-out
CARD_EDGE_FADE = 0.15


def _material_images(material: bpy.types.Material) -> List[bpy.types.Image]:
    """The images of a material's nodes and of the groups in it."""
    images = []
    trees = [material.node_tree]
    for node in material.node_tree.nodes:
        if node.bl_idname == "ShaderNodeGroup" and node.node_tree:
            trees.append(node.node_tree)
    for tree in trees:
        for node in tree.nodes:
            image = getattr(node, "image", None)
            if image is not None and image not in images:
                images.append(image)
    return images


def _atlas_image(
    material: bpy.types.Material, name_part: str
) -> Optional[bpy.types.Image]:
    """An atlas texture of a hair card material, found by name inside its group."""
    for node in material.node_tree.nodes:
        if node.bl_idname != "ShaderNodeGroup" or not node.node_tree:
            continue
        for inner in node.node_tree.nodes:
            image = getattr(inner, "image", None)
            if image is not None and name_part in image.name:
                return image
    return None


def _native_size(texture_set: TextureSet, size: int) -> Optional[int]:
    """The size to bake a native pass of a hair set at, see NATIVE_PASSES:
    that of the largest strand texture of its materials, when it is a whole
    multiple of the texture size and larger."""
    largest = 0
    for material in texture_set.materials:
        for image in _material_images(material):
            largest = max(largest, int(image.size[0]))
    native = min(largest, MAX_NATIVE_SIZE)
    if native > size and native % size == 0:
        return native
    return None


def _card_source(
    material: bpy.types.Material,
    pass_id: str,
    fallback: Tuple[Optional[bpy.types.NodeSocket], float],
) -> Tuple[Optional[bpy.types.NodeSocket], float]:
    """The socket to bake a pass of hair cards from.

    The strands of the card atlas are drawn to full alpha, and the card
    material scales that down to a fraction, so stacked cards read as
    translucent in Cycles. Engines cut cards out, and a cut-out of
    translucent strands is blobby up close and gone at a distance, so the
    alpha is baked from the atlas itself: full strands with anti-aliased
    edges, cut out at the half alpha every engine defaults to. The roughness
    comes from the strand specular map of the atlas, so every strand
    reflects on its own. A material without the atlas keeps its inputs.
    """
    image = _atlas_image(material, CARD_ATLAS_IMAGES[pass_id])
    if image is None:
        return fallback
    nodes = material.node_tree.nodes
    atlas = nodes.new("ShaderNodeTexImage")
    atlas.image = image
    atlas.label = f"atlas_{pass_id}"
    if pass_id in ("alpha", FLOW_PASS):
        return atlas.outputs["Color"], 0.0  # type:ignore[return-value]
    gloss = nodes.new("ShaderNodeMath")
    gloss.operation = "MULTIPLY_ADD"
    gloss.inputs[1].default_value = -CARD_STRAND_GLOSS  # type:ignore[index]
    gloss.inputs[2].default_value = CARD_ROUGHNESS  # type:ignore[index]
    material.node_tree.links.new(atlas.outputs["Color"], gloss.inputs[0])  # type:ignore[index]
    return gloss.outputs[0], 0.0  # type:ignore[return-value]


def _prepare_pass(texture_set: TextureSet, pass_id: str) -> object:
    """Readies the materials of a set for the bake of one pass: a new target
    image, active in every node tree, with the input of the pass wired to the
    output.

    A pass whose input is a plain value in every material gets no image, the
    value is returned. The materials are changed for the bake and not
    restored: they are replaced by the baked material afterwards.
    """
    materials = texture_set.materials
    for material in materials:
        # The look of hair cards in Blender is no part of the textures
        remove_blender_look(material)
    if pass_id == FLOW_PASS:
        # No Principled input: only cards with a generated atlas have it
        sources = [(None, 0.0) for _ in materials]
    elif pass_id != "normal":
        sources = [_input_source(_principled(material), pass_id) for material in materials]
    if pass_id != "normal":
        if texture_set.is_cards and pass_id in CARD_ATLAS_PASSES:
            sources = [
                _card_source(material, pass_id, source)
                for material, source in zip(materials, sources)
            ]
            if pass_id == "alpha":
                texture_set.atlas_alpha = (
                    _atlas_image(texture_set.material, CARD_ATLAS_IMAGES["alpha"]) is not None
                )
        if all(source is None for source, _ in sources):
            return sources[0][1]

    is_color = pass_id == "base_color"
    sampled = pass_id in IMPLICIT_PASSES
    size = SAMPLE_SIZE if sampled else texture_set.resolution
    # Scaled down after the bake, see _alpha_channel and _normal_pixels
    native = _native_size(texture_set, size) if pass_id in NATIVE_PASSES and texture_set.is_hair else None
    if native:
        size = native
    image = bpy.data.images.new(
        f"hg_bake_{texture_set.part}_{pass_id}",
        width=size,
        height=size,
        # The alpha of a sampled pass tells which texels the bake reached
        alpha=sampled,
        # Eight bits are enough for a native bake, which is scaled down
        float_buffer=not is_color and not native,
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
            # One call per object: a bake call only writes the active object,
            # so the caps of the eyebrows and eyelashes were missing from the
            # image they share with the scalp cap. The image is cleared once.
            for index, obj in enumerate(group):
                with context_override(context, obj, [obj]):
                    bpy.ops.object.bake(  # type:ignore[misc, arg-type]
                        type=bake_type, use_clear=index == 0
                    )
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


# The pixels of every baked image right after its pass, by image name. A
# later bake session resets the buffer of an image that one of its materials
# still references to the state after its first bake call, which lost the
# eyebrows and eyelashes from the cap image they share with the scalp cap.
_SNAPSHOTS: Dict[str, np.ndarray] = {}
# Channels a snapshot keeps per pass: the native passes of the hair are
# baked at up to 4096 px, see NATIVE_PASSES
SNAPSHOT_CHANNELS = {"alpha": 1, "normal": 3, FLOW_PASS: 3}


def _snapshot(image: bpy.types.Image, channels: int = 4) -> None:
    """Keeps the first channels of the pixels of a baked image."""
    pixels = _read_pixels(image)
    _SNAPSHOTS[image.name] = pixels[:, :channels].copy() if channels < 4 else pixels


def _read_pixels(image: bpy.types.Image) -> np.ndarray:
    pixels = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(pixels)
    return pixels.reshape(-1, 4)


def _pixels(image: bpy.types.Image) -> np.ndarray:
    """The pixels of a baked image as they were right after its pass."""
    snapshot = _SNAPSHOTS.get(image.name)
    return snapshot.copy() if snapshot is not None else _read_pixels(image)


def _channel(source: object, size: int, invert: bool = False) -> np.ndarray:
    """One channel of a baked pass as array, a plain value fills the channel."""
    if isinstance(source, bpy.types.Image):
        values = _pixels(source)[:, 0]
    else:
        values = np.full(size * size, float(source), dtype=np.float32)  # type:ignore[arg-type]
    return 1.0 - values if invert else values


def _box_down(values: np.ndarray, factor: int) -> np.ndarray:
    """Scales a (rows, cols, ...) array down by a whole factor, averaging."""
    rows, cols = values.shape[:2]
    shape = (rows // factor, factor, cols // factor, factor) + values.shape[2:]
    return values.reshape(shape).mean(axis=(1, 3)).astype(np.float32)


def _alpha_channel(texture_set: TextureSet, size: int) -> np.ndarray:
    """The baked alpha of a set at the texture size.

    A native bake (see NATIVE_PASSES) is scaled down: the alpha of a cap by
    averaging, the atlas coverage of cards with the strand coverage kept, see
    _downsample_coverage. The atlas alpha is a color image, so Cycles bakes
    its values decoded to linear, which thins every anti-aliased strand edge;
    the mask was drawn in the stored values, those are what the cut-out should
    see, with the strands made solid from ALPHA_SOLID up.
    """
    alpha = _channel(texture_set.baked["alpha"], size)
    native = int(round(math.sqrt(alpha.size)))
    alpha = alpha.reshape(native, native)
    if not texture_set.atlas_alpha:
        if native > size:
            alpha = _box_down(alpha, native // size)
        return alpha.ravel()
    atlas = _atlas_image(texture_set.material, CARD_ATLAS_IMAGES["alpha"])
    if atlas is not None and atlas.colorspace_settings.name != "Non-Color":
        linear = np.clip(alpha, 0.0, 1.0)
        alpha = np.where(
            linear <= 0.0031308,
            linear * 12.92,
            1.055 * np.power(linear, 1.0 / 2.4) - 0.055,
        ).astype(np.float32)
    alpha = np.minimum(alpha / ALPHA_SOLID, 1.0).astype(np.float32)
    alpha *= _card_edge_fade(texture_set, native)
    if native > size:
        rects = _card_rects(texture_set.obj, texture_set.slot)
        alpha = _downsample_coverage(alpha, native // size, rects)
    return alpha.ravel()


def _normal_pixels(texture_set: TextureSet, size: int) -> np.ndarray:
    """The baked normal of a set as (size * size, 4) pixels.

    A native bake is scaled down by averaging the normals, weighted by the
    alpha baked at the same size when the set has one: the normal of a strand
    edge is that of the strand, not of the gap next to it, and a texel
    between strands is flat. Without that the gaps, which the bake fills with
    whatever the atlas has there, pulled every edge normal over.
    """
    pixels = _pixels(texture_set.baked["normal"])  # type:ignore[arg-type]
    native = int(round(math.sqrt(len(pixels))))
    rgb = pixels[:, :3]
    if native > size:
        factor = native // size
        vectors = rgb.reshape(native, native, 3) * 2.0 - 1.0
        alpha = texture_set.baked.get("alpha")
        if isinstance(alpha, bpy.types.Image) and alpha.size[0] == native:
            weight = np.clip(_pixels(alpha)[:, 0].reshape(native, native, 1), 0.0, 1.0)
            vectors = _box_down(vectors * weight, factor)
            total = _box_down(weight, factor)
            flat = total < 1e-4
            vectors[flat[..., 0]] = (0.0, 0.0, 1.0)
        else:
            vectors = _box_down(vectors, factor)
        length = np.linalg.norm(vectors, axis=2, keepdims=True)
        rgb = (vectors / np.maximum(length, 1e-6) * 0.5 + 0.5).reshape(-1, 3)
    out = np.ones((size * size, 4), dtype=np.float32)
    out[:, :3] = rgb
    return out


def _flow_pixels(texture_set: TextureSet, size: int) -> np.ndarray:
    """The baked flow map of a set as (size * size, 4) pixels, see FLOW_PASS.

    A native bake is scaled down like the normals: the directions averaged,
    weighted by the alpha baked at the same size, so the edge of a strand
    keeps the direction of that strand, and a texel without strands flows
    straight from root to tip. The noise is averaged the same way.
    """
    from ...human.hair.card_atlas import FLOW_DEFAULT

    pixels = _pixels(texture_set.baked[FLOW_PASS])  # type:ignore[arg-type]
    native = int(round(math.sqrt(len(pixels))))
    rgb = pixels[:, :3].reshape(native, native, 3)
    direction = rgb[..., :2] * 2.0 - 1.0
    noise = rgb[..., 2:]
    if native > size:
        factor = native // size
        alpha = texture_set.baked.get("alpha")
        if isinstance(alpha, bpy.types.Image) and alpha.size[0] == native:
            weight = np.clip(_pixels(alpha)[:, 0].reshape(native, native, 1), 0.0, 1.0)
        else:
            weight = np.ones((native, native, 1), dtype=np.float32)
        total = _box_down(weight, factor)
        direction = _box_down(direction * weight, factor)
        noise = _box_down(noise * weight, factor)
        covered = total[..., 0] > 1e-4
        noise = np.where(covered[..., None], noise / np.maximum(total, 1e-6), FLOW_DEFAULT[2])
    else:
        covered = np.ones((size, size), dtype=bool)
    length = np.linalg.norm(direction, axis=2)
    covered &= length > 1e-6
    out = np.ones((size * size, 4), dtype=np.float32)
    flow = np.empty((size, size, 3), dtype=np.float32)
    flow[...] = FLOW_DEFAULT
    flow[covered, :2] = direction[covered] / length[covered][:, None] * 0.5 + 0.5
    flow[covered, 2] = np.clip(noise[covered, 0], 0.0, 1.0)
    out[:, :3] = flow.reshape(-1, 3)
    return out


Rect = Tuple[float, float, float, float]


def _card_rects(obj: bpy.types.Object, slot: int) -> List[Rect]:
    """The parts of the atlas the cards of an object use, as (u0, u1, v0, v1).

    A card is a strip of quads between two columns of the atlas, so the two u
    values of its polygons are the sides of its part, and its v values span it.
    """
    mesh = obj.data
    uv_layer = mesh.uv_layers.active
    if uv_layer is None or not len(mesh.polygons):
        return []
    uvs = np.empty(len(mesh.loops) * 2, dtype=np.float32)
    uv_layer.data.foreach_get("uv", uvs)
    uvs = uvs.reshape(-1, 2)
    material_index = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("material_index", material_index)
    loop_total = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("loop_total", loop_total)
    of_slot = np.repeat(material_index == slot, loop_total)
    polygon = np.repeat(np.arange(len(mesh.polygons)), loop_total)[of_slot]
    u, v = uvs[of_slot, 0], uvs[of_slot, 1]
    count = len(mesh.polygons)
    u_min = np.full(count, np.inf)
    u_max = np.full(count, -np.inf)
    np.minimum.at(u_min, polygon, u)
    np.maximum.at(u_max, polygon, u)
    sides = np.round(np.stack((u_min[polygon], u_max[polygon]), axis=1), 4)
    v_min = np.full(count, np.inf)
    v_max = np.full(count, -np.inf)
    np.minimum.at(v_min, polygon, v)
    np.maximum.at(v_max, polygon, v)
    rects: List[Rect] = []
    for u0, u1 in np.unique(sides, axis=0):
        if u1 - u0 < 1e-4:
            continue
        of_rect = np.unique(polygon[(sides[:, 0] == u0) & (sides[:, 1] == u1)])
        # Cards of a generated atlas stack in the same column with a gap between
        # their tiles: every run of touching polygons is one part
        order = of_rect[np.argsort(v_min[of_rect], kind="stable")]
        start, end = float(v_min[order[0]]), float(v_max[order[0]])
        for poly in order[1:]:
            if v_min[poly] > end + CARD_RECT_GAP:
                rects.append((float(u0), float(u1), start, end))
                start = float(v_min[poly])
            end = max(end, float(v_max[poly]))
        rects.append((float(u0), float(u1), start, end))
    return rects


# Gap in v between the polygons of two cards in the same column of the atlas, at
# which they are two parts; the quads of one card touch
CARD_RECT_GAP = 0.0005


def _card_edge_fade(texture_set: TextureSet, size: int) -> np.ndarray:
    """A (size, size) factor that fades the alpha out at the sides of every
    part of the atlas the cards use, see CARD_EDGE_FADE."""
    fade = np.ones((size, size), dtype=np.float32)
    for u0, u1, v0, v1 in _card_rects(texture_set.obj, texture_set.slot):
        x0, x1 = int(u0 * size), int(math.ceil(u1 * size))
        y0, y1 = int(v0 * size), int(math.ceil(v1 * size))
        centers = (np.arange(x0, x1) + 0.5) / size
        distance = np.minimum(centers - u0, u1 - centers) / (u1 - u0)
        t = np.clip(distance / CARD_EDGE_FADE, 0.0, 1.0)
        fade[y0:y1, x0:x1] = np.minimum(fade[y0:y1, x0:x1], t * t * (3 - 2 * t))
    return fade


def _downsample_coverage(
    alpha: np.ndarray, factor: int, rects: Optional[List[Rect]] = None
) -> np.ndarray:
    """Scales an alpha image down by a whole factor, keeping the share of texels
    above the cut-out the same in every part of the atlas the cards use.

    Averaging alone turns a strand thinner than a texel into a texel below the
    cut-out, so the hair thinned out with every step down from the atlas.
    The averaged alpha is multiplied by the factor that brings the covered
    share back, as Unity's coverage-preserving mipmaps do. The factor is found
    per part: one factor for the whole atlas was set by its dense parts, and
    the parts of fine strands lost whole cards.
    """
    rows, cols = alpha.shape
    small = _box_down(alpha, factor)
    out = small.copy()
    regions = [(0.0, 1.0, 0.0, 1.0)] if not rects else rects
    for u0, u1, v0, v1 in regions:
        x0, x1 = int(u0 * cols) // factor, -(-int(math.ceil(u1 * cols)) // factor)
        y0, y1 = int(v0 * rows) // factor, -(-int(math.ceil(v1 * rows)) // factor)
        part = alpha[y0 * factor : y1 * factor, x0 * factor : x1 * factor]
        averaged = small[y0:y1, x0:x1]
        coverage = (part > HAIR_ALPHA_CUTOFF).mean() if part.size else 0.0
        if coverage <= 0:
            continue
        low, high = 1.0, 8.0
        for _ in range(20):
            scale = (low + high) / 2
            if (np.minimum(averaged * scale, 1.0) > HAIR_ALPHA_CUTOFF).mean() < coverage:
                low = scale
            else:
                high = scale
        out[y0:y1, x0:x1] = np.minimum(averaged * (low + high) / 2, 1.0)
    return out.astype(np.float32)


# Alpha above which a texel of a hair texture counts as covered, see _fill_uncovered
COVERED_ALPHA = 0.3
# How far, in texels, the color of the strands is spread into the gaps
FILL_RADIUS = 8


def _fill_uncovered(pixels: np.ndarray, size: int) -> None:
    """Spreads the color of the covered texels into the transparent ones.

    The gaps between the strands of the hair cards are black in the baked
    color, and texture filtering and mipmaps mix that black into the edges
    of every strand, which gave the hair a dark fringe and made it darker at
    a distance. The gaps get the color of the nearest strand, and whatever
    stays empty beyond the fill radius gets the average color of the strands.
    """
    rgb = pixels[:, :3].reshape(size, size, 3)
    covered = pixels[:, 3].reshape(size, size) > COVERED_ALPHA
    if not covered.any():
        return
    average = rgb[covered].mean(axis=0)
    color = np.where(covered[..., None], rgb, 0.0).astype(np.float32)
    weight = covered.astype(np.float32)
    for _ in range(FILL_RADIUS):
        total = np.zeros_like(color)
        count = np.zeros_like(weight)
        for axis in (0, 1):
            for shift in (-1, 1):
                total += np.roll(color, shift, axis=axis)
                count += np.roll(weight, shift, axis=axis)
        grow = (weight == 0) & (count > 0)
        color[grow] = total[grow] / count[grow][:, None]
        weight[grow] = 1.0
    color[weight == 0] = average
    rgb[~covered] = color[~covered]


def _average(image: bpy.types.Image, weights: object) -> Optional[float]:
    """The mean of a sampled pass over the texels the bake reached, weighted
    by the alpha pass of the set when it has one: the specular of hair cards
    counts where the strands are, not in the gaps between them."""
    pixels = _pixels(image)
    covered = pixels[:, 3] > 0.5
    weight = covered.astype(np.float32)
    if isinstance(weights, bpy.types.Image) and weights.size[0] % image.size[0] == 0:
        factor = weights.size[0] // image.size[0]
        alpha = _pixels(weights)[:, 0].reshape(image.size[1], factor, image.size[0], factor)
        weight *= alpha.mean(axis=(1, 3)).ravel()
    if weight.sum() <= 0:
        return None
    return float((pixels[:, 0] * weight).sum() / weight.sum())


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
        # The file gets the name of the scheme, also when an image of that name
        # is in the file already, like the textures of an earlier result
        file_name = SUFFIX.sub("", image.name)
        image.filepath_raw = os.path.join(folder, f"{file_name}.{extension}")
        image.file_format = file_format.upper()
        image.save()
        image.reload()
    else:
        image.pack()


def _build_material(  # noqa: CCR001
    human: "Human",
    texture_set: TextureSet,
    settings: TextureBakeSettings,
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
            pixels[:, 3] = _alpha_channel(texture_set, size)
            _fill_uncovered(pixels, size)
        images["base_color"] = _new_image(
            namer.texture(part, "base_color", per_level), size, pixels, True, pack_alpha
        )
    if isinstance(alpha, bpy.types.Image) and (
        "base_color" not in images or images["base_color"].alpha_mode != "CHANNEL_PACKED"
    ):
        pixels = np.ones((size * size, 4), dtype=np.float32)
        pixels[:, :3] = _alpha_channel(texture_set, size)[:, None]
        images["alpha"] = _new_image(
            namer.texture(part, "alpha", per_level), size, pixels, False, False
        )

    normal = baked.get("normal")
    if isinstance(normal, bpy.types.Image):
        pixels = _normal_pixels(texture_set, size)
        if settings.normal_map == "directx":
            pixels[:, 1] = 1.0 - pixels[:, 1]
        images["normal"] = _new_image(
            namer.texture(part, "normal", per_level), size, pixels, False, False
        )

    flow = baked.get(FLOW_PASS)
    if isinstance(flow, bpy.types.Image):
        images[FLOW_PASS] = _new_image(
            namer.texture(part, FLOW_PASS, per_level), size, _flow_pixels(texture_set, size), False, False
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

    specular = baked.get("specular")
    if isinstance(specular, bpy.types.Image):
        average = _average(specular, alpha)
        if average is not None:
            constants["specular"] = average
    elif specular is not None:
        constants["specular"] = float(specular)  # type:ignore[arg-type]

    for image in images.values():
        _save(image, folder, settings.file_format)

    material = bpy.data.materials.new(namer.material(part, per_level))
    # Hair cards are cut out at half alpha, the haircap fades: the glTF exporter
    # writes the cards as alphaMode MASK, which engines import as alpha clip
    clip_alpha = texture_set.is_cards
    # LOD levels share it on purpose, see share_textures and copy_materials
    material[BAKED_KEY] = True
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
                _link_alpha(nodes, links, node.outputs["Alpha"], principled, clip_alpha)  # type:ignore[index]
        elif pass_id == "alpha":
            _link_alpha(nodes, links, node.outputs["Color"], principled, clip_alpha)  # type:ignore[index]
        elif pass_id == "normal":
            normal_node = nodes.new("ShaderNodeNormalMap")
            normal_node.location = (-350, -300)
            if settings.normal_map == "directx":
                # Flip the green channel back, so Blender shows it right
                _link_directx_normal(nodes, links, node, normal_node)
            else:
                links.new(node.outputs["Color"], normal_node.inputs["Color"])  # type:ignore[index]
            links.new(normal_node.outputs["Normal"], principled.inputs["Normal"])  # type:ignore[index]
        elif pass_id in ("roughness", "metallic"):
            links.new(node.outputs["Color"], principled.inputs[PASS_INPUTS[pass_id]])  # type:ignore[index]
        elif pass_id == FLOW_PASS:
            pass  # Read by no input, kept for the export, see FLOW_PASS
        else:
            _link_packed(nodes, links, node, principled, workflow)

    if any(image.alpha_mode == "CHANNEL_PACKED" for image in images.values()) or "alpha" in images:
        if bpy.app.version < (4, 3, 0):
            material.blend_method = "CLIP" if clip_alpha else "BLEND"
            material.alpha_threshold = HAIR_ALPHA_CUTOFF
            material.shadow_method = "CLIP"
        else:
            material.surface_render_method = "DITHERED" if clip_alpha else "BLENDED"

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


# Alpha below which a hair card texel is cut out in engines and in Blender's
# display of the baked copy. The baked alpha is the strand coverage of the
# atlas (see _card_source and ALPHA_SOLID), full strands with anti-aliased
# edges, so the half alpha that every engine and glTF default to cuts them
# out at their drawn width. The glTF exporter writes it as alphaCutoff, the
# Companions set it.
HAIR_ALPHA_CUTOFF = 0.5

# Name of the node that flips the green channel of a DirectX normal map for
# Blender's display. Exporters only find an image linked straight to the Normal
# Map node, so export.py links around it while the file is written.
DIRECTX_FLIP_NODE = "directx_flip"


def _link_directx_normal(nodes, links, image_node, normal_node) -> None:  # noqa: ANN001
    separate = nodes.new("ShaderNodeSeparateColor")
    separate.name = separate.label = DIRECTX_FLIP_NODE + "_separate"
    separate.location = (-550, -300)
    invert = nodes.new("ShaderNodeMath")
    invert.operation = "SUBTRACT"
    invert.inputs[0].default_value = 1.0  # type:ignore[index]
    invert.location = (-450, -400)
    combine = nodes.new("ShaderNodeCombineColor")
    combine.name = combine.label = DIRECTX_FLIP_NODE
    combine.location = (-350, -450)
    links.new(image_node.outputs["Color"], separate.inputs["Color"])  # type:ignore[index]
    links.new(separate.outputs["Red"], combine.inputs["Red"])  # type:ignore[index]
    links.new(separate.outputs["Green"], invert.inputs[1])  # type:ignore[index]
    links.new(invert.outputs[0], combine.inputs["Green"])  # type:ignore[index]
    links.new(separate.outputs["Blue"], combine.inputs["Blue"])  # type:ignore[index]
    links.new(combine.outputs["Color"], normal_node.inputs["Color"])  # type:ignore[index]


def _link_alpha(nodes, links, socket, principled, clip: bool) -> None:  # noqa: ANN001
    """Links an alpha output to the Principled alpha, through a cut-out for cards.

    A Math "greater than" node with a constant is what Blender's glTF exporter
    reads as alpha clipping at that value (alphaMode MASK with alphaCutoff);
    without it the material is exported as BLEND.
    """
    if not clip:
        links.new(socket, principled.inputs["Alpha"])  # type:ignore[index]
        return
    clip_node = nodes.new("ShaderNodeMath")
    clip_node.operation = "GREATER_THAN"
    clip_node.inputs[1].default_value = HAIR_ALPHA_CUTOFF  # type:ignore[index]
    clip_node.name = clip_node.label = "alpha_clip"
    clip_node.location = (-200, -450)
    links.new(socket, clip_node.inputs[0])  # type:ignore[index]
    links.new(clip_node.outputs[0], principled.inputs["Alpha"])  # type:ignore[index]


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


def write_sidecar_images(human: "Human", folder: str) -> List[str]:
    """Writes the baked images of the human that no exporter carries next to
    the file: the flow maps of the hair cards, which no material input reads
    and which embedded textures therefore leave out.

    Args:
        human (Human): The processed copy with baked materials.
        folder (str): Folder of the written file.

    Returns:
        List[str]: The paths written, as PNG files named like the images.
    """
    written: List[str] = []
    seen = set()
    for obj in human.objects:
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            material = slot.material
            if not material or BAKED_KEY not in material or not material.node_tree:
                continue
            node = material.node_tree.nodes.get(FLOW_PASS)
            image = getattr(node, "image", None)
            if image is None or image.name in seen:
                continue
            seen.add(image.name)
            path = os.path.join(folder, f"{SUFFIX.sub('', image.name)}.png")
            image.file_format = "PNG"
            image.save(filepath=path)
            written.append(path)
    return written


def copy_materials(
    human: "Human", objects: Optional[Iterable[bpy.types.Object]] = None
) -> None:
    """Gives the human its own copy of every material, so baking and renaming
    can't reach the human it was duplicated from.

    Materials that nothing outside this human uses are kept, so this can run
    more than once without leaving orphan copies behind. Baked materials are
    kept too, the LOD levels share those, see `share_textures`.

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
        if outside_users <= 0 or BAKED_KEY in material:
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
