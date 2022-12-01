from contextlib import contextmanager

import bpy


@contextmanager
def context_override(
    context, active_object, selected_objects, allow_contextmanager=True
):
    """Context manager to override the context of a bpy function.

    Args:
        active_object (bpy.types.Object): The object to set as active.
        selected_objects (List[bpy.types.Object]): The objects to set as selected.
        allow_contextmanager (bool, optional): Whether to allow the use of the context manager. Defaults to True.
    """
    if bpy.app.version >= (3, 3, 0) and allow_contextmanager:
        with context.temp_override(
            active_object=active_object,
            object=active_object,
            selected_objects=selected_objects,
            selected_editable_objects=selected_objects,
        ):
            yield
    else:
        old_selected = context.selected_objects
        old_active = context.active_object

        active_object.select_set(True)
        context.view_layer.objects.active = active_object

        for obj in selected_objects:
            obj.select_set(True)

        try:
            yield
        finally:
            for obj in selected_objects:
                obj.select_set(False)

            for obj in old_selected:
                obj.select_set(True)

            context.view_layer.objects.active = old_active
