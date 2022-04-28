import bpy
from .base_clothing import BaseClothing


class OutfitSettings(BaseClothing):
    def __init__(self, human):
        self._human = human
