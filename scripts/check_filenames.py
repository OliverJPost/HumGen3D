"""Fail when a tracked file has a path Windows can't create.

The add-on updater downloads the repo as a zip and writes every file in it, so
one file named `How to fix "x".md` stops the update on every Windows machine.
Runs on any OS (no Blender needed) and checks the files in the git index:

    python scripts/check_filenames.py
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

INVALID_CHARS = re.compile(r'[<>:"|?*\\\x00-\x1f]')
RESERVED_NAMES = re.compile(r"^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(\..*)?$", re.I)
# Windows paths stop at 260 characters. The add-on folder is about 90 of those
# (C:\Users\<name>\AppData\Roaming\Blender Foundation\Blender\4.2\scripts\addons\HumGen3D\),
# the updater's staging folder a few more; leave room for long user names.
MAX_PATH_LENGTH = 140


def tracked_files() -> list[str]:
    """The paths in the git index, as they end up in the GitHub zip."""
    out = subprocess.run(
        ["git", "-c", "core.quotepath=off", "ls-files", "-z"],
        cwd=REPO,
        capture_output=True,
        check=True,
    ).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def problems(paths: list[str]) -> list[str]:
    """One message per path that can't be written on Windows."""
    found = []
    for path in paths:
        for part in path.split("/"):
            if INVALID_CHARS.search(part):
                chars = "".join(sorted(set(INVALID_CHARS.findall(part))))
                found.append(f"{path}: invalid character(s) {chars!r}")
            elif part.endswith((" ", ".")):
                found.append(f"{path}: {part!r} ends with a space or dot")
            elif RESERVED_NAMES.match(part):
                found.append(f"{path}: {part!r} is a reserved name")
        if len(path) > MAX_PATH_LENGTH:
            found.append(f"{path}: longer than {MAX_PATH_LENGTH} characters")

    seen: dict[str, str] = {}
    for path in paths:
        other = seen.setdefault(path.lower(), path)
        if other != path:
            found.append(f"{path}: differs only in case from {other}")
    return found


def main() -> int:
    """Print the bad paths and return 1 if there are any."""
    found = problems(tracked_files())
    for message in found:
        print(message)
    if found:
        print("These paths break the add-on update on Windows; rename them.")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
