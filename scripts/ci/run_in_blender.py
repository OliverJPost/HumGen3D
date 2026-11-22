"""Run pytest files inside a Blender install, with the repo as the add-on.

    python run_in_blender.py <blender-dist> <repo> tests/test_a.py tests/test_b.py

`<blender-dist>` is a folder holding a Blender (the one `fetch_blender.py`
unpacked, or any folder with a link to a local Blender executable). The repo
is linked into a temporary user scripts folder as `addons/HumGen3D`, pytest is
installed into a temporary folder with Blender's own Python (the install is
not touched), and Blender runs headless with an empty user config, so nothing
else on the machine leaks in. The exit code is pytest's.
"""
import os
import shutil
import subprocess
import sys
import tempfile

from fetch_blender import executable

RUNNER = """
import sys
sys.path.insert(0, {site!r})
import pytest
sys.exit(pytest.main([{args}, "-p", "no:cacheprovider", "-W", "ignore", "-q", "-x"]))
"""


def python_of(blender: str) -> str:
    """The Python bundled with this Blender: <dist>/<ver>/python/bin on Linux and
    Windows, Contents/Resources/<ver>/python/bin on macOS."""
    real = os.path.realpath(blender)
    for base in (os.path.dirname(real), os.path.dirname(os.path.dirname(real))):
        for dirpath, dirs, files in os.walk(base):
            if os.path.basename(dirpath) != "bin" or "python" not in dirpath:
                continue
            for name in ("python3.13", "python3.12", "python3.11", "python3.10", "python3", "python", "python.exe"):
                if name in files:
                    return os.path.join(dirpath, name)
    raise SystemExit("No bundled Python found next to " + blender)


def main() -> None:
    dist, repo, *tests = sys.argv[1:]
    blender = executable(dist)
    python = python_of(blender)
    site = tempfile.mkdtemp(prefix="hg_ci_site_")
    if subprocess.run([python, "-m", "pip", "--version"], capture_output=True).returncode != 0:
        subprocess.check_call([python, "-m", "ensurepip", "--upgrade"])  # a Blender without pip
    subprocess.check_call([python, "-m", "pip", "install", "--quiet", "--target", site, "pytest", "pytest-lazy-fixtures"])

    scripts = tempfile.mkdtemp(prefix="hg_ci_scripts_")
    addons = os.path.join(scripts, "addons")
    os.makedirs(addons)
    target = os.path.join(addons, "HumGen3D")
    try:
        os.symlink(os.path.abspath(repo), target)
    except (OSError, NotImplementedError):
        shutil.copytree(repo, target, ignore=shutil.ignore_patterns(".git", "__pycache__", "blender-dist", "build"))

    env = dict(os.environ)
    env["BLENDER_USER_SCRIPTS"] = scripts
    env["BLENDER_USER_CONFIG"] = tempfile.mkdtemp(prefix="hg_ci_config_")
    env["HUMGEN_SETTINGS_FILE"] = os.path.join(env["BLENDER_USER_CONFIG"], "humgen-settings.json")
    args = ", ".join(repr(os.path.join(target, t)) for t in tests)
    script = os.path.join(scripts, "run_tests.py")
    with open(script, "w") as f:
        f.write(RUNNER.format(site=site, args=args))
    # The add-on must be importable as HumGen3D: enable it, then run pytest
    result = subprocess.run(
        [blender, "-b", "--python-exit-code", "1", "--python-expr", "import bpy; bpy.ops.preferences.addon_enable(module='HumGen3D')", "--python", script],
        env=env,
        cwd=target,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
