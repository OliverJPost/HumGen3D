"""This will turn your haircards textures into png with transparancy.
This is useful for game engines like Unity, which expect rgba textures.

Baking with "Pack haircard alpha" enabled already does this for the color textures,
this script does it for all textures of the haircards.

ONLY USE ON HAIRCARDS THAT HAVE BEEN BAKED!
"""

import bpy
from HumGen3D import Human
from HumGen3D.human.process.bake import pack_alpha_into_image


def main(context: bpy.types.Context, human: Human):
    """This function is called when the script is executed.

    Args:
        context (bpy.types.Context): Blender context.
        human (Human): Instance of a single human. Script will be run for each human.
    """
    if not human.process.has_haircards:
        print("No haircards found for", human.name)
        return

    for haircards_obj in human.objects.haircards:
        for mat in haircards_obj.data.materials:
            alpha_node = mat.node_tree.nodes.get("Alpha")
            if not alpha_node:
                print("No baked alpha texture found for", mat.name)
                continue

            for node in mat.node_tree.nodes:
                if node.type != "TEX_IMAGE":
                    continue
                if node is alpha_node:
                    continue

                pack_alpha_into_image(node.image, alpha_node.image)
