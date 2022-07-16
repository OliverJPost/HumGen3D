import bpy


# MODULE
def add_to_collection(context, obj, collection_name="HumGen") -> bpy.types.Collection:
    """Adds the giver object toa colleciton. By default added to HumGen collection

    Args:
        obj (Object): object to add to collection
        collection_name (str, optional): Name of collection. Defaults to 'HumGen'.

    Returns:
        bpy.types.Collection: Collection the object was added to
    """
    collection = bpy.data.collections.get(collection_name)

    if not collection:
        collection = bpy.data.collections.new(name=collection_name)
        if collection_name == "HumGen_Backup [Don't Delete]":
            bpy.data.collections["HumGen"].children.link(collection)
            context.view_layer.layer_collection.children["HumGen"].children[
                collection_name
            ].exclude = True
        elif collection_name == "HG Batch Markers":
            hg_collection = bpy.data.collections.get("HumGen")
            if not hg_collection:
                hg_collection = bpy.data.collections.new(name="HumGen")
                context.scene.collection.children.link(hg_collection)
            hg_collection.children.link(collection)
        else:
            context.scene.collection.children.link(collection)

    if obj in [o for o in context.scene.collection.objects]:
        context.scene.collection.objects.unlink(obj)
    else:
        obj.users_collection[0].objects.unlink(obj)

    collection.objects.link(obj)

    return collection
