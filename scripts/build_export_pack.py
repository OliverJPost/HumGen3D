"""Builds HG_Export.hgpack from the content folder.

The pack holds the data the process system runs on, which is not part of the
add-on (see human/process/export_pack.py): the built-in recipes, the bone names
of the game skeletons and the edge lists of the mesh reduction. Their source is
the content folder, edit them there and log the change in CONTENT_CHANGELOG.md.

    python scripts/build_export_pack.py "<content folder>" [output folder]

Writes HG_Export.hgpack to the output folder, the Desktop by default. Raise
"pack_version" in content_packs/HG_Export.json before building a new release,
and `REQUIRED_VERSION` in export_pack.py when the add-on needs the new data.
Runs without Blender.
"""

import json
import os
import sys
from zipfile import ZIP_DEFLATED, ZipFile

PACK_NAME = "HG_Export"
MANIFEST = f"content_packs/{PACK_NAME}.json"
# Files and folders of the pack, relative to the content folder
DATA = (
    "process/recipes",
    "process/game_rig_presets.json",
    "process/lod/edges.json",
    "process/lod/collar_edges.json",
    "process/lod/lod2.json",
)


def pack_files(content_folder: str) -> list:
    """Paths of the data files, relative to the content folder."""
    files = []
    for entry in DATA:
        path = os.path.join(content_folder, entry)
        if os.path.isdir(path):
            files.extend(
                f"{entry}/{name}" for name in sorted(os.listdir(path)) if name.endswith(".json")
            )
        elif os.path.isfile(path):
            files.append(entry)
        else:
            sys.exit(f"Missing {path}")
    return files


def check(content_folder: str, files: list) -> None:
    """Every file is valid JSON and every recipe of order.json exists."""
    for file in files:
        with open(os.path.join(content_folder, file)) as f:
            json.load(f)
    with open(os.path.join(content_folder, "process/recipes/order.json")) as f:
        order = json.load(f)
    missing = [name for name in order if f"process/recipes/{name}.json" not in files]
    if missing:
        sys.exit(f"Recipes in order.json without a file: {missing}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    content_folder = sys.argv[1]
    output_folder = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser("~/Desktop")

    with open(os.path.join(content_folder, MANIFEST)) as f:
        manifest = json.load(f)
    # The list of installed files is added on install, see content_packs.py
    manifest.pop("files", None)

    files = pack_files(content_folder)
    check(content_folder, files)

    path = os.path.join(output_folder, PACK_NAME + ".hgpack")
    with ZipFile(path, "w", ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST, json.dumps(manifest, indent=4))
        for file in files:
            zf.write(os.path.join(content_folder, file), file)
    version = ".".join(str(n) for n in manifest["config"]["pack_version"])
    print(f"Wrote {path}: version {version}, {len(files)} files")


if __name__ == "__main__":
    main()
