# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import contextlib
import os

import bpy  # type: ignore


def main():
    for obj in bpy.data.objects[:]:
        if not bpy.context.scene.objects.get(obj.name):
            bpy.data.objects.remove(obj)

    override = bpy.context.copy()
    override["area.type"] = ["OUTLINER"]
    override["display_mode"] = ["ORPHAN_DATA"]
    for _ in range(8):
        bpy.ops.outliner.orphans_purge(override)

    bpy.ops.file.make_paths_relative()

    bpy.ops.wm.save_mainfile()

    blend1_file = bpy.data.filepath.replace(".blend", ".blend1")

    with contextlib.suppress(OSError):
        os.remove(blend1_file)


if __name__ == "__main__":
    main()
