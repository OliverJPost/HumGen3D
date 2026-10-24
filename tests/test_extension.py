# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The add-on as a Blender extension: manifest, package name, import alias, no Pillow.

These run with the add-on loaded the legacy way, as `HumGen3D`. The extension
way is covered by `test_extension_mode.py`.
"""
import ast
import importlib
import os
import re
import sys
import textwrap
import tomllib

import bpy
import pytest

import HumGen3D
from HumGen3D import alias
from HumGen3D.common.images import file_format, save_resized
from HumGen3D.package import (
    MANIFEST_FILE,
    addon_package,
    addon_root,
    addon_version,
    is_extension,
    manifest_path,
    manifest_version,
)

ROOT = addon_root()
# Folders of the add-on that are not part of the shipped package
NOT_SHIPPED = {"tests", "docs", "scripts", "venv", ".venv", ".git", "__pycache__", "reports", "research_notes", ".idea"}
PACKAGE_IMPORT = re.compile(r"^\s*(from|import)\s+(HumGen3D|HG3D)\b")


def shipped_python_files():
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in NOT_SHIPPED]
        for fn in files:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


@pytest.fixture(scope="module")
def manifest() -> dict:
    with open(manifest_path(), "rb") as f:
        return tomllib.load(f)


# Manifest


def test_manifest_is_next_to_init():
    assert os.path.isfile(os.path.join(ROOT, MANIFEST_FILE))
    assert os.path.isfile(os.path.join(ROOT, "__init__.py"))


def test_manifest_required_fields(manifest):
    assert manifest["schema_version"] == "1.0.0"
    assert manifest["id"] == "humgen3d"
    assert manifest["type"] == "add-on"
    assert manifest["name"] == "Human Generator 3D"
    assert manifest["license"] == ["SPDX:GPL-3.0-or-later"]
    assert "maintainer" in manifest
    assert tuple(int(n) for n in manifest["blender_version_min"].split(".")) >= (4, 2, 0)


def test_manifest_id_is_valid_module_name(manifest):
    # Blender's own rules for an extension id
    pkg_id = manifest["id"]
    assert pkg_id.isidentifier()
    assert "__" not in pkg_id
    assert not pkg_id.startswith("_") and not pkg_id.endswith("_")


def test_manifest_short_texts_fit(manifest):
    assert len(manifest["tagline"]) <= 64
    for reason in manifest["permissions"].values():
        assert len(reason) <= 64


def test_manifest_permissions_are_the_two_the_addon_needs(manifest):
    # The update check and content downloads need the network, the content
    # folder needs files. Anything else would be a surprise.
    assert set(manifest["permissions"]) == {"files", "network"}


def test_manifest_bundles_no_wheels(manifest):
    assert "wheels" not in manifest
    assert not os.path.isdir(os.path.join(ROOT, "wheels"))


def test_manifest_build_leaves_out_development_folders(manifest):
    excluded = manifest["build"]["paths_exclude_pattern"]
    for folder in ("/tests/", "/docs/", "/scripts/", "/venv/", "/.git/", "__pycache__/"):
        assert folder in excluded


# Version


def test_version_comes_from_the_manifest():
    assert HumGen3D.__version__ == manifest_version()
    assert addon_version() == manifest_version()
    assert len(manifest_version()) == 3


def test_bl_info_mirrors_the_manifest_version():
    """Blender 4.0 and 4.1 read bl_info as a literal, so it can't be derived."""
    with open(os.path.join(ROOT, "__init__.py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    bl_info = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", None) == "bl_info" for t in node.targets)
    )
    assert tuple(bl_info["version"]) == manifest_version()
    assert tuple(HumGen3D.bl_info["version"]) == manifest_version()


def test_manifest_version_without_a_version_line_is_an_error(tmp_path, monkeypatch):
    broken = tmp_path / MANIFEST_FILE
    broken.write_text('id = "x"\n')
    monkeypatch.setattr("HumGen3D.package.manifest_path", lambda: str(broken))
    with pytest.raises(RuntimeError):
        manifest_version()


# Package name


def test_package_helpers_in_legacy_mode():
    assert addon_package() == "HumGen3D"
    assert not is_extension()
    assert addon_root() == os.path.dirname(os.path.abspath(HumGen3D.__file__))


def test_no_absolute_imports_of_the_package():
    """Under the extension system the package is not called HumGen3D."""
    offenders = []
    for path in shipped_python_files():
        with open(path, encoding="utf-8") as f:
            for number, line in enumerate(f, 1):
                if PACKAGE_IMPORT.match(line):
                    offenders.append(f"{os.path.relpath(path, ROOT)}:{number}: {line.strip()}")
    assert not offenders, "\n".join(offenders)


def test_no_pillow_or_runtime_pip():
    """An extension may not install packages at runtime, and Pillow is gone."""
    offenders = []
    forbidden = re.compile(r"^\s*(from PIL|import PIL)|ensurepip|\"pip\"")
    for path in shipped_python_files():
        with open(path, encoding="utf-8") as f:
            for number, line in enumerate(f, 1):
                if forbidden.search(line):
                    offenders.append(f"{os.path.relpath(path, ROOT)}:{number}: {line.strip()}")
    assert not offenders, "\n".join(offenders)


def test_preferences_id_is_the_package_name():
    from HumGen3D.backend.preferences.preferences import HG_PREF

    assert HG_PREF.bl_idname == addon_package()


def test_updater_registered_in_legacy_mode():
    from HumGen3D.backend.updates import addon_updater_ops

    if not bpy.context.preferences.addons.get("HumGen3D"):
        bpy.ops.preferences.addon_enable(module="HumGen3D")
    assert all(cls.is_registered for cls in addon_updater_ops.classes)


# Import alias


