# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""The HG_Export content pack the process system needs, see export_pack.py.

The other process tests run with the pack installed in the content folder.
These point the pack at an empty or outdated content folder of their own.
"""

import json
import os
from types import SimpleNamespace

import bpy
import pytest
from HumGen3D import ExportPackMissing, ExportSettings, HumGenException
from HumGen3D.backend.preferences.preference_func import get_prefs
from HumGen3D.human.process import export_pack, game_rig
from HumGen3D.human.process.settings import OutputSettings, recipe_items
from HumGen3D.tests.process.test_process_ui import (
    ContextProxy,
    LayoutRecorder,
    PanelStandIn,
    _bound,
    _draw_all,
)
from HumGen3D.user_interface.process_panel.process_panel import HG_PT_PROCESS
from HumGen3D.tests.test_fixtures import *


def _pack_folder(folder, version=(1, 0), data=True):
    """A content folder with the manifest of the pack, and the data when asked."""
    os.makedirs(folder / "content_packs", exist_ok=True)
    manifest = {"config": {"pack_name": "HG Export", "pack_version": list(version)}}
    (folder / "content_packs" / "HG_Export.json").write_text(json.dumps(manifest))
    if data:
        os.makedirs(folder / "process" / "recipes", exist_ok=True)
        (folder / "process" / "recipes" / "order.json").write_text("[]")
    return folder


@pytest.fixture
def without_pack(tmp_path, monkeypatch):
    """The pack looks in an empty content folder."""
    monkeypatch.setattr(export_pack, "content_folder", lambda: str(tmp_path))
    return tmp_path


def test_installed():
    assert export_pack.status() == "installed"
    assert export_pack.installed_version() >= export_pack.REQUIRED_VERSION
    assert os.path.isfile(export_pack.data_path("game_rig_presets.json"))


def test_missing(without_pack):
    assert export_pack.status() == "missing"
    assert not export_pack.is_installed()
    assert export_pack.message().startswith("Export data not installed")
    assert "Install HG Export" in export_pack.message()


def test_manifest_without_data_is_missing(without_pack):
    _pack_folder(without_pack, data=False)
    assert export_pack.status() == "missing"


def test_outdated(without_pack):
    _pack_folder(without_pack, version=(0, 9))
    assert export_pack.status() == "outdated"
    assert "needs an update" in export_pack.message()
    with pytest.raises(ExportPackMissing, match="needs an update"):
        export_pack.require()


def test_unreadable_manifest_is_outdated(without_pack):
    _pack_folder(without_pack)
    (without_pack / "content_packs" / "HG_Export.json").write_text("not json")
    assert export_pack.status() == "outdated"


def test_status_follows_the_manifest(without_pack):
    """The status is cached by the time the manifest changed."""
    _pack_folder(without_pack, version=(0, 9))
    assert export_pack.status() == "outdated"
    _pack_folder(without_pack, version=(9, 0))
    path = without_pack / "content_packs" / "HG_Export.json"
    stat = path.stat()
    os.utime(path, (stat.st_atime, stat.st_mtime + 10))
    assert export_pack.status() == "installed"


def test_error_is_a_humgen_exception():
    assert issubclass(ExportPackMissing, HumGenException)


def test_data_needs_the_pack(without_pack):
    with pytest.raises(ExportPackMissing, match="Export data not installed"):
        ExportSettings.from_recipe("unity")
    with pytest.raises(ExportPackMissing):
        recipe_items()
    with pytest.raises(ExportPackMissing):
        game_rig.presets()


def test_settings_without_recipe_still_work(without_pack):
    """Building settings by hand needs no data, running them does."""
    settings = ExportSettings()
    assert ExportSettings.from_json(settings.to_json()) == settings


def test_api_needs_the_pack(male_human, without_pack, tmp_path, context):
    process = male_human.process
    settings = ExportSettings()
    calls = [
        lambda: process.run(settings, context=context),
        lambda: process.run_steps(settings, context=context),
        lambda: process.preflight(settings, context=context),
        lambda: process.set_t_pose_as_rest(context=context),
        lambda: process.convert_to_game_rig(names="unreal", context=context),
        lambda: process.apply_names(OutputSettings()),
        lambda: process.lod,
        lambda: process.baking,
        lambda: male_human.export.write(str(tmp_path / "jake.fbx"), OutputSettings(format="fbx"), context=context),
    ]
    for call in calls:
        with pytest.raises(ExportPackMissing):
            call()

    # Nothing changed, and the read-only properties still answer
    assert not process.has_t_pose_rest
    assert not process.has_game_rig
    assert not process.is_lod
    assert process.settings is None


def test_operators_need_the_pack(without_pack):
    assert not bpy.ops.hg3d.process.poll()
    assert not bpy.ops.hg3d.init_process.poll()
    assert not bpy.ops.hg3d.reset_recipe.poll()


def _operators(context):
    """Operator and text of every button the main panel draws."""
    log = []
    _bound(HG_PT_PROCESS, PanelStandIn(HG_PT_PROCESS, LayoutRecorder(log)), "draw")(context)
    return [(args[0], kwargs.get("text")) for name, args, kwargs in log if name == "operator"]


def test_panel_without_pack(male_human, without_pack, context):
    context.scene.HG3D.ui.active_tab = "PROCESS"
    rig = male_human.objects.rig
    drawn, labels = _draw_all(ContextProxy(rig, [rig]))
    assert drawn == ["HG_PT_PROCESS"], "The sections are hidden without the pack"
    assert "Export data not installed" in labels
    operators = _operators(ContextProxy(rig, [rig]))
    assert ("hg3d.setup_update", "Install HG Export") in operators
    assert not any("Superhive" in (text or "") for _, text in operators), "No manual download"
    assert not any(op == "hg3d.process" for op, _ in operators)


def test_panel_with_outdated_pack(male_human, without_pack, context):
    _pack_folder(without_pack, version=(0, 9))
    context.scene.HG3D.ui.active_tab = "PROCESS"
    rig = male_human.objects.rig
    _, labels = _draw_all(ContextProxy(rig, [rig]))
    assert "Export data needs an update" in labels


def test_trial_without_pack(male_human, without_pack, context, monkeypatch):
    from HumGen3D.user_interface.process_panel import process_panel

    prefs = SimpleNamespace(is_trial=True, experimental_features=False)
    monkeypatch.setattr(process_panel, "get_prefs", lambda: prefs)
    context.scene.HG3D.ui.active_tab = "PROCESS"
    rig = male_human.objects.rig
    _, labels = _draw_all(ContextProxy(rig, [rig]))
    assert "Disabled in Trial Version" in labels
    assert "Export data not installed" not in labels
