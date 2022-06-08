import bpy

from .base_clothing import BaseClothing


class OutfitSettings(BaseClothing):
    def __init__(self, human):
        self._human = human

    @property
    def objects(self):
        return [obj for obj in self._human.objects if "cloth" in obj]
