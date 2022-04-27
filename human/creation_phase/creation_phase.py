from typing import TYPE_CHECKING

import bpy

from .body.body import BodySettings
from .face.face import FaceKeys
from .length.length import LengthSettings

# if TYPE_CHECKING:
#     from HumGen3D import Human


class CreationPhaseSettings:
    def __init__(self, human):
        self._human: Human = human

    @property
    def body(self) -> BodySettings:
        if not hasattr(self, "_body"):
            self._body = BodySettings(self._human)
        return self._body

    @property
    def length(self) -> LengthSettings:
        if not hasattr(self, "_length"):
            self._length = LengthSettings(self._human)
        return self._length

    @property
    def face(self) -> FaceKeys:
        if not hasattr(self, "_face"):
            self._face = FaceKeys(self._human)
        return self._face