def test_hg3d_alias_in_legacy_mode():
    finder = alias.installed()
    assert finder is not None
    assert finder.package == "HumGen3D"
    assert finder.aliases == ("HG3D",)
    import HG3D
    from HG3D.human.human import Human as aliased
    from HumGen3D.human.human import Human

    assert HG3D is HumGen3D
    assert aliased is Human
    assert sys.modules["HumGen3D.human.human"].__spec__.name == "HumGen3D.human.human"


def test_install_is_idempotent():
    before = alias.installed()
    alias.install()
    alias.install()
    assert alias.installed() is before
    assert sys.meta_path.count(before) == 1


def test_uninstall_removes_alias_entries_and_install_restores():
    import HG3D.human.human  # noqa: F401  make sure an alias entry exists

    try:
        alias.uninstall()
        assert alias.installed() is None
        assert "HG3D" not in sys.modules
        assert "HG3D.human.human" not in sys.modules
        assert "HumGen3D.human.human" in sys.modules
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("HG3D.human.human")
    finally:
        alias.install()
    assert alias.installed() is not None
    import HG3D.human.human as again

    assert again is sys.modules["HumGen3D.human.human"]


@pytest.fixture
def synthetic_packages(tmp_path, monkeypatch):
    """A real package with lazy submodules, and an alias finder for it."""
    real = "hg_alias_real_pkg"
    public = "hg_alias_public_pkg"
    pkg = tmp_path / real
    (pkg / "sub").mkdir(parents=True)
    (pkg / "__init__.py").write_text("VALUE = 1\n")
    (pkg / "sub" / "__init__.py").write_text("")
    (pkg / "sub" / "leaf.py").write_text(
        textwrap.dedent(
            """
            class Leaf:
                pass
            """
        )
    )
    (pkg / "eager.py").write_text("EAGER = True\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    finder = alias.AliasFinder((public,), real)
    sys.meta_path.insert(0, finder)
    try:
        yield real, public, finder
    finally:
        sys.meta_path.remove(finder)
        for name in list(sys.modules):
            if name.split(".")[0] in (real, public):
                del sys.modules[name]


def test_finder_answers_only_for_its_aliases(synthetic_packages):
    real, public, finder = synthetic_packages
    assert finder.find_spec("os") is None
    assert finder.find_spec(public + "_other") is None
    assert finder.real_name(public) == real
    assert finder.real_name(public + ".sub.leaf") == real + ".sub.leaf"
    assert finder.real_name("other") is None


def test_alias_root_is_the_real_package(synthetic_packages):
    real, public, _ = synthetic_packages
    aliased = importlib.import_module(public)
    assert aliased is importlib.import_module(real)
    assert aliased.VALUE == 1
    assert aliased.__name__ == real
    assert aliased.__spec__.name == real
    assert sys.modules[public] is sys.modules[real]


def test_alias_imports_submodules_lazily_as_one_object(synthetic_packages):
    real, public, _ = synthetic_packages
    importlib.import_module(public)
    assert real + ".sub.leaf" not in sys.modules
    leaf_alias = importlib.import_module(public + ".sub.leaf")
    assert real + ".sub.leaf" in sys.modules
    assert leaf_alias is sys.modules[real + ".sub.leaf"]
    assert leaf_alias.Leaf is sys.modules[real + ".sub.leaf"].Leaf
    # The module keeps its real identity, the alias only names it
    assert leaf_alias.__name__ == real + ".sub.leaf"
    assert leaf_alias.__package__ == real + ".sub"
    assert leaf_alias.__spec__.name == real + ".sub.leaf"
    assert leaf_alias.__spec__.origin.endswith("leaf.py")


def test_alias_after_real_import_is_the_same_module(synthetic_packages):
    real, public, _ = synthetic_packages
    eager = importlib.import_module(real + ".eager")
    assert importlib.import_module(public + ".eager") is eager


def test_from_import_through_alias(synthetic_packages):
    real, public, _ = synthetic_packages
    namespace = {}
    exec(f"from {public}.sub.leaf import Leaf", namespace)
    assert namespace["Leaf"] is sys.modules[real + ".sub.leaf"].Leaf


def test_missing_submodule_through_alias_is_not_found(synthetic_packages):
    _, public, _ = synthetic_packages
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(public + ".does_not_exist")


# Images without Pillow


@pytest.fixture
def source_png(tmp_path):
    image = bpy.data.images.new("hg_test_source", 64, 64)
    image.filepath_raw = str(tmp_path / "source.png")
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)
    return str(tmp_path / "source.png")


def _image_size(path):
    image = bpy.data.images.load(path, check_existing=False)
    try:
        return tuple(image.size)
    finally:
        bpy.data.images.remove(image)


@pytest.mark.parametrize("ext", [".png", ".tiff"])
def test_save_resized_writes_a_scaled_copy(source_png, tmp_path, ext):
    destination = str(tmp_path / "out" / "nested" / f"small{ext}")
    before = len(bpy.data.images)
    save_resized(source_png, destination, 16)
    assert os.path.isfile(destination)
    assert _image_size(destination) == (16, 16)
    assert _image_size(source_png) == (64, 64)
    assert len(bpy.data.images) == before, "leaves no image datablock behind"


def test_save_resized_rejects_unknown_formats(source_png, tmp_path):
    with pytest.raises(NotImplementedError):
        save_resized(source_png, str(tmp_path / "out.webp"), 16)


def test_file_format_names():
    assert file_format("a.png") == "PNG"
    assert file_format("a.PNG") == "PNG"
    assert file_format("a.tif") == "TIFF"
    assert file_format("a.tiff") == "TIFF"
    assert file_format("a.jpg") == "JPEG"
    with pytest.raises(NotImplementedError):
        file_format("a.exr")
