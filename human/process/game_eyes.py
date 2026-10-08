# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Implements converting the eyes of a human to single layer eyes for game engines."""

import math
from typing import TYPE_CHECKING, Iterable

import bmesh
import bpy
from HumGen3D.common import is_legacy
from HumGen3D.common.exceptions import HumGenException
from HumGen3D.common.objects import remove_all_shapekeys
from HumGen3D.human.hair.compatibility import (
    SPECULAR_INPUT_NAME,
    SUBSURFACE_INPUT_NAME,
)
from mathutils import Vector

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

# Amount of times the resolution of the eye mesh is halved
DETAIL_LEVELS = {"high": 0, "medium": 1, "low": 2}
# Faces further than this from the looking direction of the eye are removed. Up to
# 60 degrees is visible between the eyelids, the rest is margin for eye rotation.
VISIBLE_ANGLE = math.radians(110)
# The eye is a single opaque surface, the low roughness replaces the glossy cornea
ROUGHNESS = 0.1
CORNEA_SLOT = 0
EYEBALL_SLOT = 1
LOOKAT_BONE_PREFIX = "eyeball_lookat"
# Set on the rig once the eyes are converted
GAME_EYES_KEY = "game_eyes"


def convert_to_game_eyes(human: "Human", detail: str = "medium") -> None:
    """Replaces the layered eyes of this human by single layer eyes.

    Only the front of the cornea is kept, with the eye color as opaque material on
    it. The shape keys of the eyes are applied.

    Args:
        human (Human): Human to convert the eyes of.
        detail (str): Resolution of the eye mesh, "high", "medium" or "low".

    Raises:
        HumGenException: If the human is a legacy human or already has game eyes.
        ValueError: If the detail level does not exist.
    """
    if detail not in DETAIL_LEVELS:
        raise ValueError(f"Detail has to be one of {tuple(DETAIL_LEVELS)}")
    if is_legacy(human.objects.rig):
        raise HumGenException("Can't convert the eyes of a legacy human.")
    if human.process.has_game_eyes:
        raise HumGenException("Human already has game eyes.")

    eyes = human.objects.eyes
    _apply_shape_keys(eyes)
    _simplify_mesh(eyes.data, DETAIL_LEVELS[detail])
    _set_single_material(eyes.data)

    # The eyes are aimed by the engine, these bones only exist as constraint targets
    for pose_bone in human.objects.rig.pose.bones:
        original_name = pose_bone.get("original_name", pose_bone.name)
        if original_name.startswith(LOOKAT_BONE_PREFIX):
            pose_bone.bone.use_deform = False

    human.objects.rig[GAME_EYES_KEY] = True


def _apply_shape_keys(eyes: bpy.types.Object) -> None:
    if not eyes.data.shape_keys:
        return

    mix = eyes.shape_key_add(name="hg_mix", from_mix=True)
    remove_all_shapekeys(eyes, apply_last=mix.name)


def _simplify_mesh(mesh: bpy.types.Mesh, unsubdivide_levels: int) -> None:
    bm = bmesh.new()
    bm.from_mesh(mesh)

    eyeball_faces = [face for face in bm.faces if face.material_index != CORNEA_SLOT]
    bmesh.ops.delete(bm, geom=eyeball_faces, context="FACES")

    # Has to be found before the vertex in the middle of the cornea can be removed
    eye_orientations = _get_eye_orientations(bm)
    # Lowering the resolution would otherwise create faces spanning two UV islands
    _extend_front_uv_island(bm, eye_orientations)

    if unsubdivide_levels:
        bmesh.ops.unsubdivide(bm, verts=bm.verts, iterations=unsubdivide_levels * 2)

    hidden_faces = []
    for face in bm.faces:
        center = face.calc_center_median()
        orientation = min(
            eye_orientations, key=lambda orientation: (center - orientation[0]).length
        )
        if _angle_from_pupil(center, orientation) > VISIBLE_ANGLE:
            hidden_faces.append(face)
    bmesh.ops.delete(bm, geom=hidden_faces, context="FACES")

    for face in bm.faces:
        face.smooth = True

    bm.to_mesh(mesh)
    bm.free()

    # The custom normals don't match the changed topology, a sphere doesn't need them
    custom_normals = mesh.attributes.get("custom_normal")
    if custom_normals:
        mesh.attributes.remove(custom_normals)
    mesh.update()


