# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Contains commonly used decorators for the addon."""

import functools
import os
import time
import traceback
from typing import Any, Callable, TypeVar, cast
import addon_utils
import bpy
from HumGen3D.backend import hg_log
from HumGen3D.common.exceptions import HumGenException
from functools import wraps
import functools
import inspect
import warnings



F = TypeVar("F", bound=Callable[..., Any])


string_types = (type(b''), type(u''))


def deprecated(reason):
    """
    This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.
    """

    if isinstance(reason, string_types):

        # The @deprecated is used with a 'reason'.
        #
        # .. code-block:: python
        #
        #    @deprecated("please, use another function")
        #    def old_function(x, y):
        #      pass

        def decorator(func1):

            if inspect.isclass(func1):
                fmt1 = "Call to deprecated class {name} ({reason})."
            else:
                fmt1 = "Call to deprecated function {name} ({reason})."

            @functools.wraps(func1)
            def new_func1(*args, **kwargs):
                warnings.simplefilter('always', DeprecationWarning)
                warnings.warn(
                    fmt1.format(name=func1.__name__, reason=reason),
                    category=DeprecationWarning,
                    stacklevel=2
                )
                warnings.simplefilter('default', DeprecationWarning)
                return func1(*args, **kwargs)

            return new_func1

        return decorator

    elif inspect.isclass(reason) or inspect.isfunction(reason):

        # The @deprecated is used without any 'reason'.
        #
        # .. code-block:: python
        #
        #    @deprecated
        #    def old_function(x, y):
        #      pass

        func2 = reason

        if inspect.isclass(func2):
            fmt2 = "Call to deprecated class {name}."
        else:
            fmt2 = "Call to deprecated function {name}."

        @functools.wraps(func2)
        def new_func2(*args, **kwargs):
            warnings.simplefilter('always', DeprecationWarning)
            warnings.warn(
                fmt2.format(name=func2.__name__),
                category=DeprecationWarning,
                stacklevel=2
            )
            warnings.simplefilter('default', DeprecationWarning)
            return func2(*args, **kwargs)

        return new_func2

    else:
        raise TypeError(repr(type(reason)))


def disable_mesh_changing_modifiers(func: F) -> F:
    @wraps(func)
    def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        body = getattr(self, "_human", self).objects.body
        disable_list = get_modifiers_to_disable(body)

        for mod in disable_list:
            mod.show_viewport = False

        result = func(self, *args, **kwargs)

        for mod in disable_list:
            mod.show_viewport = True

        return result

    def get_modifiers_to_disable(body):
        disable_list = []
        for mod in body.modifiers:
            if mod.type not in {"ARMATURE", "PARTICLE_SYSTEM"} and mod.show_viewport:
                disable_list.append(mod)

        return disable_list

    return cast(F, wrapper)


def check_for_addon_issues():
    addon = bpy.context.preferences.addons.get("HumGen3D")
    if not addon:
        raise HumGenException("HumGen3D addon not enabled.")
    if not addon.preferences.filepath:
        raise HumGenException("HumGen3D filepath not set.")
    base_humans_path = os.path.join(addon.preferences.filepath, "content_packs", "Base_Humans.json")
    if not os.path.exists(base_humans_path):
        raise HumGenException("Base humans content pack not installed.")

def verify_addon(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        check_for_addon_issues()
        return func(*args, **kwargs)

    return wrapper


def timing(f):
    def wrap(*args):
        time1 = time.perf_counter()
        ret = f(*args)
        time2 = time.perf_counter()
        print(f"function {f.__name__} took {time2 - time1} seconds")
        return ret

    return wrap


def raise_if_pytest_human(args):
    self = args[0]
    if hasattr(self, "_human"):
        human = self._human
    else:
        human = self
        if not hasattr(human, "_rig_obj"):
            return

    if "pytest_human" in human._rig_obj:
        raise HumGenException("No context passed for injected context.")


def injected_context(func: F) -> F:
    """Replaces keyword argument "context=None" with bpy.context if left at default. # noqa

    Args:
        func: Function that's decorated # noqa
    Returns:
        Function wrapper
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):  # type:ignore[no-untyped-def]
        varnames = func.__code__.co_varnames
        if "context" not in varnames:
            raise TypeError("No argument 'context' in function arguments.")

        context_arg_index = varnames.index("context")
        context_in_args = len(args) >= (context_arg_index + 1)
        if not context_in_args and "context" not in kwargs:
            raise_if_pytest_human(args)

            kwargs["context"] = bpy.context

            hg_log(traceback.extract_stack()[-2])
            hg_log(
                f"Argument 'context' for function '{func.__name__}'",
                "substituted with bpy.context.",
                " It's highly recommended to pass your own context!",
                level="WARNING",
            )

        return func(*args, **kwargs)

    return cast(F, wrapper)
