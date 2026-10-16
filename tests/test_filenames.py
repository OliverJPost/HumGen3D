"""Every tracked file must be creatable on Windows, or the add-on update fails there."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_filenames.py"
_spec = importlib.util.spec_from_file_location("check_filenames", SCRIPT)
check_filenames = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_filenames)


def test_tracked_files_are_valid_on_windows():
    assert check_filenames.problems(check_filenames.tracked_files()) == []


def test_checker_catches_bad_names():
    bad = [
        'docs/FAQ/How to fix "x".md',
        "docs/a:b.md",
        "docs/trailing./x.md",
        "docs/aux.md",
        "docs/Readme.md",
        "docs/README.md",
        "a/" + "x" * 200,
    ]
    assert len(check_filenames.problems(bad)) == len(bad) - 1
