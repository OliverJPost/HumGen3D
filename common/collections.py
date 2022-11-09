# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Contains functions for dealing with Blender's object collections."""

import bpy


def add_to_collection(
    context: bpy.types.Context, obj: bpy.types.Object, collection_name: str = "HumGen"
) -> bpy.types.Collection:
    """Adds the giver object toa colleciton. By default added to HumGen collection.

    Args:
        context(bpy.types.Context): Blender context
        obj (Object): object to add to collection
        collection_name (str, optional): Name of collection. Defaults to 'HumGen'.

    Returns:
        bpy.types.Collection: Collection the object was added to
    """
    collection = bpy.data.collections.get(
        collection_name, _new_collection(context, collection_name)
    )

    # Unlink object from old collection
    if context.scene.collection.objects.get(obj.name):
        context.scene.collection.objects.unlink(obj)
    else:
        obj.users_collection[0].objects.unlink(obj)

    collection.objects.link(obj)

    return collection  # type: ignore [return-value]


def _new_collection(
    context: bpy.types.Context, collection_name: str
) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name=collection_name)
    if collection_name == "HG Batch Markers":
        hg_collection = bpy.data.collections.get("HumGen")
        if not hg_collection:
            hg_collection = bpy.data.collections.new(name="HumGen")
            context.scene.collection.children.link(hg_collection)
        hg_collection.children.link(collection)
    else:
        context.scene.collection.children.link(collection)
    return collection
