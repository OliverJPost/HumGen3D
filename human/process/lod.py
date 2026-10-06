"""Contain class for producing LODs for the meshes of a human."""

import json
import os
from typing import TYPE_CHECKING, Literal

import bmesh
import bpy
from HumGen3D.backend.preferences.preference_func import get_addon_root
from HumGen3D.common.context import context_override
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C
from HumGen3D.human.keys.keys import apply_shapekeys

if TYPE_CHECKING:
    from HumGen3D.human.human import Human


# Decimate ratio of the clothing meshes for every option of LodProps.clothing
CLOTHING_DECIMATE_RATIOS = {"original": 1.0, "high": 0.5, "medium": 0.25, "low": 0.1}
# Part of the triangles that is left for every option of the other meshes, as
# measured on the default human
BODY_TRIS_RATIOS = {0: 1.0, 1: 0.715, 2: 0.19}
EYES_TRIS_RATIOS = {"original": 1.0, "high": 0.34, "medium": 0.085, "low": 0.02}
TEETH_TRIS_RATIOS = {0: 1.0, 1: 0.37, 2: 0.27}
# Decimate ratios for the gums and tongue, the front teeth and the molars. The molars
# have the least geometry to start with, the gums are the least detailed.
TEETH_DECIMATE_RATIOS = {1: (0.25, 0.3, 0.5), 2: (0.15, 0.2, 0.35)}
# Triangle counts that tell the parts of the teeth meshes apart
GUMS_MIN_TRIS = 1000
FRONT_TEETH_MIN_TRIS = 300


