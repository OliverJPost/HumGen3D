"""Contain class for producing LODs for the meshes of a human."""

import json
import os
from typing import TYPE_CHECKING, Literal

import bmesh
import bpy
from human.keys.keys import apply_shapekeys
from HumGen3D.backend.preferences.preference_func import get_addon_root
from HumGen3D.common.context import context_override
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C

if TYPE_CHECKING:
    from HumGen3D.human.human import Human


class LodSettings:
    """Has methods for setting LODs for the meshes of a human."""

    def __init__(self, _human: "Human") -> None:
        self._human = _human

    def set_body_lod(self, lod: Literal[0, 1, 2]) -> None:
        """Set the LOD of the body mesh.

        Args:
            lod (Literal[0, 1, 2]): LOD to set the body mesh to. 0 means no difference,
                1 means lower polycount in the face and 2 means lower polycount in the
                whole body.

        Raises:
            ValueError: If you pass a LOD value higher than the one the human currently
                has. At this moment it's not possible to revert LODs.
        """
        body_obj = self._human.objects.body
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

    @injected_context
    def set_clothing_lod(
        self,
        decimate_ratio: float = 0.15,
        remove_subdiv: bool = True,
        remove_solidify: bool = True,
        context: C = None,
    ) -> None:
        """Set the LOD of the clothing meshes by decimating them.

        Args:
            decimate_ratio (float): Ratio of decimation. Defaults to 0.15.
            remove_subdiv (bool): Whether to remove subdivision modifiers.
            remove_solidify (bool): Whether to remove solidify modifiers.
        """
        clothing_objs = (
            self._human.clothing.outfit.objects + self._human.clothing.footwear.objects
        )

        for obj in clothing_objs:
            if decimate_ratio < 1.0:
                apply_shapekeys(obj)
                dec_mod = obj.modifiers.new("Decimate", "DECIMATE")
                dec_mod.ratio = decimate_ratio
                with context_override(context, obj, [obj]):
                    bpy.ops.object.modifier_apply(modifier=dec_mod.name)

            for mod in obj.modifiers[:]:
                if (mod.type == "SUBSURF" and remove_subdiv) or (
                    mod.type == "SOLIDIFY" and remove_solidify
                ):
                    obj.modifiers.remove(mod)
