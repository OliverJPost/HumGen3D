# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import contextlib
import os

import bpy  # type:ignore


def main():
    for obj in bpy.data.objects:
        with contextlib.suppress(Exception):
            for sk in obj.data.shape_keys.key_blocks:
                obj.shape_key_remove(sk)

    bpy.ops.wm.save_mainfile()

    blend1_file = bpy.data.filepath.replace(".blend", ".blend1")

    with contextlib.suppress(OSError):
        os.remove(blend1_file)


if __name__ == "__main__":
    main()
