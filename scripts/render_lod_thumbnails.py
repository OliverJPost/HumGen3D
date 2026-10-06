# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""Render the wireframe thumbnails shown in the Optimize Meshes pickers.

Writes user_interface/icons/lod_{body,clothing,eyes,teeth}_<option>.png and
haircards_<quality>.png, one per option of the matching process property, and
prints the triangle count of every option. Run headless with the add-on enabled:
Blender -b --python scripts/render_lod_thumbnails.py
"""

import math
import os

import bpy
from HumGen3D.backend.preferences.preference_func import get_addon_root
from HumGen3D.human.human import Human
from HumGen3D.human.keys.keys import apply_shapekeys
from HumGen3D.human.process.lod import CLOTHING_DECIMATE_RATIOS
from mathutils import Vector

THUMB_SIZE = 256
OUT_DIR = os.path.join(get_addon_root(), "user_interface", "icons")
OUTFIT = "Casual_Weekday"
HAIR = "Medium Side Part"


def _setup_scene(scene):
    body_mat = bpy.data.materials.new("thumb_body")
    body_mat.diffuse_color = (0.86, 0.86, 0.86, 1.0)
    wire_mat = bpy.data.materials.new("thumb_wire")
    wire_mat.diffuse_color = (0.08, 0.08, 0.08, 1.0)

    cam_data = bpy.data.cameras.new("thumb_cam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("thumb_cam", cam_data)
    scene.collection.objects.link(cam)
    cam.rotation_euler = (math.radians(90), 0, 0)
    scene.camera = cam

    # Workbench is fast and needs no lights
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_cavity = False
    scene.display.shading.show_shadows = False
    scene.render.resolution_x = scene.render.resolution_y = THUMB_SIZE
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "Standard"
    scene.world = bpy.data.worlds.new("thumb_world")
    scene.world.color = (0.16, 0.16, 0.16)

    return cam, body_mat, wire_mat


def _world_coords(objs):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    coords = []
    for obj in objs:
        eval_obj = obj.evaluated_get(depsgraph)
        coords.extend(obj.matrix_world @ v.co for v in eval_obj.data.vertices)
    return coords


def _aim_camera(cam, center, size, angle=0.0):
    """Point the orthographic camera at center, angle radians to the right of the
    front view."""
    cam.location = center + Vector((2.0 * math.sin(angle), -2.0 * math.cos(angle), 0))
    cam.rotation_euler = (math.radians(90), 0, angle)
    cam.data.ortho_scale = size


def _bounds(objs):
    coords = _world_coords(objs)
    low = Vector(map(min, zip(*coords)))
    high = Vector(map(max, zip(*coords)))
    return (low + high) / 2, high - low


def _render_wireframe(
    scene, objs, filepath, body_mat, wire_mat, wire_thickness, solid_objs=()
):
    """Render objs as flat solids with a wireframe on top, as the eye sees them.
    The solid_objs are rendered without wireframe, as context."""
    copies = []
    for obj in list(solid_objs) + list(objs):
        # A solid copy with a flat material, and a wireframe copy on top of it
        solid = obj.copy()
        solid.data = obj.data.copy()
        solid.data.materials.clear()
        solid.data.materials.append(body_mat)
        for poly in solid.data.polygons:
            poly.material_index = 0
        solid.parent = None
        solid.matrix_world = obj.matrix_world
        solid.hide_render = False
        for mod in solid.modifiers:
            if mod.type == "PARTICLE_SYSTEM":
                mod.show_render = False
        scene.collection.objects.link(solid)
        copies.append(solid)
        if obj in solid_objs:
            continue

        wire = solid.copy()
        wire.data = solid.data.copy()
        wire.data.materials.clear()
        wire.data.materials.append(wire_mat)
        wire_mod = wire.modifiers.new("Wire", "WIREFRAME")
        wire_mod.thickness = wire_thickness
        wire_mod.use_replace = True
        wire_mod.use_even_offset = False
        scene.collection.objects.link(wire)
        copies.append(wire)

    scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)

    for obj in copies:
        bpy.data.objects.remove(obj, do_unlink=True)


def _tris_count(objs):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    return sum(
        len(poly.vertices) - 2
        for obj in objs
        for poly in obj.evaluated_get(depsgraph).data.polygons
    )


def _render_body(human, context, scene, cam, mats):
    """Closeup of the face, where the first LOD level makes its difference."""
    body = human.objects.body
    for mod in body.modifiers:
        if mod.type == "SUBSURF":
            mod.show_render = False
    top_z = max(coord.z for coord in _world_coords([body]))
    _aim_camera(cam, Vector((0.0, 0.0, top_z - 0.125)), 0.25)

    for lod in (0, 1, 2):
        if lod > 0:
            human.process.lod.set_body_lod(lod, context=context)
        path = os.path.join(OUT_DIR, f"lod_body_{lod}.png")
        _render_wireframe(scene, [body], path, *mats, wire_thickness=0.001)
        print(f"TRIS body {lod}: {_tris_count([body])}")


def _render_clothing(human, context, scene, cam, mats):
    """The outfit from the front, decimated like set_clothing_lod does it."""
    options = human.clothing.outfit.get_options(context)
    chosen = next((opt for opt in options if OUTFIT in opt), options[0])
    human.clothing.outfit.set(chosen, context)
    objs = human.clothing.outfit.objects
    for obj in objs:
        obj.hide_render = True
        apply_shapekeys(obj)
        for mod in obj.modifiers[:]:
            if mod.type in ("SUBSURF", "SOLIDIFY"):
                obj.modifiers.remove(mod)

    # The whole outfit is too small to read, so frame the top garment
    top = max(objs, key=lambda obj: _bounds([obj])[0].z)
    center, size = _bounds([top])
    _aim_camera(cam, center, max(size) * 1.1)

    for option, ratio in CLOTHING_DECIMATE_RATIOS.items():
        mods = []
        if ratio < 1.0:
            for obj in objs:
                mod = obj.modifiers.new("Decimate", "DECIMATE")
                mod.ratio = ratio
                mods.append((obj, mod))
        path = os.path.join(OUT_DIR, f"lod_clothing_{option}.png")
        _render_wireframe(scene, objs, path, *mats, wire_thickness=0.002)
        print(f"TRIS clothing {option}: {_tris_count(objs)}")
        for obj, mod in mods:
            obj.modifiers.remove(mod)


def _render_eyes(human, context, scene, cam, mats):
    """Closeup of one eye from the side, showing that the game eyes are only the
    front of the eye. The conversion is irreversible, so the mesh is restored from
    a copy for every option."""
    eyes = human.objects.eyes
    original_mesh = eyes.data.copy()
    # The left eye of the human, on the right from the front
    eye_coords = [coord for coord in _world_coords([eyes]) if coord.x > 0]
    low = Vector(map(min, zip(*eye_coords)))
    high = Vector(map(max, zip(*eye_coords)))
    _aim_camera(cam, (low + high) / 2, max(high - low) * 1.2, math.radians(90))

    for option in ("original", "high", "medium", "low"):
        if option != "original":
            eyes.data = original_mesh.copy()
            human.process.convert_to_game_eyes(option)
        path = os.path.join(OUT_DIR, f"lod_eyes_{option}.png")
        _render_wireframe(scene, [eyes], path, *mats, wire_thickness=0.00012)
        print(f"TRIS eyes {option}: {_tris_count([eyes])}")
        human.objects.rig.pop("game_eyes", None)


def _render_teeth(human, context, scene, cam, mats):
    """Both teeth from the front. Decimating is irreversible, so the meshes are
    restored from copies for every option."""
    teeth = [human.objects.upper_teeth, human.objects.lower_teeth]
    original_meshes = [obj.data.copy() for obj in teeth]
    center, size = _bounds(teeth)
    _aim_camera(cam, center, max(size.x, size.z) * 1.1)

    for lod in (0, 1, 2):
        if lod > 0:
            for obj, mesh in zip(teeth, original_meshes):
                obj.data = mesh.copy()
                obj.pop("hg_lod", None)
            human.process.lod.set_teeth_lod(lod, context=context)
        path = os.path.join(OUT_DIR, f"lod_teeth_{lod}.png")
        _render_wireframe(scene, teeth, path, *mats, wire_thickness=0.0003)
        print(f"TRIS teeth {lod}: {_tris_count(teeth)}")


def _render_haircards(preset, context, scene, cam, mats):
    """Haircards on the head from the side. Converting is irreversible, so every
    quality gets a fresh human. Prints the triangle counts of the hair objects,
    which HairSettings.estimate_haircards_triangles is based on."""
    body_mat, wire_mat = mats
    for quality in ("ultra", "high", "medium", "low", "haircap_only"):
        human = Human.from_preset(preset, context=context)
        for obj in human.objects:
            obj.hide_render = True
        options = human.hair.regular_hair.get_options(context)
        chosen = next((opt for opt in options if HAIR in opt), options[0])
        human.hair.regular_hair.set(chosen, context)
        for mod in human.objects.body.modifiers:
            if mod.type == "SUBSURF":
                mod.show_render = False

        hair_objs = []
        hair_types = human.hair.regular_hair, human.hair.eyebrows, human.hair.eyelashes
        if human.hair.face_hair.modifiers:
            hair_types += (human.hair.face_hair,)
        for hair in hair_types:
            hair_objs.append(hair.convert_to_haircards(quality, context))
            print(f"TRIS haircards {quality} {hair._haircap_type}: "
                  f"{_tris_count(hair_objs[-1:])}")

        body = human.objects.body
        top_z = max(coord.z for coord in _world_coords([body]))
        _aim_camera(cam, Vector((0.0, 0.0, top_z - 0.09)), 0.36, math.radians(60))
        path = os.path.join(OUT_DIR, f"haircards_{quality}.png")
        _render_wireframe(
            scene, hair_objs, path, body_mat, wire_mat, 0.0015, solid_objs=[body]
        )
        human.delete()


def main():
    context = bpy.context
    scene = context.scene
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    preset = Human.get_preset_options("male", context=context)[0]
    human = Human.from_preset(preset, context=context)
    # Only the copies made per option are rendered
    for obj in human.objects:
        obj.hide_render = True

    cam, *mats = _setup_scene(scene)
    _render_eyes(human, context, scene, cam, mats)
    _render_teeth(human, context, scene, cam, mats)
    _render_body(human, context, scene, cam, mats)
    _render_clothing(human, context, scene, cam, mats)
    human.delete()
    _render_haircards(preset, context, scene, cam, mats)


if __name__ == "__main__":
    main()
