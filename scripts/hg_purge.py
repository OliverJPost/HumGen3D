# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import contextlib
import os

import bpy  # type: ignore


def main():
    for obj in bpy.data.objects[:]:
        if not bpy.context.scene.objects.get(obj.name):
            bpy.data.objects.remove(obj)

    # Passing a context override dict to an operator was removed in Blender 4.0.
    # The purge no longer needs an outliner, recursive covers nested orphans.
    bpy.ops.outliner.orphans_purge(
        do_local_ids=True, do_linked_ids=True, do_recursive=True
    )

    bpy.ops.file.make_paths_relative()

    bpy.ops.wm.save_mainfile()

    blend1_file = bpy.data.filepath.replace(".blend", ".blend1")

    with contextlib.suppress(OSError):
        os.remove(blend1_file)


if __name__ == "__main__":
    main()
