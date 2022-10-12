# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy


def _post_vscode_reload() -> None:
    bpy.ops.hg3d.activate()  # type:ignore[attr-defined]
