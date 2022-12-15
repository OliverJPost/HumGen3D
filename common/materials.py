import bpy.types

from HumGen3D.common.exceptions import HumGenException


def verify_no_undefined_nodes_in_mat(mat: bpy.types.Material) -> None:
    """Verify that the material has no nodes of undefined type."""
    _verify_no_undefined_nodes_in_nodes(mat.node_tree.nodes)


def _verify_no_undefined_nodes_in_nodes(nodes):
    for node in nodes:
        if node.type == "GROUP":
            _verify_no_undefined_nodes_in_nodes(node.node_tree.nodes)
        if node.bl_idname == "NodeUndefined":
            raise HumGenException("Invalid node in material")
