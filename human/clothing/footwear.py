import bpy

from .base_clothing import BaseClothing


class FootwearSettings(BaseClothing):
    def __init__(self, human):
        self._human = human
        self._pcoll_name = "footwear"
        self._pcoll_gender_split = True

    @property
    def objects(self):
        return [obj for obj in self._human.objects if "shoe" in obj]
