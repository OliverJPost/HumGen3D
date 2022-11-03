from typing import TYPE_CHECKING, Optional

import bpy

if TYPE_CHECKING:
    from HumGen3D.human.human import Human


class MaterialSettings:
    def __init__(self, human: "Human") -> None:
        self._human = human

    @property
    def body(self) -> bpy.types.Material:
        return self._human.body_obj.data.materials[0]

    @property
    def haircards(self) -> Optional[bpy.types.Material]:
        hc_obj = self._human.haircards_obj
        if hc_obj is not None:
            return hc_obj.data.materials[0]
        else:
            return None

    @property
    def haircap(self) -> Optional[bpy.types.Material]:
        hc_obj = self._human.haircards_obj
        if hc_obj is not None:
            return hc_obj.data.materials[1]
        else:
            return None

    @property
    def clothing(self) -> list[bpy.types.Material]:
        mat_list = []
        for obj in self._human.clothing.outfit.objects:
            mat_list.extend(obj.data.materials)

        for obj in self._human.clothing.footwear.objects:
            mat_list.extend(obj.data.materials)

        return list(set(mat_list))

    @property
    def eye_hair(self) -> bpy.types.Material:
        return self._human.body_obj.data.materials[1]

    @property
    def head_hair(self) -> bpy.types.Material:
        return self._human.body_obj.data.materials[2]

    @property
    def face_hair(self) -> bpy.types.Material:
        return self._human.body_obj.data.materials[3]

    @property
    def teeth(self) -> bpy.types.Material:
        return self._human.upper_teeth_obj.data.materials[0]

    @property
    def eye_outer(self) -> bpy.types.Material:
        return self._human.eye_obj.data.materials[0]

    @property
    def eye_inner(self) -> bpy.types.Material:
        return self._human.eye_obj.data.materials[1]
