import bpy

from .bake import BakeSettings


class ProcessSettings:
    def __init__(self, human) -> None:
        self._human = human

    @property
    def baking(self) -> BakeSettings:
        return BakeSettings(self._human)
