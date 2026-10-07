# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Baking the materials of a human to textures, see textures.py for the work.

Kept as the `human.process.baking` API: `bake_all` bakes with the default
texture settings, `pack_alpha_into_image` is used by scripts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import bpy
import numpy as np
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.progress import run
from HumGen3D.common.type_aliases import C

from .naming import Namer
from .settings import OutputSettings, TextureSettings

if TYPE_CHECKING:
    from ..human import Human


def pack_alpha_into_image(image: bpy.types.Image, alpha_image: bpy.types.Image) -> None:
    """Replaces the alpha channel of an image with a grayscale image and saves it.

    Game engines expect the transparency of haircards in the alpha channel of the
    color texture, instead of as a separate texture.

    Args:
        image (bpy.types.Image): Image to change the alpha channel of.
        alpha_image (bpy.types.Image): Grayscale image with the alpha values.

    Raises:
        HumGenException: If the images don't have the same size.
    """
    if tuple(image.size) != tuple(alpha_image.size):
        raise HumGenException(
            f"Can't pack {alpha_image.name} into {image.name}, sizes don't match"
        )

    pixels = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(pixels)
    alpha_pixels = np.empty(len(alpha_image.pixels), dtype=np.float32)
    alpha_image.pixels.foreach_get(alpha_pixels)

    pixels[3::4] = alpha_pixels[::4]

    # Images without transparency are saved without an alpha channel, so the file
    # is written by a new image that does have one
    width, height = image.size
    packed_image = bpy.data.images.new("HG_packed_alpha", width, height, alpha=True)
    packed_image.pixels.foreach_set(pixels)
    packed_image.filepath_raw = image.filepath_raw
    packed_image.file_format = image.file_format
    packed_image.save()
    bpy.data.images.remove(packed_image)

    image.reload()
    # Prevents Blender from multiplying the color with the alpha
    image.alpha_mode = "CHANNEL_PACKED"


class BakeSettings:
    """Bakes the materials of a human, see `HumGen3D.human.process.textures`."""

    def __init__(self, human: "Human") -> None:
        self._human = human

    @injected_context
    def bake_all(
        self,
        folder_path: Optional[str] = None,
        samples: int = 4,
        settings: Optional[TextureSettings] = None,
        context: C = None,
    ) -> list[bpy.types.Image]:
        """Bakes every material of this human and replaces it by the result.

        Changes this human, so call it on a copy. Use the process system for
        packed maps, naming schemes and LOD levels.

        Args:
            folder_path (Optional[str]): Folder to write the images to, None
                packs them in the blend file.
            samples (int): Cycles samples of the bakes.
            settings (Optional[TextureSettings]): Passes, resolution and
                packing. Defaults to separate maps at 2k.
            context (C): Blender context. bpy.context if not provided.

        Returns:
            list[bpy.types.Image]: The baked images.

        Raises:
            HumGenException: If the human was already baked.
        """
        from .textures import bake_steps, copy_materials

        if self.is_baked():
            raise HumGenException("Human was already baked")
        settings = settings.copy() if settings else TextureSettings()
        settings.samples = samples
        copy_materials(self._human)
        namer = Namer(OutputSettings(), self._human.name)
        return run(bake_steps(self._human, settings, namer, folder_path, context))

    def is_baked(self) -> bool:
        """Whether the materials of this human were baked."""
        return "hg_baked" in self._human.objects.rig
