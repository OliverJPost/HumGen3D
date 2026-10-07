# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""Custom Python scripts that run at a stage of the process.

A script is a file with a `main(context, human, ...)` function. Extra parameters
with a str, int, float or bool annotation become arguments the interface asks
for. A script that runs after the export can take a `files` parameter with the
paths that were written. The stages are the steps of the pipeline, see
`settings.SCRIPT_STAGES`: the ones before the export run on every LOD level. A
module constant `STAGE = "after_export"` sets the stage a script is added with.
"""

import ast
import importlib.util
import os
import traceback
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from HumGen3D.backend.logging import hg_log
from HumGen3D.backend.preferences.preference_func import get_addon_root, get_prefs
from HumGen3D.common.exceptions import HumGenException

from .settings import SCRIPT_STAGES, ScriptSettings

if TYPE_CHECKING:
    from HumGen3D.human.human import Human

ARG_TYPES = {"str": str, "int": int, "float": float, "bool": bool}
FILES_PARAMETER = "files"
STAGE_CONSTANT = "STAGE"
STAGE_IDS = tuple(stage for stage, *_ in SCRIPT_STAGES)
SCRIPT_TEMPLATE = '''"""Describe what the script does here, the interface shows it."""

import bpy
from HumGen3D import Human

# The stage the script is added with, one of: {stages}
STAGE = "after_processing"


def main(context: bpy.types.Context, human: Human):
    """Runs at the stage chosen in the interface, on every LOD level.

    Extra parameters with a str, int, float or bool annotation become arguments
    in the interface, for example `strength: float = 1.0`. A script that runs
    after the export can take `files: list` with the paths that were written.
    `human.objects.rig["hg_export_level"]` is the LOD level, 0 for the first.

    Args:
        context (bpy.types.Context): Blender context.
        human (Human): The processed copy, never the original human.
    """
    pass  # Your code goes here
'''.replace("{stages}", ", ".join(STAGE_IDS))


class ScriptError(HumGenException):
    """A script could not be read or failed to run."""


@dataclass
class ScriptArgument:
    """A parameter of the main function of a script."""

    name: str
    type: str  # noqa: A003
    default: Any = None


@dataclass
class ScriptInfo:
    """What the interface shows about a script."""

    path: str
    name: str
    description: str
    args: List[ScriptArgument] = field(default_factory=list)
    takes_files: bool = False
    # The stage of the STAGE constant of the script, None when it has none
    stage: Optional[str] = None


def script_folders() -> List[str]:
    """The folder of the user and the folder with the shipped scripts."""
    return [
        os.path.join(get_prefs().filepath, "scripts"),
        os.path.join(get_addon_root(), "scripts", "preset_scripts"),
    ]


def available_scripts() -> List[str]:
    """Paths of every script in the script folders."""
    paths = []
    for folder in script_folders():
        if not os.path.isdir(folder):
            continue
        for file in sorted(os.listdir(folder)):
            if file.endswith(".py") and not file.startswith("_"):
                paths.append(os.path.join(folder, file))
    return paths


def inspect_script(path: str) -> ScriptInfo:
    """Reads the description and the arguments of a script without running it.

    Raises:
        ScriptError: If the file can't be read or has no usable main function.
    """
    try:
        with open(path, "r") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError) as e:
        raise ScriptError(f"Can't read script {os.path.basename(path)}: {e}") from e

    main = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        ),
        None,
    )
    if main is None:
        raise ScriptError(f"{os.path.basename(path)} has no main function")

    info = ScriptInfo(
        path=path,
        name=os.path.splitext(os.path.basename(path))[0],
        description=ast.get_docstring(tree) or "",
        stage=_stage_constant(tree, path),
    )
    params = main.args.args[2:]
    defaults: List[Optional[ast.expr]] = [None] * (
        len(params) - len(main.args.defaults)
    ) + list(main.args.defaults)
    for param, default in zip(params, defaults):
        if param.arg == FILES_PARAMETER:
            info.takes_files = True
            continue
        annotation = getattr(param.annotation, "id", None)
        if annotation not in ARG_TYPES:
            raise ScriptError(
                f"Parameter '{param.arg}' of {info.name} needs a str, int, float or"
                " bool annotation"
            )
        value = None
        if isinstance(default, ast.Constant):
            value = default.value
        info.args.append(ScriptArgument(param.arg, annotation, value))
    return info


def _stage_constant(tree: ast.Module, path: str) -> Optional[str]:
    """The value of the module level STAGE constant, None if there is none.

    Raises:
        ScriptError: If the stage is not one of SCRIPT_STAGES.
    """
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == STAGE_CONSTANT for t in node.targets):
            continue
        value = node.value.value if isinstance(node.value, ast.Constant) else None
        if value not in STAGE_IDS:
            raise ScriptError(
                f"{os.path.basename(path)}: STAGE must be one of {', '.join(STAGE_IDS)}"
            )
        return str(value)
    return None


def default_args(info: ScriptInfo) -> Dict[str, Any]:
    """The arguments of a script with their default values."""
    return {
        arg.name: arg.default if arg.default is not None else ARG_TYPES[arg.type]()
        for arg in info.args
    }


def run_script(
    settings: ScriptSettings,
    context: Any,
    human: "Human",
    files: Optional[List[str]] = None,
) -> Optional[str]:
    """Runs a script on a processed human.

    Args:
        settings (ScriptSettings): Which script, its arguments and what to do
            when it fails.
        context: Blender context.
        human (Human): The processed copy to run on.
        files (Optional[List[str]]): Written files, for scripts after the export.

    Returns:
        Optional[str]: A warning when the script failed and was skipped, None
            when it ran.

    Raises:
        ScriptError: If the script failed and its policy is to stop.
    """
    name = os.path.basename(settings.path)
    try:
        info = inspect_script(settings.path)
        module = _load_module(settings.path)
        kwargs = default_args(info)
        for arg in info.args:
            if arg.name in settings.args:
                kwargs[arg.name] = ARG_TYPES[arg.type](settings.args[arg.name])
        if info.takes_files:
            kwargs[FILES_PARAMETER] = list(files or [])
        module.main(context, human, **kwargs)
    except Exception as e:  # noqa: BLE001
        message = f"Script {name} failed: {e}"
        hg_log(message + "\n" + traceback.format_exc(), level="ERROR")
        if settings.on_error == "skip":
            return message
        raise ScriptError(message) from e
    return None


def create_script(name: str) -> str:
    """Writes a new script from the template in the script folder of the user.

    Args:
        name (str): File name without extension.

    Returns:
        str: Path of the new script.
    """
    folder = script_folders()[0]
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name + ".py")
    with open(path, "w") as f:
        f.write(SCRIPT_TEMPLATE)
    return path


def _load_module(path: str) -> Any:
    """Imports the script as a module of its own, fresh every run."""
    name = "hg_script_" + os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ScriptError(f"Can't import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
