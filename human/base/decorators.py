import functools
import traceback

import bpy
from HumGen3D.backend import hg_log


def cached_property(func):
    return property(cached_instance(func))


def cached_instance(function):
    @functools.wraps(function)
    def wrapper(self, *args, **kwargs):

        cached_attribute_name = f"_{function.__name__}"
        if hasattr(self, cached_attribute_name):
            return getattr(self, cached_attribute_name)
        else:
            result = function(self, *args, **kwargs)
            setattr(self, cached_attribute_name, result)
            return result

    return wrapper


def injected_context(func):
    """Replaces keyword argument "context=None" with bpy.context if left at default None value"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        varnames = func.__code__.co_varnames
        if "context" not in varnames:
            raise TypeError("No argument 'context' in function arguments.")

        context_arg_index = varnames.index("context")
        context_in_args = len(args) >= (context_arg_index + 1)
        if not context_in_args and "context" not in kwargs:
            kwargs["context"] = bpy.context

            hg_log(traceback.extract_stack()[-2])
            hg_log(
                f"Argument 'context' for function '{func.__name__}' substituted with bpy.context. It's highly recommended to pass your own context!",
                level="WARNING",
            )

        return func(*args, **kwargs)

    return wrapper
