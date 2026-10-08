# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Removes the skin under the clothing from the body mesh.

Clothing hides the skin it covers with mask modifiers on the body. Exporters
write the mesh without its modifiers, to keep the shape keys, so the exported
body would be complete under every garment. This deletes the masked vertices
from the mesh itself, with bmesh, which carries the shape keys along.
"""

from typing import TYPE_CHECKING

import bmesh
import bpy
from HumGen3D.common.decorators import injected_context
from HumGen3D.common.type_aliases import C

if TYPE_CHECKING:
    from HumGen3D.human.human import Human


@injected_context
def remove_hidden_skin(human: "Human", context: C = None) -> int:
    """Deletes the vertices of the body that its mask modifiers hide.

    Only masks by vertex group are applied, which is the kind the clothing
    adds. The mask modifiers are removed afterwards.

    Args:
        human (Human): Human to change the body of, in place.
        context (C): Blender context. bpy.context if not provided.

    Returns:
        int: Number of vertices removed.
    """
    body = human.objects.body
    masks = [
        mod
        for mod in body.modifiers
        if mod.type == "MASK"
        and mod.mode == "VERTEX_GROUP"
        and mod.vertex_group in body.vertex_groups
        and (mod.show_viewport or mod.show_render)
    ]
    if not masks:
        return 0

    # Each mask keeps the vertices in its group, so a vertex stays when every
    # mask keeps it
    hidden = set()
    for mod in masks:
        group_index = body.vertex_groups[mod.vertex_group].index
        for vertex in body.data.vertices:
            in_group = any(
                g.group == group_index and g.weight > mod.threshold
                for g in vertex.groups
            )
            if in_group == mod.invert_vertex_group:
                hidden.add(vertex.index)
    if not hidden:
        for mod in masks:
            body.modifiers.remove(mod)
        return 0

    # The particle hair is bound to the vertices of the body
    human.hair.set_connected(False, context)
    bm = bmesh.new()  # type:ignore[call-arg]
    bm.from_mesh(body.data)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(
        bm, geom=[bm.verts[index] for index in hidden], context="VERTS"
    )
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    for mod in masks:
        body.modifiers.remove(mod)
    human.hair.set_connected(True, context)
    return len(hidden)


def has_hidden_skin(body: bpy.types.Object) -> bool:
    """Whether the body has mask modifiers that hide skin."""
    return any(mod.type == "MASK" for mod in body.modifiers)
