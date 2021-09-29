import bpy #type:ignore
import random
import os 
import sys
import json

print('################ IGNORE ERRORS ABOVE THIS LINE ####################')

bpy.context.scene.HG3D.active_ui_tab = 'BATCH'
settings_dict =  json.loads(sys.argv[4])

for obj in bpy.data.objects[:]:
    bpy.data.objects.remove(obj)

bpy.ops.hg3d.quick_generate(**settings_dict)

hg_rig = next(obj for obj in bpy.data.objects if obj.HG.ishuman)

backup_rig = hg_rig.HG.backup
for obj in backup_rig.children[:]:
    bpy.data.objects.remove(obj)
    
bpy.data.objects.remove(backup_rig)

bpy.ops.wm.save_as_mainfile(filepath = '/Users/olepost/Documents/Humgen_Files_Main/batch_result.blend')
