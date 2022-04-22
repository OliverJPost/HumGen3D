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


remove_broken_drivers()

bpy.ops.wm.save_mainfile()
print('test2')
blend1_file = bpy.data.filepath.replace(".blend", ".blend1")

try:
    os.remove(blend1_file)
except OSError:
    pass

bpy.ops.wm.quit_blender()
