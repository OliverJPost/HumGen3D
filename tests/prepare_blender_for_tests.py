import os
import shutil
import site
import subprocess
import sys
from pathlib import Path

import bpy


def make_archive(source, destination):
    base = os.path.basename(destination)
    name = base.split(".")[0]
    format = base.split(".")[1]
    archive_from = os.path.dirname(source)
    archive_to = os.path.basename(source.strip(os.sep))
    shutil.make_archive(name, format, archive_from, archive_to)
    shutil.move("%s.%s" % (name, format), destination)


def main():
    # Get blender python path
    dev_requirements = os.path.join(
        str(Path(__file__).parent.parent), "dev_requirements.txt"
    )
    py_exec = sys.executable
    assert "blender" in py_exec, f"Not Blender python: {py_exec}"
    subprocess.call([py_exec, "-m", "pip", "install", "-r", dev_requirements])
    sp = site.getsitepackages()[0]
    print("site packages", sp)
    for module in ["pytest", "pytest-cov", "pytest-lazy-fixture", "pytest-blender"]:
        subprocess.call([py_exec, "-m", "pip", "install", module, "-t", sp])
    print(f"Installed dev requirements in {py_exec}")
    # Get blender addon folder
    scripts_folder = Path(bpy.utils.user_resource("SCRIPTS"))
    # Create HumGen3D folder
    # Copy addon folder to add-on folder (for testing)
    # path of parent of parent folder
    humgen_path = str(Path(__file__).parent.parent)
    temp_folder = "/private/tmp"
    addon_folder = os.path.join(scripts_folder, "addons")

    zipped_addon_path = os.path.join(temp_folder, "HumGen3D.zip")
    if os.path.exists(zipped_addon_path):
        os.remove(zipped_addon_path)

    make_archive(humgen_path, zipped_addon_path)

    hg_folder = os.path.join(scripts_folder, "addons", "HumGen3D")
    try:
        shutil.rmtree(hg_folder)
    except (FileNotFoundError, NotADirectoryError):
        pass

    bpy.ops.preferences.addon_install(filepath=zipped_addon_path)
    bpy.ops.preferences.addon_enable(module="HumGen3D")
    pref = bpy.context.preferences.addons["HumGen3D"].preferences
    pref.filepath = "/Users/ole/Documents/Human Generator"
    bpy.ops.wm.save_userpref()

    bpy.ops.wm.quit_blender()


if __name__ == "__main__":
    main()
