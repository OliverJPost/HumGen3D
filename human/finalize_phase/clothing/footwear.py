import bpy
from .base_clothing import BaseClothing


class FootwearSettings(BaseClothing):
    def __init__(self, human):
        self._human = human
