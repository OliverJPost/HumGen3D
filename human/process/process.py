# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE


import json
import os
from typing import TYPE_CHECKING, Literal

import bmesh
from HumGen3D.backend.preferences.preference_func import get_addon_root

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

from .bake import BakeSettings


class ProcessSettings:
    def __init__(self, human: "Human") -> None:
        self._human = human

    @property
    def baking(self) -> BakeSettings:
        return BakeSettings(self._human)

    def set_lod(self, lod: Literal[0, 1, 2]) -> None:
        body_obj = self._human.body_obj
        current_lod = body_obj["hg_lod"] if "hg_lod" in body_obj else 0
        if current_lod > lod:
            raise ValueError(
                (
                    "New LOD level has to be higher than original current"
                    + f"[{current_lod}] LOD level."
                )
            )
        self._human.hair.set_connected(False)
        bm = bmesh.new()  # type:ignore[call-arg]
        bm.from_mesh(body_obj.data)

        directory = os.path.join(get_addon_root(), "human", "process")

        edge_files = []
        if lod >= 1 and current_lod == 0:
            edge_files.extend(["edges.json", "collar_edges.json"])
        if lod >= 2 and current_lod < 2:
            edge_files.append("lod2.json")

        for edge_file in edge_files:
            with open(os.path.join(directory, edge_file), "r") as f:
                edge_idxs = set(json.load(f))

            edges_to_dissolve = [edge for edge in bm.edges if edge.index in edge_idxs]

            bmesh.ops.dissolve_edges(
                bm, edges=edges_to_dissolve, use_verts=True, use_face_split=True
            )

        bm.to_mesh(body_obj.data)
        bm.free()
        body_obj["hg_lod"] = lod
        self._human.hair.set_connected(True)
