# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Contains commonly used decorators for the addon."""

import functools
import traceback
from typing import Any, Callable, TypeVar, cast

import bpy
from HumGen3D.backend import hg_log
from HumGen3D.common.exceptions import HumGenException

F = TypeVar("F", bound=Callable[..., Any])


def raise_if_pytest_human(args):
    self = args[0]
    if hasattr(self, "_human"):
        human = self._human
    else:
        human = self
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
