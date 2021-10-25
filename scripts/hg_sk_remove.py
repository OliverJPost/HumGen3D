import os

import bpy  # type:ignore

for obj in bpy.data.objects:
    try:
        for sk in [sk for sk in obj.data.shape_keys.key_blocks]:
            obj.shape_key_remove(sk)
    except:
        pass
    
bpy.ops.wm.save_mainfile()

blend1_file = bpy.data.filepath.replace('.blend', '.blend1')

try:
    os.remove(blend1_file)
except OSError:
    pass
