import os
import subprocess

PATH = r"/Users/olepost/Documents/Humgen_Files_Main"
PY_PATH = r"/Users/olepost/Library/Application Support/Blender/3.1/scripts/addons/HumGen3D/scripts/remove_broken_drivers.py"
print("wow")
for root, dirs, files in os.walk(PATH):
    for name in files:
        path = os.path.join(root, name)

        subprocess.call(
            ["blender", "--background", path, "--python", PY_PATH, "--"]
        )
        print("test1")
