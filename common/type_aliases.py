"""File containing commonly used type aliases."""

from typing import List, Literal, Optional, Union

import bpy
from mathutils import Vector

C = Optional[bpy.types.Context]

PcollRowHeader = tuple[str, str, str]
PcollRow = tuple[str, str, str, int]
PcollRowIcon = tuple[str, str, str, int, int]
BpyEnum = List[Union[PcollRow, PcollRowIcon, PcollRowHeader]]
DistanceDict = dict[int, tuple[int, Vector]]
GenderStr = Literal["male", "female"]
BpyModifierName = Literal[
    "DATA_TRANSFER",
    "MESH_CACHE",
    "MESH_SEQUENCE_CACHE",
    "NORMAL_EDIT",
    "WEIGHTED_NORMAL",
    "UV_PROJECT",
    "UV_WARP",
    "VERTEX_WEIGHT_EDIT",
    "VERTEX_WEIGHT_MIX",
    "VERTEX_WEIGHT_PROXIMITY",
    "ARRAY",
    "BEVEL",
    "BOOLEAN",
    "BUILD",
    "DECIMATE",
    "EDGE_SPLIT",
    "NODES",
    "MASK",
    "MIRROR",
    "MESH_TO_VOLUME",
    "MULTIRES",
    "REMESH",
    "SCREW",
    "SKIN",
    "SOLIDIFY",
    "SUBSURF",
    "TRIANGULATE",
    "VOLUME_TO_MESH",
    "WELD",
    "WIREFRAME",
    "ARMATURE",
    "CAST",
    "CURVE",
    "DISPLACE",
    "HOOK",
    "LAPLACIANDEFORM",
    "LATTICE",
    "MESH_DEFORM",
    "SHRINKWRAP",
    "SIMPLE_DEFORM",
    "SMOOTH",
    "CORRECTIVE_SMOOTH",
    "LAPLACIANSMOOTH",
    "SURFACE_DEFORM",
    "WARP",
    "WAVE",
    "VOLUME_DISPLACE",
    "CLOTH",
    "COLLISION",
    "DYNAMIC_PAINT",
    "EXPLODE",
    "FLUID",
    "OCEAN",
    "PARTICLE_INSTANCE",
    "PARTICLE_SYSTEM",
    "SOFT_BODY",
    "SURFACE",
]
