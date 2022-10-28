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
