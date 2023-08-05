"""This will turn your haircards textures into png with transparancy.
This is useful for game engines like Unity, which expect rgba textures.

ONLY USE ON HAIRCARDS THAT HAVE BEEN BAKED!
"""

import bpy
from HumGen3D import Human
import subprocess
import os
import sys

def ensure_PIL():
    try:
        from PIL import Image
    except ImportError:
        python_exe = os.path.join(sys.prefix, "bin", "python.exe")
        target = os.path.join(sys.prefix, "lib", "site-packages")
        subprocess.call([python_exe, "-m", "ensurepip"])
        subprocess.call([python_exe, "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.call(
            [
                python_exe,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "Pillow",
                "-t",
                target,
            ]
        )
        from PIL import Image

    return Image

def main(context: bpy.types.Context, human: Human):
    """This function is called when the script is executed.

    Args:
        context (bpy.types.Context): Blender context.
        human (Human): Instance of a single human. Script will be run for each human.
    """
    if not human.process.has_haircards:
        print("No haircards found for", human.name)
        return

    Image = ensure_PIL()
    for haircards_obj in human.objects.haircards:
        for mat in haircards_obj.data.materials:
            alpha_node = mat.node_tree.nodes.get("Alpha")
            alpha_path = alpha_node.image.filepath
            alpha_img = Image.open(alpha_path)

            for node in mat.node_tree.nodes:
                if node.type != "TEX_IMAGE":
                    continue
                if node is alpha_node:
                    continue

                img = Image.open(node.image.filepath)
                img = img.convert("RGBA")
                alpha = alpha_img.convert('L')
                r, g, b, a = img.split()
                new_img = Image.merge('RGBA', (r, g, b, alpha))
                new_img.save(node.image.filepath)


