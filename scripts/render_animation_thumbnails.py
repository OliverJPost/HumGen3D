# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Renders a thumbnail for every animation clip in the content folder.

Run headless with the Human Generator add-on enabled:

    blender -b --python render_animation_thumbnails.py -- [--overwrite] [--outfit PATH]

A male human is created and every clip is applied to it. A representative frame
is rendered to a jpg next to the clip, which the preview collection uses as icon.
"""

import math
import os
import sys

import bpy
import numpy as np
from HumGen3D.backend import get_prefs
from HumGen3D.human.human import Human
from mathutils import Vector

THUMB_SIZE = 256
PRESET = "models/male/Caucasian/David.json"
OUTFIT = "outfits/male/Summer/Beach_Day.blend"
# Fraction of the clip to render, by words in the clip name. Entering animations
# end in the interesting pose, exiting ones start in it.
FRAME_FRACTIONS = {"Enter": 0.9, "Death": 0.95, "Land": 0.9, "Exit": 0.1, "Start": 0.3}
DEFAULT_FRACTION = 0.4


def frame_fraction(clip_name: str) -> float:
    for word, fraction in FRAME_FRACTIONS.items():
        if word in clip_name:
            return fraction
    return DEFAULT_FRACTION


def setup_scene(context: bpy.types.Context) -> bpy.types.Object:
    scene = context.scene
    engines = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
    scene.render.engine = next(
        e.identifier for e in engines if e.identifier.startswith("BLENDER_EEVEE")
    )
    scene.render.resolution_x = scene.render.resolution_y = THUMB_SIZE
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 90
    scene.render.film_transparent = False
    scene.render.fps = 30
    world = bpy.data.worlds.new("Thumbnail World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0, 0, 0, 1)

    cam = bpy.data.objects.new("Thumbnail Camera", bpy.data.cameras.new("Camera"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens = 50

    for name, rotation, energy in (
        ("Key", (50, 0, 35), 3.0),
        ("Fill", (60, 0, -60), 1.0),
        ("Rim", (-50, 0, 180), 2.0),
    ):
        light = bpy.data.objects.new(name, bpy.data.lights.new(name, "SUN"))
        light.data.energy = energy
        light.data.angle = math.radians(20)
        light.rotation_euler = [math.radians(r) for r in rotation]
        scene.collection.objects.link(light)

    return cam


def frame_human(
    context: bpy.types.Context, human: Human, cam: bpy.types.Object
) -> None:
    """Points the camera at the human so the whole body fits in the frame."""
    depsgraph = context.evaluated_depsgraph_get()
    depsgraph.update()
    body = human.objects.body.evaluated_get(depsgraph)
    coords = np.empty(len(body.data.vertices) * 3)
    body.data.vertices.foreach_get("co", coords)
    rotation = np.array(body.matrix_world.to_3x3())
    translation = np.array(body.matrix_world.translation)
    coords = coords.reshape((-1, 3)) @ rotation.T + translation
    center = Vector((coords.min(axis=0) + coords.max(axis=0)) / 2)
    radius = max(np.linalg.norm(coords - np.array(center), axis=1))

    fov = cam.data.angle
    distance = radius / math.sin(fov / 2) * 1.05
    direction = Vector((0.45, -1, 0.3)).normalized()
    cam.location = center + direction * distance
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    overwrite = "--overwrite" in args
    outfit = args[args.index("--outfit") + 1] if "--outfit" in args else OUTFIT

    bpy.ops.wm.read_homefile(use_empty=True)
    context = bpy.context
    cam = setup_scene(context)
    human = Human.from_preset(PRESET, context)
    if outfit:
        human.clothing.outfit.set(outfit, context)

    animations_dir = os.path.join(get_prefs().filepath, "animations")
    for root, _, files in os.walk(animations_dir):
        for file_name in sorted(files):
            if not file_name.endswith(".json"):
                continue
            path = os.path.join(root, file_name)
            thumb_path = os.path.splitext(path)[0] + ".jpg"
            if os.path.exists(thumb_path) and not overwrite:
                continue

            human.animation.set(os.path.relpath(path, get_prefs().filepath), context)
            scene = context.scene
            frames = scene.frame_end - scene.frame_start
            frame = scene.frame_start + round(frame_fraction(file_name) * frames)
            scene.frame_set(frame)
            frame_human(context, human, cam)
            scene.render.filepath = thumb_path
            bpy.ops.render.render(write_still=True)
            print("Rendered", os.path.relpath(thumb_path, animations_dir))


if __name__ == "__main__":
    main()
