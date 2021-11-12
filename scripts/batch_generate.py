import json
import os
import sys
import tempfile

import bpy

bpy.context.scene.HG3D.active_ui_tab = 'BATCH'
settings_dict =  json.loads(sys.argv[4])

for obj in bpy.data.objects[:]:
    bpy.data.objects.remove(obj)

bpy.context.scene.render.use_simplify = True
bpy.context.scene.render.simplify_child_particles = 0

bpy.ops.hg3d.quick_generate(**settings_dict)

hg_rig = next(obj for obj in bpy.data.objects if obj.HG.ishuman)

hg_addon = next(addon for addon in bpy.context.preferences.addons 
                if 'humgen' in addon.module.lower()
                )

full_path = os.path.join(hg_addon.preferences.filepath, 'batch_result.blend')
bpy.ops.wm.save_as_mainfile(filepath = full_path)
