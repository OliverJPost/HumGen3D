"""Contains class for accessing materials of human."""

from typing import TYPE_CHECKING, Optional

import bpy

if TYPE_CHECKING:
    from HumGen3D.human.human import Human


class MaterialSettings:
    """Interface for accessing materials of human."""

    def __init__(self, human: "Human") -> None:
        self._human = human

    @property
    def body(self) -> bpy.types.Material:
        """Body material.

        Returns:
            bpy.types.Material: Body material.
        """
        return self._human.objects.body.data.materials[0]

    @property
    def clothing(self) -> list[bpy.types.Material]:
        """Clothing materials.

        Returns:
            list[bpy.types.Material]: List of all materials of clothing on this human.
                Does not have duplicates.
        """
        mat_list = []
        for obj in self._human.clothing.outfit.objects:
            mat_list.extend(obj.data.materials)

        for obj in self._human.clothing.footwear.objects:
            mat_list.extend(obj.data.materials)

        return list(set(mat_list))

    @property
    def teeth(self) -> bpy.types.Material:
        """Teeth material.

        Returns:
            bpy.types.Material: Teeth material.
        """
        return self._human.objects.upper_teeth.data.materials[0]

    @property
    def eye_outer(self) -> Optional[bpy.types.Material]:
        """Outer eye material.

        Returns:
            Optional[bpy.types.Material]: Outer eye material. None if the human
                has game eyes, which don't have an outer layer.
        """
        if self._human.process.has_game_eyes:
            return None
        return self._human.objects.eyes.data.materials[0]

    @property
    def eye_inner(self) -> bpy.types.Material:
        """Inner eye material. For game eyes this is their only material.

        Returns:
            bpy.types.Material: Inner eye material.
        """
        return self._human.objects.eyes.data.materials[self.eye_inner_slot]

    @property
    def eye_inner_slot(self) -> int:
        """Index of the material slot of the inner eye material.

        Returns:
            int: Index of the material slot.
        """
        return 0 if self._human.process.has_game_eyes else 1

    @property
    def haircards(self) -> list[bpy.types.Material]:
        """Materials of the haircards, if generated.

        Returns:
            list[bpy.types.Material]: Materials of the haircards.
        """
        mats = []
        for obj in self._human.objects.haircards:
            if len(obj.data.materials) > 1:
                mats.append(obj.data.materials[1])

        return mats

    @property
    def haircap(self) -> list[bpy.types.Material]:
        """Materials of the haircaps, if generated.

        The haircap is in the first material slot of the haircard objects.

        Returns:
            list[bpy.types.Material]: Materials of the haircaps.
        """
        mats = []
        for obj in self._human.objects.haircards:
            mats.append(obj.data.materials[0])

        return mats

    @property
    def eye_hair(self) -> bpy.types.Material:
        return self._human.objects.body.data.materials[1]

    @property
    def head_hair(self) -> bpy.types.Material:
        return self._human.objects.body.data.materials[2]

    @property
    def face_hair(self) -> bpy.types.Material:
        return self._human.objects.body.data.materials[3]

    def __iter__(self):
        """Iterate over all materials of human."""
        yield self.body
        yield from self.clothing
        yield self.teeth
        yield self.eye_outer
        yield self.eye_inner
