# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy

from .base_clothing import BaseClothing


class OutfitSettings(BaseClothing):
    def __init__(self, human):
        self._human = human
        self._pcoll_name = "outfits"
        self._pcoll_gender_split = True

    @property
    def objects(self):
        return [obj for obj in self._human.objects if "cloth" in obj]
