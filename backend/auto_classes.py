# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import inspect
import os
from types import ModuleType
from typing import Any, Callable

import bpy
import HumGen3D

# There are more, but I'm not using them
BPY_CLASSES = (
    bpy.types.Operator,
    bpy.types.PropertyGroup,
    bpy.types.Panel,
    bpy.types.AddonPreferences,
    bpy.types.Header,
    bpy.types.Menu,
    bpy.types.UIList,
)

Class = Callable[..., Any]


def _get_bpy_classes() -> list[Class]:
    dir_path = os.path.dirname(os.path.abspath(HumGen3D.__file__))

    py_files = get_python_files_from_dir(dir_path)

    class_priority_tuples: list[tuple[Class, int]] = []
    for root, filename in py_files:
        module = _import_pyfile_as_module(dir_path, root, filename)

        for _, obj in inspect.getmembers(module):
            if not inspect.isclass(obj) or not issubclass(obj, BPY_CLASSES):
                continue

            priority = getattr(obj, "_register_priority", 99)
            class_priority_tuples.append((obj, priority))

    class_priority_tuples.sort(key=lambda x: x[1])
    return [cls for cls, _ in class_priority_tuples]


def _import_pyfile_as_module(dir_path: str, root: str, filename: str) -> ModuleType:
    abspath = os.path.join(root, filename)
    rel_path_split = os.path.normpath(os.path.relpath(abspath, dir_path)).split(os.sep)
    module_import_path = ".".join(rel_path_split)

    module = __import__(
        ".".join(["HumGen3D", module_import_path[:-3]]),
        fromlist=[module_import_path[:-3]],
    )

    return module  # noqa


def get_python_files_from_dir(dir_path: str) -> list[tuple[str, str]]:
    skip_dirs = (".vscode", ".mypy", ".git", "tests")
    py_files = []
    for root, _, files in os.walk(dir_path):
        if any(d in root for d in skip_dirs):
            continue
        for f in [f for f in files if f.endswith(".py")]:
            if f != "__init__.py" and f != "setup.py":
                py_files.append((root, f))
    return py_files
