from typing import TYPE_CHECKING

import bpy

if TYPE_CHECKING:
    from HumGen3D.human.human import Human


class MaterialSettings:
    def __init__(self, human: "Human") -> None:
        self._human = human

    @property
    def body(self) -> bpy.types.Material:
        return self._human.objects.body.data.materials[0]

    @property
    def clothing(self) -> list[bpy.types.Material]:
        mat_list = []
        for obj in self._human.clothing.outfit.objects:
            mat_list.extend(obj.data.materials)

        for obj in self._human.clothing.footwear.objects:
            mat_list.extend(obj.data.materials)

        return list(set(mat_list))

    @property
    def teeth(self) -> bpy.types.Material:
        return self._human.objects.upper_teeth.data.materials[0]

    @property
    def eye_outer(self) -> bpy.types.Material:
        return self._human.objects.eyes.data.materials[0]

    @property
    def eye_inner(self) -> bpy.types.Material:
        return self._human.objects.eyes.data.materials[1]
