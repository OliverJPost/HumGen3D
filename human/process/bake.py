# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Baking the materials of a human to textures, see textures.py for the work.

Kept as the `human.process.baking` API of earlier versions, the process system
itself uses `ProcessSettings.bake_textures`. `pack_alpha_into_image` is used
by scripts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import bpy
import numpy as np
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.type_aliases import C

from .settings import TextureBakeSettings

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
    """The `human.process.baking` API of earlier versions.

    Use `human.process.bake_textures` and `human.process.was_baked` instead.
    """

    def __init__(self, human: "Human") -> None:
        self._human = human

    @injected_context
    def bake_all(
        self,
        folder_path: Optional[str] = None,
        samples: int = 4,
        settings: Optional[TextureBakeSettings] = None,
        context: C = None,
    ) -> list[bpy.types.Image]:
        """Bakes every material of this human, see `ProcessSettings.bake_textures`.

        Args:
            folder_path (Optional[str]): Folder to write the images to, None
                packs them in the blend file.
            samples (int): Cycles samples of the bakes.
            settings (Optional[TextureBakeSettings]): Passes, resolution and
                packing. Defaults to separate maps at 2k.
            context (C): Blender context. bpy.context if not provided.

        Returns:
            list[bpy.types.Image]: The baked images.
        """
        settings = settings.copy() if settings else TextureBakeSettings()
        settings.samples = samples
        return self._human.process.bake_textures(
            settings, folder=folder_path, context=context
        )

    def is_baked(self) -> bool:
        """Whether the materials of this human were baked, see `ProcessSettings.was_baked`."""
        return self._human.process.was_baked