class LodSettings:
    """Has methods for setting LODs for the meshes of a human."""

    def __init__(self, _human: "Human") -> None:
        self._human = _human

    def estimate_triangles(
        self,
        body_lod: Literal[0, 1, 2] = 0,
        clothing: str = "original",
        eyes: str = "original",
        teeth: Literal[0, 1, 2] = 0,
        remove_clothing_subdiv: bool = True,
        remove_clothing_solidify: bool = True,
    ) -> dict[str, int]:
        """Estimate the triangle count of the meshes after setting these LODs.

        Cheap enough to call while drawing the UI. The estimate ignores the parts of
        the body that are hidden under clothing.

        Args:
            body_lod (Literal[0, 1, 2]): See set_body_lod.
            clothing (str): Option of the clothing LOD, "original", "high", "medium"
                or "low".
            eyes (str): Detail of the game eyes, "original", "high", "medium" or
                "low".
            teeth (Literal[0, 1, 2]): See set_teeth_lod.
            remove_clothing_subdiv (bool): Whether subdivision modifiers are
                removed from the clothing.
            remove_clothing_solidify (bool): Whether solidify modifiers are removed
                from the clothing.

        Returns:
            dict[str, int]: Triangle count for "body", "clothing", "eyes" and
                "teeth".
        """
        objects = self._human.objects
        clothing_tris = 0
        for obj in self._human.clothing.outfit.objects + (
            self._human.clothing.footwear.objects
        ):
            tris = _mesh_tris(obj.data) * CLOTHING_DECIMATE_RATIOS[clothing]
            for mod in obj.modifiers:
                if mod.type == "SUBSURF" and not remove_clothing_subdiv:
                    tris *= 4**mod.levels
                elif mod.type == "SOLIDIFY" and not remove_clothing_solidify:
                    tris *= 2
            clothing_tris += tris

        return {
            "body": round(_mesh_tris(objects.body.data) * BODY_TRIS_RATIOS[body_lod]),
            "clothing": round(clothing_tris),
            "eyes": round(_mesh_tris(objects.eyes.data) * EYES_TRIS_RATIOS[eyes]),
            "teeth": round(
                (
                    _mesh_tris(objects.upper_teeth.data)
                    + _mesh_tris(objects.lower_teeth.data)
                )
                * TEETH_TRIS_RATIOS[teeth]
            ),
        }

    @injected_context
    def set_body_lod(self, lod: Literal[0, 1, 2], context: C = None) -> None:
        """Set the LOD of the body mesh.

        Args:
            lod (Literal[0, 1, 2]): LOD to set the body mesh to. 0 means no difference,
                1 means lower polycount in the face and 2 means lower polycount in the
                whole body.
            context (C): Blender context. bpy.context if not provided.

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
        self._human.hair.set_connected(False, context)
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
        self._human.hair.set_connected(True, context)

    @injected_context
    def set_clothing_lod(
        self,
        decimate_ratio: float = 0.15,
        remove_subdiv: bool = True,
        remove_solidify: bool = True,
        keep_shape_keys: bool = False,
        context: C = None,
    ) -> None:
        """Set the LOD of the clothing meshes by decimating them.

        Args:
            decimate_ratio (float): Ratio of decimation. Defaults to 0.15.
            remove_subdiv (bool): Whether to remove subdivision modifiers.
            remove_solidify (bool): Whether to remove solidify modifiers.
            keep_shape_keys (bool): Decimate the shape keys of the clothing along
                with the mesh, instead of applying them first. Slower.
        """
        from HumGen3D.human.process.apply_modifiers import (
            apply_topology_changing_modifiers,
        )

        clothing_objs = (
            self._human.clothing.outfit.objects + self._human.clothing.footwear.objects
        )

        for obj in clothing_objs:
            if decimate_ratio < 1.0:
                dec_mod = obj.modifiers.new("Decimate", "DECIMATE")
                dec_mod.ratio = decimate_ratio
                if keep_shape_keys and obj.data.shape_keys:
                    apply_topology_changing_modifiers(
                        context, {"DECIMATE"}, obj, self._human
                    )
                else:
                    apply_shapekeys(obj)
                    with context_override(context, obj, [obj]):
                        bpy.ops.object.modifier_apply(modifier=dec_mod.name)

            for mod in obj.modifiers[:]:
                if (mod.type == "SUBSURF" and remove_subdiv) or (
                    mod.type == "SOLIDIFY" and remove_solidify
                ):
                    obj.modifiers.remove(mod)

    @injected_context
    def set_teeth_lod(self, lod: Literal[0, 1, 2], context: C = None) -> None:
        """Set the LOD of the teeth meshes by decimating them.

        The gums, front teeth and molars are decimated separately, so every tooth
        keeps its shape. The shape keys of the tongue are kept.

        Args:
            lod (Literal[0, 1, 2]): LOD to set the teeth to. 0 means no difference,
                1 leaves about 4,600 triangles and 2 about 3,300.
            context (C): Blender context. bpy.context if not provided.

        Raises:
            ValueError: If the teeth already have a lower level of detail, as they
                can only be decimated from their original resolution.
        """
        teeth_objs = (self._human.objects.upper_teeth, self._human.objects.lower_teeth)
        if any(obj.get("hg_lod") for obj in teeth_objs):
            raise ValueError("The teeth already have a lower level of detail.")
        if lod == 0:
            return

        old_active = context.view_layer.objects.active
        old_selected = context.selected_objects
        for obj in old_selected:
            obj.select_set(False)

        for obj in teeth_objs:
            obj.select_set(True)
            context.view_layer.objects.active = obj
            _decimate_teeth(obj, TEETH_DECIMATE_RATIOS[lod])
            obj.select_set(False)
            obj["hg_lod"] = lod

        for obj in old_selected:
            obj.select_set(True)
        context.view_layer.objects.active = old_active


def _mesh_tris(mesh: bpy.types.Mesh) -> int:
    # Every polygon with n corners has n - 2 triangles
    return len(mesh.loops) - 2 * len(mesh.polygons)


def _decimate_teeth(obj: bpy.types.Object, ratios: tuple[float, float, float]) -> None:
    gums_ratio, front_teeth_ratio, molars_ratio = ratios
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="FACE")

    # Smallest parts first, so the other parts still have their original size
    for min_tris, max_tris, ratio in (
        (0, FRONT_TEETH_MIN_TRIS, molars_ratio),
        (FRONT_TEETH_MIN_TRIS, GUMS_MIN_TRIS, front_teeth_ratio),
        (GUMS_MIN_TRIS, float("inf"), gums_ratio),
    ):
        bpy.ops.mesh.select_all(action="DESELECT")
        bm = bmesh.from_edit_mesh(obj.data)
        for island in _get_face_islands(bm):
            tris_count = sum(len(face.verts) - 2 for face in island)
            if min_tris <= tris_count < max_tris:
                for face in island:
                    face.select_set(True)
        bmesh.update_edit_mesh(obj.data)
        # Works in edit mode because that keeps the shape keys, unlike the modifier
        bpy.ops.mesh.decimate(ratio=ratio)

    bpy.ops.object.mode_set(mode="OBJECT")

    # The custom normals don't match the changed topology
    custom_normals = obj.data.attributes.get("custom_normal")
    if custom_normals:
        obj.data.attributes.remove(custom_normals)


def _get_face_islands(bm: bmesh.types.BMesh) -> list[list[bmesh.types.BMFace]]:
    islands = []
    visited = set()
    for start_face in bm.faces:
        if start_face in visited:
            continue
        visited.add(start_face)
        island = []
        stack = [start_face]
        while stack:
            face = stack.pop()
            island.append(face)
            for vert in face.verts:
                for other_face in vert.link_faces:
                    if other_face not in visited:
                        visited.add(other_face)
                        stack.append(other_face)
        islands.append(island)

    return islands
