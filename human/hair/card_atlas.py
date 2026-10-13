# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Draws the hairs of the clumps onto the tiles of a texture atlas for haircards.

The cards used to pick a rectangle of a shared, hand painted strand texture. Those
rectangles are cut through strands at their sides and most of them are sparse, so
cards of short hair showed a tenth of the hairs the particle system has. Here the
atlas is generated for the hairstyle: cards of the same shape and density share a
tile, and the hairs of all their clumps are drawn into it where they are on the
cards. Coverage, strand width and the tapered tips then match the particle hair of
that style. A tile per card would be faithful to every single card, but a short
style has close to two thousand cards, which leaves a tile a dozen texels wide, so
the tiles are shared to keep the texel density of the painted atlas.
"""

import math
from dataclasses import dataclass
from typing import Dict, Tuple

import bpy
import numpy as np

#: Width and height of the generated atlas in texels
ATLAS_SIZE = 2048
#: The hairs are drawn at this multiple of the atlas size and averaged down, so a
#: hair thinner than a texel covers a part of it instead of all or nothing
SUPERSAMPLING = 2
#: Empty texels between tiles, so filtering does not pull one card into the next
GUTTER = 2
#: Share of the atlas the tiles may fill; a shelf packing wastes the rest
TARGET_FILL = 0.78
#: Texels per meter across the cards the tiles aim at, which sets how many tiles
#: the cards of a hair type share: 0.15 mm per texel, a texel of the texture baked
#: at 1k is then 0.3 mm, under a pixel of a character seen from close by
TARGET_TEXELS_PER_METER = 1 / 0.00015
#: Fewest tiles the cards of a hair type are drawn with, so even a few long cards
#: do not all look alike
MIN_TILES = 8
#: Hairs are drawn with at most this many strands per particle system. More strands
#: than the clustering uses, so the drawn hairs are the real children of the system
#: instead of one strand standing for many
DRAW_STRANDS_PER_SYSTEM = 40000
#: Diameter of a hair when the particle settings give none
DEFAULT_DIAMETER = 0.00007
#: Hairs are drawn at least this many atlas texels wide. A real hair is thinner
#: than a texel, which drew as a faint line that the cut-out of the engines lost;
#: the painted atlas draws every strand at full alpha too. To keep the coverage of
#: the clump, a hair thinner than this is drawn with the probability of its width
#: over this width: fewer strands, as thick as the texture can show
MIN_STRAND_TEXELS = 1.0
#: A strand that stands for several hairs is drawn as that many copies, spread
#: sideways over the room the hairs have between the neighbouring strands. More
#: copies than this are drawn as ink
MAX_COPIES = 6
#: Brightness variation between hairs and darkening towards the roots, as the
#: occlusion texture of the painted atlas has (its strands average 0.83)
MIN_BRIGHTNESS = 0.7
ROOT_DARKENING = 0.25
ROOT_SHARE = 0.35
#: Range of the specular variation between hairs
MIN_GLOSS = 0.25
#: Tilt of the normal at the sides of a card, so a flat card shades like a bundle of
#: hair with a round cross-section. 1 would be a full cylinder
NORMAL_TILT = 0.4
#: Longest distance between two drawn points of a hair, in supersampled texels
MAX_STEP = 0.75
#: Cap on the points drawn per atlas, long hairs are drawn coarser above it
MAX_SAMPLES = 60_000_000

#: Name parts of the images of the card material, by the texture they hold. The
#: flow image is not read by the material: it holds the direction of the hairs
#: across the tile (red and green, in the UV space of the card, from root to tip)
#: and a random value per hair (blue), for the hair shaders of game engines
IMAGE_NAME_PARTS = {
    "alpha": "_ALPHA",
    "occlusion": "_AO",
    "specular": "_SPECULAR",
    "normal": "_NORMAL",
    "flow": "_FLOW",
}
COLOR_SPACES = {
    "alpha": "sRGB",
    "occlusion": "sRGB",
    "specular": "Non-Color",
    "normal": "Non-Color",
    "flow": "Non-Color",
}
#: Flow of a texel without hairs: straight from the root to the tip of the card
#: (towards -v), with the noise in the middle
FLOW_DEFAULT = (0.5, 0.0, 0.5)


@dataclass
class AtlasLayout:
    """Where the cards are on the generated atlas and how to draw their hairs."""

    #: (c, 4) tile of every card in UV coordinates: u_min, v_min, u_max, v_max. The
    #: root of the card is at v_max; u_min > u_max for a card that uses its tile
    #: mirrored
    uv_rects: np.ndarray
    #: (t, 4) tiles of the atlas as (x, y, width, height) in texels
    tiles: np.ndarray
    #: (c,) tile every card draws its hairs into and is textured with
    tile_of_card: np.ndarray
    #: (c, STATIONS, 3) middle line of the cards
    centers: np.ndarray
    #: (c, STATIONS, 3) unit vectors from the middle to the side with u_max
    sides: np.ndarray
    #: (c, STATIONS) half the width of the cards
    half_widths: np.ndarray
    #: (c, STATIONS) length along the card at every station
    arc: np.ndarray
    #: (c,) clump every card belongs to
    clump: np.ndarray
    #: (k, f) center of every clump in the feature space of the clustering
    clump_centroids: np.ndarray
    #: (k,) particle system of every clump
    clump_system: np.ndarray
    #: (k,) number of strands the clustering put in every clump
    clump_sizes: np.ndarray
    #: Width and height of the atlas in texels
    size: int = ATLAS_SIZE


def tile_count(lengths: np.ndarray, widths: np.ndarray, size: int = ATLAS_SIZE) -> int:
    """How many tiles the cards should share so a tile is TARGET_TEXELS_PER_METER
    across.

    Args:
        lengths (np.ndarray): (c,) length of the cards in meters.
        widths (np.ndarray): (c,) average width of the cards in meters.
        size (int): Width and height of the atlas in texels.

    Returns:
        int: Number of tiles, between MIN_TILES and the number of cards.
    """
    count = len(lengths)
    if not count:
        return 0
    tile_h = np.minimum(lengths * TARGET_TEXELS_PER_METER, size - GUTTER) + GUTTER
    tile_w = widths * TARGET_TEXELS_PER_METER + GUTTER
    mean_area = float((tile_h * tile_w).mean())
    wanted = int(round(size * size * TARGET_FILL / max(mean_area, 1.0)))
    return int(np.clip(wanted, min(MIN_TILES, count), count))


def pack_tiles(
    lengths: np.ndarray, widths: np.ndarray, size: int = ATLAS_SIZE
) -> np.ndarray:
    """Gives every tile its place on the atlas, sized by the length and width of the
    cards it stands for.

    The tiles are packed on shelves: sorted by height, laid out in rows. The texel
    density is the largest at which all tiles fit.

    Args:
        lengths (np.ndarray): (t,) length of the cards of the tiles in meters.
        widths (np.ndarray): (t,) average width of those cards in meters.
        size (int): Width and height of the atlas in texels.

    Returns:
        np.ndarray: (t, 4) tiles as (x, y, width, height) in texels.
    """
    count = len(lengths)
    tiles = np.zeros((count, 4), dtype=np.int64)
    if not count:
        return tiles
    lengths = np.maximum(lengths, 1e-4)
    widths = np.maximum(widths, 1e-4)
    area = float((lengths * widths).sum())
    density = math.sqrt(size * size * TARGET_FILL / area)
    for _ in range(60):
        tile_w = np.minimum(np.ceil(widths * density).astype(np.int64) + 1, size)
        tile_h = np.minimum(np.ceil(lengths * density).astype(np.int64) + 1, size)
        order = np.argsort(-tile_h, kind="stable")
        x = y = row_h = 0
        fits = True
        for idx in order:
            w, h = int(tile_w[idx]), int(tile_h[idx])
            if x + w > size:
                x = 0
                y += row_h + GUTTER
                row_h = 0
            if y + h > size:
                fits = False
                break
            tiles[idx] = (x, y, w, h)
            x += w + GUTTER
            row_h = max(row_h, h)
        if fits:
            return tiles
        density *= 0.93
    raise ValueError("Hair cards do not fit on the atlas")


def tiles_to_uv(tiles: np.ndarray, size: int) -> np.ndarray:
    """Converts texel tiles to (u_min, v_min, u_max, v_max) rectangles."""
    x, y, w, h = tiles.T
    return np.stack((x, y, x + w, y + h), axis=1) / size


def _box_down(image: np.ndarray, factor: int) -> np.ndarray:
    rows, cols = image.shape[:2]
    shape = (rows // factor, factor, cols // factor, factor) + image.shape[2:]
    return image.reshape(shape).mean(axis=(1, 3))


def _smoothstep(edge0: float, edge1: float, values: np.ndarray) -> np.ndarray:
    t = np.clip((values - edge0) / (edge1 - edge0), 0, 1)
    return t * t * (3 - 2 * t)


def _srgb_to_linear(values: np.ndarray) -> np.ndarray:
    return np.where(
        values <= 0.04045, values / 12.92, ((values + 0.055) / 1.055) ** 2.4
    )


def _linear_to_srgb(values: np.ndarray) -> np.ndarray:
    values = np.clip(values, 0, 1)
    return np.where(
        values <= 0.0031308, values * 12.92, 1.055 * values ** (1 / 2.4) - 0.055
    )


def draw_atlas(
    layout: AtlasLayout,
    points: np.ndarray,
    labels: np.ndarray,
    weights: np.ndarray,
    diameters: np.ndarray,
    seed: int = 0,
) -> Dict[str, np.ndarray]:
    """Draws the hairs of the clumps into the tiles of their cards.

    The cards that share a tile draw their clumps on top of each other, each
    thinned out by the number of cards, so the tile shows the average of them.

    Args:
        layout (AtlasLayout): Tiles and frames of the cards.
        points (np.ndarray): (n, STATIONS, 3) strands to draw, in the space of the
            card frames.
        labels (np.ndarray): (n,) clump of every strand, -1 for strands to skip.
        weights (np.ndarray): (n,) number of hairs every strand stands for.
        diameters (np.ndarray): (n, 2) diameter of the hairs at the root and the tip
            in meters.
        seed (int): Seed of the random brightness and spread of the hairs.

    Returns:
        Dict[str, np.ndarray]: (size, size, 3) float images by name, see
            IMAGE_NAME_PARTS, with the row for v = 0 first.
    """
    size = layout.size
    ss_size = size * SUPERSAMPLING
    rng = np.random.default_rng(seed)
    stations = layout.centers.shape[1]
    tiles = layout.tiles[layout.tile_of_card]
    tile_x, tile_y, tile_w, tile_h = tiles.T
    # The cards that use their tile mirrored draw their hairs mirrored
    flip = np.where(layout.uv_rects[:, 2] < layout.uv_rects[:, 0], -1.0, 1.0)
    cards_per_tile = np.bincount(layout.tile_of_card, minlength=len(layout.tiles))

    # Pairs of a card and a strand of its clump; a clump with a crossing card draws
    # its strands on both
    strand_of_clump = [np.flatnonzero(labels == k) for k in range(len(layout.clump_sizes))]
    pair_card = np.concatenate(
        [np.full(len(strand_of_clump[k]), c) for c, k in enumerate(layout.clump)]
    ).astype(np.int64)
    pair_strand = np.concatenate([strand_of_clump[k] for k in layout.clump]).astype(np.int64)
    pair_count = len(pair_card)
    ink = np.zeros(ss_size * ss_size, dtype=np.float64)
    bright_ink = np.zeros_like(ink)
    gloss_ink = np.zeros_like(ink)
    flow_x_ink = np.zeros_like(ink)
    flow_y_ink = np.zeros_like(ink)
    noise_ink = np.zeros_like(ink)

    if pair_count:
        centers = layout.centers[pair_card]
        offsets = points[pair_strand] - centers
        u = np.einsum("nmi,nmi->nm", offsets, layout.sides[pair_card])
        u = u / np.maximum(layout.half_widths[pair_card], 1e-6)
        # Where along the card every station of a strand is: the arc of the card
        # at that station plus how far ahead of or behind the station the point
        # is along the card. A hair that is shorter than the middle line of its
        # clump, or curls more, ends before the tip of the card instead of being
        # stretched to it, which is what makes the tips of the cards ragged
        tangents = np.gradient(layout.centers, axis=1)
        tangents /= np.maximum(np.linalg.norm(tangents, axis=2, keepdims=True), 1e-9)
        ahead = np.einsum("nmi,nmi->nm", offsets, tangents[pair_card])
        along = (layout.arc[pair_card] + ahead) / np.maximum(layout.arc[pair_card, -1:], 1e-9)
        # Supersampled texel coordinates of every station
        u = u * flip[pair_card, None]
        px = (tile_x[pair_card, None] + tile_w[pair_card, None] * (1 + u) / 2) * SUPERSAMPLING
        py = (tile_y[pair_card, None] + tile_h[pair_card, None] * (1 - along)) * SUPERSAMPLING
        meters_per_px = (
            layout.arc[pair_card, -1] / np.maximum(tile_h[pair_card] * SUPERSAMPLING, 1)
        )
        root_px = diameters[pair_strand, 0] / np.maximum(meters_per_px, 1e-9)
        tip_px = diameters[pair_strand, 1] / np.maximum(meters_per_px, 1e-9)
        # Room a strand has between its neighbours across the card, for the copies
        clump_width_px = tile_w[pair_card] * SUPERSAMPLING
        spacing = clump_width_px / np.maximum(layout.clump_sizes[layout.clump[pair_card]], 1)
        strand_weight = weights[pair_strand]
        copies = np.clip(np.ceil(strand_weight), 1, MAX_COPIES).astype(np.int64)
        brightness = rng.uniform(MIN_BRIGHTNESS, 1.0, len(points))[pair_strand]
        gloss = rng.uniform(MIN_GLOSS, 1.0, len(points))[pair_strand]
        noise = rng.uniform(0.0, 1.0, len(points))[pair_strand]

        # Segments between stations
        seg = stations - 1
        x0, x1 = px[:, :-1].ravel(), px[:, 1:].ravel()
        y0, y1 = py[:, :-1].ravel(), py[:, 1:].ravel()
        along_mid = ((along[:, :-1] + along[:, 1:]) / 2).ravel()
        seg_pair = np.repeat(np.arange(pair_count), seg)
        width_px = root_px[seg_pair] + (tip_px[seg_pair] - root_px[seg_pair]) * along_mid
        # A hair that tapers is drawn fainter towards its tip, as the one-texel
        # floor below would otherwise draw it at full alpha to the last texel
        taper = np.clip(width_px / np.maximum(root_px[seg_pair], 1e-9), 0.0, 1.0)
        floor_px = MIN_STRAND_TEXELS * SUPERSAMPLING
        # Thin out the strands that are drawn wider than they are, see MIN_STRAND_TEXELS
        mean_width = (root_px + tip_px) / 2
        keep_share = np.clip(mean_width / floor_px, 0.0, 1.0)
        # A tile shows the average of the cards that share it
        keep_share /= cards_per_tile[layout.tile_of_card[pair_card]]
        kept = rng.random((pair_count, MAX_COPIES)) < keep_share[:, None]
        width_px = np.maximum(width_px, floor_px)
        lengths = np.hypot(x1 - x0, y1 - y0)
        # Drop segments entirely outside the tile of their card
        tx0 = tile_x[pair_card[seg_pair]] * SUPERSAMPLING
        tx1 = tx0 + tile_w[pair_card[seg_pair]] * SUPERSAMPLING
        inside = (np.maximum(x0, x1) >= tx0) & (np.minimum(x0, x1) < tx1)
        seg_copies = copies[seg_pair]
        step = MAX_STEP
        wanted = float((np.ceil(lengths[inside] / step) * seg_copies[inside]).sum())
        if wanted > MAX_SAMPLES:
            step *= wanted / MAX_SAMPLES
        keep = np.flatnonzero(inside)
        steps = np.maximum(np.ceil(lengths[keep] / step).astype(np.int64), 1)
        # Every copy of a segment is a run of samples
        run_seg = np.repeat(keep, seg_copies[keep])
        run_copy = np.concatenate([np.arange(n) for n in seg_copies[keep]]) if len(keep) else np.zeros(0, dtype=np.int64)
        run_steps = np.repeat(steps, seg_copies[keep])
        run_kept = kept[seg_pair[run_seg], run_copy]
        run_seg, run_copy, run_steps = run_seg[run_kept], run_copy[run_kept], run_steps[run_kept]
        total = int(run_steps.sum())
        run_of_sample = np.repeat(np.arange(len(run_seg)), run_steps)
        starts = np.concatenate(([0], np.cumsum(run_steps)[:-1]))
        t = (np.arange(total) - starts[run_of_sample] + 0.5) / run_steps[run_of_sample]
        s = run_seg[run_of_sample]
        sx = x0[s] + (x1[s] - x0[s]) * t
        sy = y0[s] + (y1[s] - y0[s]) * t
        # Sideways jitter: the thickness of the hair, plus the spread of the copies
        # that stand for the hairs around the strand
        dx, dy = x1[s] - x0[s], y1[s] - y0[s]
        norm = np.maximum(np.hypot(dx, dy), 1e-9)
        nx, ny = -dy / norm, dx / norm
        lateral = rng.uniform(-0.5, 0.5, total) * width_px[s]
        is_copy = run_copy[run_of_sample] > 0
        spread = rng.normal(0.0, 0.5, total) * spacing[seg_pair[s]] * is_copy
        sx += nx * (lateral + spread)
        sy += ny * (lateral + spread)
        # Ink: the area the hair covers per sample, shared between the copies
        pair_of_sample = seg_pair[s]
        per_copy = strand_weight[pair_of_sample] / copies[pair_of_sample]
        area = per_copy * np.maximum(width_px[s], 0.0) * (lengths[s] / run_steps[run_of_sample])
        area = np.minimum(area, 4.0) * taper[s]
        shade = 1 - ROOT_DARKENING * (1 - _smoothstep(0.0, ROOT_SHARE, along_mid[s]))

        ix = np.floor(sx).astype(np.int64)
        iy = np.floor(sy).astype(np.int64)
        tx = tile_x[pair_card[pair_of_sample]] * SUPERSAMPLING
        ty = tile_y[pair_card[pair_of_sample]] * SUPERSAMPLING
        in_tile = (
            (ix >= tx)
            & (ix < tx + tile_w[pair_card[pair_of_sample]] * SUPERSAMPLING)
            & (iy >= ty)
            & (iy < ty + tile_h[pair_card[pair_of_sample]] * SUPERSAMPLING)
        )
        flat = (iy * ss_size + ix)[in_tile]
        area = area[in_tile]
        ink += np.bincount(flat, weights=area, minlength=ink.size)
        bright_ink += np.bincount(
            flat, weights=area * brightness[pair_of_sample][in_tile] * shade[in_tile], minlength=ink.size
        )
        gloss_ink += np.bincount(flat, weights=area * gloss[pair_of_sample][in_tile], minlength=ink.size)
        # The direction of the hair at every sample, from the root to the tip
        flow_x_ink += np.bincount(flat, weights=area * (dx / norm)[in_tile], minlength=ink.size)
        flow_y_ink += np.bincount(flat, weights=area * (dy / norm)[in_tile], minlength=ink.size)
        noise_ink += np.bincount(flat, weights=area * noise[pair_of_sample][in_tile], minlength=ink.size)

    ink = ink.reshape((ss_size, ss_size))
    coverage = 1 - np.exp(-ink)
    with np.errstate(invalid="ignore", divide="ignore"):
        brightness_map = np.where(ink > 0, bright_ink.reshape(ink.shape) / ink, 0.0)
        gloss_map = np.where(ink > 0, gloss_ink.reshape(ink.shape) / ink, 0.0)
    alpha = _box_down(coverage, SUPERSAMPLING).astype(np.float32)
    # The card material divides the occlusion by the alpha to get the brightness
    # of the hairs, both decoded from sRGB, so the occlusion is stored such that
    # decoded occlusion / decoded alpha is the brightness
    brightness_down = _box_down(coverage * brightness_map, SUPERSAMPLING)
    with np.errstate(invalid="ignore", divide="ignore"):
        brightness_down = np.where(alpha > 0, brightness_down / np.maximum(alpha, 1e-6), 0.0)
    occlusion = _linear_to_srgb(_srgb_to_linear(alpha) * brightness_down).astype(np.float32)
    specular = _box_down(gloss_map * (ink > 0), SUPERSAMPLING).astype(np.float32)
    flow = _flow_image(ink, coverage, alpha, flow_x_ink, flow_y_ink, noise_ink)

    normal = np.empty((size, size, 3), dtype=np.float32)
    normal[..., 0] = normal[..., 1] = 0.5
    normal[..., 2] = 1.0
    for x, y, w, h in layout.tiles:
        across = (np.arange(w) + 0.5) / max(w, 1) * 2 - 1
        tilt_x = across * NORMAL_TILT
        tilt_z = np.sqrt(np.maximum(1 - tilt_x**2, 0))
        normal[y : y + h, x : x + w, 0] = (tilt_x + 1) / 2
        normal[y : y + h, x : x + w, 2] = tilt_z

    def grey(values: np.ndarray) -> np.ndarray:
        return np.repeat(values[..., None], 3, axis=2)

    return {
        "alpha": grey(alpha),
        "occlusion": grey(occlusion),
        "specular": grey(specular),
        "normal": normal,
        "flow": flow,
    }


def _flow_image(
    ink: np.ndarray,
    coverage: np.ndarray,
    alpha: np.ndarray,
    flow_x_ink: np.ndarray,
    flow_y_ink: np.ndarray,
    noise_ink: np.ndarray,
) -> np.ndarray:
    """The flow image of the atlas, see IMAGE_NAME_PARTS: the direction of the
    hairs averaged over the hairs of a texel and weighted by their coverage when
    scaled down, so the edge of a hair keeps the direction of that hair, with
    the default where no hair is."""
    with np.errstate(invalid="ignore", divide="ignore"):
        maps = [
            np.where(ink > 0, values.reshape(ink.shape) / ink, 0.0)
            for values in (flow_x_ink, flow_y_ink, noise_ink)
        ]
    weighted = [_box_down(coverage * values, SUPERSAMPLING) for values in maps]
    with np.errstate(invalid="ignore", divide="ignore"):
        flow_x, flow_y, noise = (
            np.where(alpha > 0, values / np.maximum(alpha, 1e-6), 0.0) for values in weighted
        )
    length = np.hypot(flow_x, flow_y)
    has_hair = (alpha > 0) & (length > 1e-6)
    flow = np.empty(alpha.shape + (3,), dtype=np.float32)
    flow[...] = FLOW_DEFAULT
    flow[has_hair, 0] = (flow_x[has_hair] / length[has_hair] + 1) / 2
    flow[has_hair, 1] = (flow_y[has_hair] / length[has_hair] + 1) / 2
    flow[has_hair, 2] = np.clip(noise[has_hair], 0, 1)
    return flow


def create_images(name: str, images: Dict[str, np.ndarray]) -> Dict[str, bpy.types.Image]:
    """Stores the drawn atlas as packed images in the blend file.

    Args:
        name (str): Name of the images, the name part of the texture is appended.
        images (Dict[str, np.ndarray]): (size, size, 3) float images, see draw_atlas.

    Returns:
        Dict[str, bpy.types.Image]: Images by texture name.
    """
    result = {}
    for key, pixels in images.items():
        rows, cols = pixels.shape[:2]
        image = bpy.data.images.new(
            f"{name}{IMAGE_NAME_PARTS[key]}", cols, rows, alpha=False, float_buffer=False
        )
        image.colorspace_settings.name = COLOR_SPACES[key]
        rgba = np.ones((rows, cols, 4), dtype=np.float32)
        rgba[..., :3] = pixels
        image.pixels.foreach_set(rgba.ravel())
        image.file_format = "PNG"
        image.pack()
        result[key] = image
    return result


def assign_images(
    material: bpy.types.Material, images: Dict[str, bpy.types.Image]
) -> None:
    """Points the strand textures of a card material at the generated images.

    The node group of the material is shared between all card materials, it is
    copied for this material first. An image the group has no texture for, like
    the flow image, is put in an image node of its own in the group, unlinked,
    so the texture bake of the process system finds it with the others.

    Args:
        material (bpy.types.Material): Material from haircards.load_card_material.
        images (Dict[str, bpy.types.Image]): Images from create_images.
    """
    group_node = next(
        node for node in material.node_tree.nodes if node.bl_idname == "ShaderNodeGroup"
    )
    if group_node.node_tree.users > 1:
        group_node.node_tree = group_node.node_tree.copy()
    assigned = set()
    for node in group_node.node_tree.nodes:
        if node.bl_idname != "ShaderNodeTexImage" or not node.image:
            continue
        for key, name_part in IMAGE_NAME_PARTS.items():
            if name_part in node.image.name and key in images:
                node.image = images[key]
                assigned.add(key)
                break
    for key, image in images.items():
        if key in assigned:
            continue
        node = group_node.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = image
        node.name = node.label = f"hg_{key}"
        node.location = (-900, -600)


def coverage_of(images: Dict[str, np.ndarray], layout: AtlasLayout) -> Tuple[float, float]:
    """Share of the tile texels that is hair, overall and above the half alpha the
    engines cut out at. For checks and logging."""
    alpha = images["alpha"][..., 0]
    mask = np.zeros(alpha.shape, dtype=bool)
    for x, y, w, h in layout.tiles:
        mask[y : y + h, x : x + w] = True
    if not mask.any():
        return 0.0, 0.0
    return float(alpha[mask].mean()), float((alpha[mask] > 0.5).mean())
