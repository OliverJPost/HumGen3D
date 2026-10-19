"""Build the extension zip and the repository index for humgen3d.com/ext.

    python scripts/release_extension.py [--blender <path>] [--out <folder>]

Writes `<out>/humgen3d-<version>.zip` and `<out>/index.json` with Blender's
own `extension build` and `extension server-generate` commands. Upload both
to `<CONTENT_BASE_URL>/ext/` (the website rewrites the archive URLs, see the
website repo's docs/addon-setup.md). Run it from the add-on folder after the
version in blender_manifest.toml was bumped and the tests passed.
"""
import argparse
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_BLENDER = {
    "Darwin": "/Applications/Blender 5.1.app/Contents/MacOS/Blender",
    "Windows": r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
    "Linux": "blender",
}


def manifest_version() -> str:
    with open(os.path.join(ROOT, "blender_manifest.toml"), encoding="utf-8") as f:
        match = re.search(r'^version\s*=\s*"([^"]+)"', f.read(), re.MULTILINE)
    if not match:
        raise SystemExit("No version in blender_manifest.toml")
    return match.group(1)


def run(blender: str, *args: str) -> None:
    cmd = [blender, "--command", *args]
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", default=DEFAULT_BLENDER.get(platform.system(), "blender"))
    parser.add_argument("--out", default=os.path.join(ROOT, "build", "ext"))
    args = parser.parse_args()
    version = manifest_version()
    out = os.path.abspath(args.out)
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)

    run(args.blender, "extension", "validate", ROOT)
    run(args.blender, "extension", "build", "--source-dir", ROOT, "--output-dir", out)
    zips = glob.glob(os.path.join(out, "*.zip"))
    if len(zips) != 1:
        raise SystemExit(f"Expected one zip in {out}, found {zips}")
    zip_path = os.path.join(out, f"humgen3d-{version}.zip")
    os.replace(zips[0], zip_path)
    run(args.blender, "extension", "server-generate", "--repo-dir", out)

    with open(os.path.join(out, "index.json"), encoding="utf-8") as f:
        index = json.load(f)
    entry = index["data"][0]
    print()
    print("Built", os.path.basename(zip_path), entry["archive_size"], "bytes", entry["archive_hash"])
    print("Upload to <CONTENT_BASE_URL>/ext/:", os.path.basename(zip_path), "and index.json")
    print("Then check https://humgen3d.com/ext/index.json shows version", entry["version"])


if __name__ == "__main__":
    sys.exit(main())
