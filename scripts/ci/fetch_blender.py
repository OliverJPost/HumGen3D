"""Download a Blender release for CI and print the path of its executable.

    python fetch_blender.py 4.2.11 blender-dist     # download and unpack
    python fetch_blender.py --path blender-dist     # print the executable path

Uses the official download mirror. Linux gets the .tar.xz, Windows the .zip;
macOS is tested locally, not here.
"""
import os
import platform
import shutil
import sys
import tarfile
import urllib.request
import zipfile

MIRROR = "https://download.blender.org/release"


def archive_name(version: str) -> str:
    major_minor = ".".join(version.split(".")[:2])
    system = platform.system()
    if system == "Linux":
        return f"Blender{major_minor}/blender-{version}-linux-x64.tar.xz"
    if system == "Windows":
        return f"Blender{major_minor}/blender-{version}-windows-x64.zip"
    raise SystemExit(f"No CI download for {system}")


def executable(dist: str) -> str:
    for root, dirs, files in os.walk(dist):
        for name in files:
            if name in ("blender", "blender.exe", "Blender"):
                # The real path: Blender finds its resources next to the binary, not a link to it
                return os.path.realpath(os.path.join(root, name))
    raise SystemExit(f"No Blender executable under {dist}")


def fetch(version: str, dist: str) -> str:
    os.makedirs(dist, exist_ok=True)
    url = f"{MIRROR}/{archive_name(version)}"
    archive = os.path.join(dist, os.path.basename(url))
    print("downloading", url, flush=True)
    urllib.request.urlretrieve(url, archive)
    print("unpacking", archive, flush=True)
    if archive.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dist)
    else:
        with tarfile.open(archive) as tf:
            tf.extractall(dist)
    os.remove(archive)
    return executable(dist)


def main() -> None:
    if sys.argv[1] == "--path":
        print(executable(sys.argv[2]))
        return
    path = fetch(sys.argv[1], sys.argv[2])
    if platform.system() != "Windows":
        os.chmod(path, 0o755)
    print(path)


if __name__ == "__main__":
    main()
