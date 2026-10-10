# export_characters.py  (as documented on docs/Process/Python API.md, folder changed)
import bpy
from HumGen3D import Human
from HumGen3D.common import find_multiple_in_list
from HumGen3D.human.process.settings import ExportSettings

settings = ExportSettings.from_recipe("godot")
settings.output.folder = "/private/tmp/claude-501/-Users-ole-Library-Application-Support-Blender-5-1-scripts-addons-HumGen3D/5ebc58cb-da65-4b6f-877e-45bb0cebb7ab/scratchpad/bl/out/godot"

for rig in find_multiple_in_list(bpy.context.scene.objects):
    human = Human.from_existing(rig)
    result = human.process.run(settings, context=bpy.context)
    print(result.summary())
    print("FILES", result.files, "SECONDS", round(result.seconds, 1))
