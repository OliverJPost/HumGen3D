# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import os

import bpy  # type:ignore


def main():
    for obj in bpy.data.objects:
        try:
            for sk in [sk for sk in obj.data.shape_keys.key_blocks]:
                obj.shape_key_remove(sk)
        except Exception:
            pass

    bpy.ops.wm.save_mainfile()

    blend1_file = bpy.data.filepath.replace(".blend", ".blend1")

    try:
        os.remove(blend1_file)
    except OSError:
        pass


if __name__ == "__main__":
    main()
