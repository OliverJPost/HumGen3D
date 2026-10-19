"""Shared pytest setup.

The setup system keeps a settings file outside Blender (see
`backend/setup/user_settings.py`). Every test run points it at a temporary
file, so no test can touch the developer's real content folder and order.
"""
import os
import tempfile

import pytest


@pytest.fixture(scope="session", autouse=True)
def isolated_user_settings():
    path = os.path.join(tempfile.mkdtemp(prefix="hg_test_settings_"), "settings.json")
    previous = os.environ.get("HUMGEN_SETTINGS_FILE")
    os.environ["HUMGEN_SETTINGS_FILE"] = path
    yield path
    if previous is None:
        os.environ.pop("HUMGEN_SETTINGS_FILE", None)
    else:
        os.environ["HUMGEN_SETTINGS_FILE"] = previous
