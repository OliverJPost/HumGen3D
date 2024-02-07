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
    # Dirty hack for making HG work with multiple scenes. Appends scene name if it's not the "main" scene
    if context.scene != bpy.data.scenes[0]:
        collection_name += context.scene.name

    collection = bpy.data.collections.get(collection_name)
    collection_in_active_scene = collection.name in context.scene.view_layers[0].layer_collection.children if collection else False

    # Handle edge case of deleted scene (Collection was connected to scene with same name, but is now dangling)
    collection_removed = False
    if collection and not collection_in_active_scene:
        bpy.data.collections.remove(collection)
        collection_removed = True

    if not collection or collection_removed:
        collection = _new_collection(context, collection_name)

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
    context.scene.collection.children.link(collection)
    return collection
