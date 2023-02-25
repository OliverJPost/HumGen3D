from abc import ABC, abstractmethod
from __future__ import annotations
from typing import Iterable, Literal

import bpy
from numpy._typing import NDArray

from HumGen3D.common.context import context_override
from HumGen3D.common.geometry import world_coords_from_obj
from HumGen3D.common.math import create_kdtree

class HairBuilder(ABC):

class HairStructureBuilder:
    def __init__(
        self, human, quality: Literal["low", "medium", "high", "ultra"] = "high"
    ):
        self._human = human
        self._quality = quality
        self._systems = []

    def add_system(self, particle_modifier: bpy.types.Modifier):
        self._systems.append(particle_modifier)

    def build(self) -> HairStructure:
        pass

class HairStructure:
    hairs: dict[int, NDArray]


class MeshHairBuilder:
    _human: bpy.types.Object
    _quality: Literal["low", "medium", "high", "ultra"]
    _structure: HairStructureBuilder

    def __init__(
        self, human, quality: Literal["low", "medium", "high", "ultra"] = "high"
    ):
        self._human = human
        self._quality = quality
        self._structure = HairStructureBuilder(human, quality)
        body_local_coords_eval = world_coords_from_obj(
            human.objects.body, data=human.keys.all_deformation_shapekeys, local=True
        )
        self.body_kd_tree_local = create_kdtree(body_local_coords_eval)

    def with_eyebrows(self):
        pass

    def with_eyelashes(self):
        pass

    def with_hair(self, particle_modifier: Iterable[bpy.types.Modifier]):
        pass

    def with_face_hair(self, particle_modifier: Iterable[bpy.types.Modifier]):
        pass

    def build(self) -> bpy.types.Object:
        pass
