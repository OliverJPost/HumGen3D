# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import contextlib
import os

import bpy  # type:ignore


def remove_broken_drivers():
    """Credits to batFINGER for this solution"""
    for sk in bpy.data.shape_keys:
        if not sk.animation_data:
            continue
        broken_drivers = []

        for d in sk.animation_data.drivers:
            try:
                sk.path_resolve(d.data_path)
            except ValueError:
                broken_drivers.append(d)

        while broken_drivers:
            sk.animation_data.drivers.remove(broken_drivers.pop())


def main():
    remove_broken_drivers()

    bpy.ops.wm.save_mainfile()
    blend1_file = bpy.data.filepath.replace(".blend", ".blend1")

    with contextlib.suppress(OSError):
        os.remove(blend1_file)

    bpy.ops.wm.quit_blender()


if __name__ == "__main__":
    main()