def _get_eye_orientations(bm: bmesh.types.BMesh) -> list[tuple[Vector, Vector]]:
    """Finds the center and looking direction of each eye in the mesh.

    Args:
        bm (BMesh): Mesh of the eyes, with only the cornea shells left.

    Returns:
        list[tuple[Vector, Vector]]: Center and looking direction per eye.
    """
    uv_layer = bm.loops.layers.uv.verify()
    uv_center = Vector((0.5, 0.5))

    orientations = []
    for island in _get_islands(bm):
        centroid = sum((vert.co for vert in island), Vector()) / len(island)
        # The pupil is in the middle of the texture
        pupil_vert = min(
            island,
            key=lambda vert: min(
                (loop[uv_layer].uv - uv_center).length for loop in vert.link_loops
            ),
        )
        direction = (pupil_vert.co - centroid).normalized()

        # The cornea bulges out, so the radius is measured sideways and from the back
        offsets = [vert.co - centroid for vert in island]
        radius = max(
            (offset - direction * offset.dot(direction)).length for offset in offsets
        )
        back = min(offset.dot(direction) for offset in offsets)
        orientations.append((centroid + direction * (back + radius), direction))

    return orientations


def _extend_front_uv_island(
    bm: bmesh.types.BMesh, eye_orientations: list[tuple[Vector, Vector]]
) -> None:
    """Gives the faces behind the UV seam the UVs of the edge of the front island.

    The front of the eye is one UV island, the back is a separate smaller one. The
    part of the back that is kept gets the color of the edge of the front, so the
    seam and the back island are not needed anymore.

    Args:
        bm (BMesh): Mesh of the eyes, with only the cornea shells left.
        eye_orientations (list[tuple[Vector, Vector]]): Center and looking direction
            per eye, in the same order as the islands of the mesh.
    """
    uv_layer = bm.loops.layers.uv.verify()

    for island, orientation in zip(_get_islands(bm), eye_orientations):
        seam_verts = {
            vert
            for vert in island
            if len({loop[uv_layer].uv.to_tuple(4) for loop in vert.link_loops}) > 1
        }
        if not seam_verts:
            continue
        seam_angle = sum(
            _angle_from_pupil(vert.co, orientation) for vert in seam_verts
        ) / len(seam_verts)

        front_uvs = {}
        back_loops = []
        for face in {face for vert in island for face in vert.link_faces}:
            center = face.calc_center_median()
            is_front = _angle_from_pupil(center, orientation) < seam_angle
            for loop in face.loops:
                if not is_front:
                    back_loops.append(loop)
                elif loop.vert in seam_verts:
                    front_uvs[loop.vert] = loop[uv_layer].uv.copy()

        for loop in back_loops:
            loop[uv_layer].uv = front_uvs[_get_nearest_vert(front_uvs, loop.vert.co)]


def _angle_from_pupil(position: Vector, orientation: tuple[Vector, Vector]) -> float:
    eye_center, direction = orientation
    return (position - eye_center).angle(direction)


def _get_nearest_vert(
    verts: Iterable[bmesh.types.BMVert], position: Vector
) -> bmesh.types.BMVert:
    return min(verts, key=lambda vert: (vert.co - position).length)


def _get_islands(bm: bmesh.types.BMesh) -> list[list[bmesh.types.BMVert]]:
    islands = []
    visited = set()
    for start_vert in bm.verts:
        if start_vert in visited:
            continue
        visited.add(start_vert)
        island = []
        stack = [start_vert]
        while stack:
            vert = stack.pop()
            island.append(vert)
            for edge in vert.link_edges:
                other_vert = edge.other_vert(vert)
                if other_vert not in visited:
                    visited.add(other_vert)
                    stack.append(other_vert)
        islands.append(island)

    return islands


def _set_single_material(mesh: bpy.types.Mesh) -> None:
    old_materials = list(mesh.materials)
    material = old_materials[EYEBALL_SLOT]

    mesh.materials.clear()
    mesh.materials.append(material)
    for polygon in mesh.polygons:
        polygon.material_index = 0
    for old_material in old_materials:
        if old_material and old_material != material and not old_material.users:
            bpy.data.materials.remove(old_material)

    node_tree = material.node_tree
    principled = next(
        node for node in node_tree.nodes if node.bl_idname == "ShaderNodeBsdfPrincipled"
    )
    principled.inputs["Roughness"].default_value = ROUGHNESS
    principled.inputs["Metallic"].default_value = 0
    principled.inputs[SPECULAR_INPUT_NAME].default_value = 0.5
    # Subsurface scattering is not part of the materials exported to game engines
    principled.inputs[SUBSURFACE_INPUT_NAME].default_value = 0
    # The normal map of the iris is made for the hollow iris of the eyeball
    for link in principled.inputs["Normal"].links:
        node_tree.links.remove(link)
