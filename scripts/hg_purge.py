import os

import bpy  # type: ignore

for obj in bpy.data.objects[:]:
    if not bpy.context.scene.objects.get(obj.name):
        bpy.data.objects.remove(obj)

override = bpy.context.copy()
override["area.type"]    = ['OUTLINER']
override["display_mode"] = ['ORPHAN_DATA']
for i in range(8):
    bpy.ops.outliner.orphans_purge(override) 

bpy.ops.file.make_paths_relative()

bpy.ops.wm.save_mainfile()

blend1_file = bpy.data.filepath.replace('.blend', '.blend1')

try:
    os.remove(blend1_file)
except OSError:
    pass
