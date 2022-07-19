import inspect
import os

import bpy
import HumGen3D


def _get_bpy_classes():
    dir_path = os.path.dirname(os.path.abspath(HumGen3D.__file__))

    # There are more, but I'm not using them
    bpy_classes = (
        bpy.types.Operator,
        bpy.types.PropertyGroup,
        bpy.types.Panel,
        bpy.types.AddonPreferences,
        bpy.types.Header,
        bpy.types.Menu,
        bpy.types.UIList,
    )

    skip_dirs = (".vscode", ".mypy", ".git", "tutorial_operator", "tests")
    py_files = []
    for root, _, files in os.walk(dir_path):
        if any(dir in root for dir in skip_dirs):
            continue
        for f in [f for f in files if f.endswith(".py")]:
            if f != "__init__.py" and f != "setup.py":
                py_files.append((root, f))

    yielded = []
    for root, f in py_files:
        abspath = os.path.join(root, f)
        rel_path_split = os.path.normpath(os.path.relpath(abspath, dir_path)).split(
            os.sep
        )
        module_import_path = ".".join(rel_path_split)

        mod = __import__(
            ".".join(["HumGen3D", module_import_path[:-3]]),
            fromlist=[module_import_path[:-3]],
        )

        waitlist = []
        for name, obj in inspect.getmembers(mod):
            if inspect.isclass(obj) and issubclass(obj, bpy_classes):
                # Check if the class is actually from the HumGen3D module
                if not obj.__module__.split(".")[0] == "HumGen3D":
                    continue
                # Skip classes that have been yielded previously
                if name in yielded:
                    continue
                # Wait with yielding UI classes that depend on parent
                if hasattr(obj, "bl_parent_id"):
                    waitlist.append(obj)
                    continue

                yielded.append(name)
                yield obj

        # Yield UI classes that depend on parent last
        yield from waitlist

    from HumGen3D.user_interface.documentation.tutorial_operator import (
        tutorial_operator,
    )

    yield tutorial_operator.HG_DRAW_PANEL
