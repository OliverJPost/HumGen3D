import json
import sys

import bpy  # type:ignore

print('################ IGNORE ERRORS ABOVE THIS LINE ####################')

bpy.context.scene.HG3D.active_ui_tab = 'BATCH'
settings_dict =  json.loads(sys.argv[4])

for obj in bpy.data.objects[:]:
    bpy.data.objects.remove(obj)

bpy.context.scene.render.use_simplify = True
bpy.context.scene.render.simplify_child_particles = 0

bpy.ops.hg3d.quick_generate(**settings_dict)

hg_rig = next(obj for obj in bpy.data.objects if obj.HG.ishuman)

bpy.ops.wm.save_as_mainfile(filepath = '/Users/olepost/Documents/Humgen_Files_Main/batch_result.blend')
