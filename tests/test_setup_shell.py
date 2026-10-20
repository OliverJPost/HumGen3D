# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The add-on around the setup: the content folder as the panels and the
preferences read it, the trial, the buy links, the licence row, the install
notices and the startup that must never raise.

The real extension loading and the double install are covered by
`test_extension_mode.py`.
"""
import ntpath
import os
import posixpath
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import bpy
import pytest

from HumGen3D.backend.content import content_packs, content_state
from HumGen3D.backend.preferences import licence
from HumGen3D.backend.setup.user_settings import Credential
from HumGen3D.human.process import export_pack
from HumGen3D.package import (
    MIN_BLENDER,
    blender_supported,
    is_extension_package,
    other_copies,
)
from HumGen3D.tests.setup_fakes import write_pack


@pytest.fixture(scope="module", autouse=True)
def addon():
    if not bpy.context.preferences.addons.get("HumGen3D"):
        bpy.ops.preferences.addon_enable(module="HumGen3D")


@pytest.fixture(autouse=True)
def fresh_cache():
    content_state.clear()
    yield
    content_state.clear()


def prefs_at(monkeypatch, folder):
    """Point the content pack code at `folder`, without touching the real preferences."""
    fake = SimpleNamespace(filepath=folder, filepath_=folder)
    monkeypatch.setattr(content_packs, "get_prefs", lambda: fake)
    return fake


# The content_packs folder


def test_cpack_folder_keeps_unc_paths():
    assert content_packs.cpack_folder("\\\\nas\\share\\HG\\", ntpath) == "\\\\nas\\share\\HG\\content_packs"
    assert content_packs.cpack_folder("\\\\nas\\share\\HG", ntpath) == "\\\\nas\\share\\HG\\content_packs"
    assert content_packs.cpack_folder("C:\\HumGen\\", ntpath) == "C:\\HumGen\\content_packs"


def test_cpack_folder_posix():
    assert content_packs.cpack_folder("/Volumes/Studio/HG/", posixpath) == "/Volumes/Studio/HG/content_packs"
    assert content_packs.cpack_folder("/Volumes/Studio/HG", posixpath) == "/Volumes/Studio/HG/content_packs"


def test_empty_folder_is_never_the_root():
    assert content_packs.cpack_folder("") == ""
    assert content_packs.cpack_json_files("") == []


def test_cpack_json_files_creates_nothing(tmp_path):
    missing = tmp_path / "unplugged" / "HG"
    assert content_packs.cpack_json_files(str(missing)) == []
    assert not missing.exists()
    empty = tmp_path / "empty"
    empty.mkdir()
    assert content_packs.cpack_json_files(str(empty)) == []
    assert not (empty / "content_packs").exists()


def test_cpack_json_files_lists_the_packs(tmp_path):
    write_pack(str(tmp_path), "Base_Humans", (4, 1))
    write_pack(str(tmp_path), "Base_Hair", (4, 1))
    (tmp_path / "content_packs" / "notes.txt").write_text("not a pack")
    names = [os.path.basename(p) for p in content_packs.cpack_json_files(str(tmp_path))]
    assert names == ["Base_Hair.json", "Base_Humans.json"]


def _no_makedirs(*args, **kwargs):
    raise AssertionError("cpacks_refresh must not create folders")


@pytest.mark.parametrize("folder_kind", ["missing", "empty", "unset"])
def test_cpacks_refresh_never_creates_folders(tmp_path, monkeypatch, folder_kind):
    folder = {"missing": str(tmp_path / "gone"), "empty": str(tmp_path), "unset": ""}[folder_kind]
    prefs_at(monkeypatch, folder)
    monkeypatch.setattr(os, "makedirs", _no_makedirs)
    monkeypatch.setattr(os, "mkdir", _no_makedirs)
    content_packs.cpacks_refresh(None, bpy.context)
    # Only the fake header row
    assert [item.name for item in bpy.context.scene.contentpacks_col] == ["header"]
    assert not (tmp_path / "gone").exists()
    assert not (tmp_path / "content_packs").exists()


def test_cpacks_refresh_skips_a_broken_pack(tmp_path, monkeypatch):
    write_pack(str(tmp_path), "Base_Humans", (4, 1))
    (tmp_path / "content_packs" / "Broken.json").write_text('{"config": null}')
    prefs_at(monkeypatch, str(tmp_path))
    content_packs.cpacks_refresh(None, bpy.context)
    names = [item.name for item in bpy.context.scene.contentpacks_col]
    assert names == ["header", "Base Humans"]


def test_delete_keeps_files_another_pack_lists(tmp_path, monkeypatch):
    folder = str(tmp_path)
    shared = "models/HG_HUMAN.blend"
    for rel in (shared, "textures/trial.png"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    write_pack(folder, "Base_Humans", (4, 1), files=[shared])
    write_pack(folder, "Trial_Content", (4, 0), files=[shared, "textures/trial.png"])
    prefs_at(monkeypatch, folder)
    content_packs.cpacks_refresh(None, bpy.context)
    assert bpy.ops.hg3d.cpackdel(item_name="Trial Content") == {"FINISHED"}
    assert (tmp_path / shared).exists()
    assert not (tmp_path / "textures" / "trial.png").exists()
    assert not (tmp_path / "content_packs" / "Trial_Content.json").exists()


# Content state and the trial


def test_content_states(tmp_path):
    assert content_state.state("") == "unset"
    assert content_state.state(str(tmp_path / "unplugged")) == "unreachable"
    assert content_state.state(str(tmp_path)) == "empty"
    write_pack(str(tmp_path), "Base_Humans", (4, 1))
    content_state.clear()
    assert content_state.state(str(tmp_path)) == "installed"


def test_is_trial_is_the_catalogue_definition(tmp_path):
    folder = str(tmp_path)
    write_pack(folder, "Trial_Content", (4, 0))
    assert content_state.is_trial(folder)
    # A buyer who installed the full packs without removing the trial pack
    write_pack(folder, "Base_Humans", (4, 1))
    content_state.clear()
    assert not content_state.is_trial(folder)


def test_prefs_is_trial_follows_the_folder(tmp_path):
    prefs = bpy.context.preferences.addons["HumGen3D"].preferences
    before = prefs.filepath_
    try:
        prefs.filepath_ = str(tmp_path)
        write_pack(str(tmp_path), "Trial_Content", (4, 0))
        assert prefs.is_trial
        write_pack(str(tmp_path), "Base_Humans", (4, 1))
        content_state.clear()
        assert not prefs.is_trial
    finally:
        prefs.filepath_ = before


def test_dev_content_folder_only_from_the_environment(monkeypatch):
    prefs = bpy.context.preferences.addons["HumGen3D"].preferences
    before = prefs.filepath_
    try:
        prefs.filepath_ = ""
        monkeypatch.delenv("HUMGEN_DEV_CONTENT", raising=False)
        assert prefs.filepath == ""
        monkeypatch.setenv("HUMGEN_DEV_CONTENT", "/some/content/")
        assert prefs.filepath == "/some/content/"
        prefs.filepath_ = "/chosen/"
        assert prefs.filepath == "/chosen/"
    finally:
        prefs.filepath_ = before


# Buy links


def _query(url):
    parsed = urlparse(url)
    return parsed.netloc + parsed.path, {k: v[0] for k, v in parse_qs(parsed.query).items()}


def test_buy_url_names_the_panel_and_the_trial():
    where, query = _query(licence.buy_url("top_widget", "0123456789abcdef"))
    assert where == "humgen3d.com/pricing"
    assert query == {
        "utm_source": "addon",
        "utm_medium": "ui_link",
        "utm_campaign": "trial_click",
        "utm_content": "top_widget",
        "hg_rid": "0123456789abcdef",
    }


def test_buy_url_without_a_trial_rid():
    _, query = _query(licence.buy_url("process", None))
    assert "hg_rid" not in query
    assert query["utm_content"] == "process"


def test_buy_operator_opens_the_link(monkeypatch):
    from HumGen3D.backend.setup import user_settings

    opened = []
    operator = bpy.ops.hg3d.buy_full_version
    user_settings.update(trial_rid="fedcba9876543210")
    monkeypatch.setattr(bpy.ops, "wm", SimpleNamespace(url_open=lambda url: opened.append(url) or {"FINISHED"}))
    try:
        assert operator(panel="content") == {"FINISHED"}
    finally:
        user_settings.update(trial_rid=None)
    _, query = _query(opened[0])
    assert query["utm_content"] == "content"
    assert query["hg_rid"] == "fedcba9876543210"


# The licence row of the preferences


def credential(**changes):
    values = dict(
        value="1f2e3d4c-aaaa-bbbb-cccc-1234567a1b2c",
        email="jane@example.com",
        kind="superhive",
        license="personal",
        status="ok",
        error_code="",
        error_message="",
        upgrade_url="",
    )
    values.update(changes)
    return Credential(**values)


def test_no_row_without_a_credential():
    assert licence.licence_row(None) is None


def test_personal_licence_offers_the_upgrade():
    row = licence.licence_row(credential())
    assert row.tier == "Personal licence"
    assert row.upgrade
    assert not row.rejected
    assert row.summary.startswith("Order \u2022\u2022\u2022\u20221b2c")
    assert "j\u2022\u2022\u2022@example.com" in row.summary
    assert "jane" not in row.summary


def test_commercial_licence_has_no_upgrade():
    row = licence.licence_row(credential(license="commercial"))
    assert row.tier == "Commercial licence"
    assert not row.upgrade


def test_unknown_tier_shows_no_label():
    row = licence.licence_row(credential(license=None))
    assert row.tier == ""
    assert not row.upgrade


def test_licence_key_is_named_as_such():
    row = licence.licence_row(credential(value="HG3D-AAAAA-BBBBB-CCCCC-9Z9Z", kind="key"))
    assert row.summary.startswith("Licence key \u2022\u2022\u2022\u20229Z9Z")


def test_rejected_credential_keeps_the_row_with_the_reason():
    row = licence.licence_row(
        credential(status="rejected", error_code="refunded", error_message="This order was refunded.")
    )
    assert row.rejected
    assert row.message == "This order was refunded."
    assert not row.upgrade
    assert licence.support_url("refunded").startswith("mailto:support@humgen3d.com?subject=")


# Export data notice


def test_export_pack_message_points_at_the_setup(monkeypatch, tmp_path):
    monkeypatch.setattr(export_pack, "content_folder", lambda: str(tmp_path))
    message = export_pack.message("missing")
    assert message.startswith("Export data not installed")
    assert "Superhive" not in message and "BlenderMarket" not in message
    assert "Superhive" not in export_pack.message("outdated")


# Install notices


def test_other_copies_of_the_extension():
    enabled = ["cycles", "HumGen3D", "bl_ext.user_default.humgen3d", "bl_ext.blender_org.other"]
    assert other_copies(enabled, "bl_ext.user_default.humgen3d") == ["HumGen3D"]
    assert other_copies(enabled, "HumGen3D") == ["bl_ext.user_default.humgen3d"]
    assert other_copies(["cycles"], "HumGen3D") == []
    assert is_extension_package("bl_ext.humgen3d_com.humgen3d")
    assert not is_extension_package("bl_ext.user_default.humgen3d_tools")
    assert not is_extension_package("HumGen3D")


def test_blender_versions():
    assert MIN_BLENDER == (4, 2, 0)
    assert not blender_supported((4, 0, 1))
    assert not blender_supported((4, 1, 1))
    assert blender_supported((4, 2, 0))
    assert blender_supported((5, 1, 0))
    assert blender_supported()


def test_registered_in_full_mode():
    import HumGen3D
    from HumGen3D.user_interface import install_notices

    assert HumGen3D._mode == "full"
    assert install_notices.startup_mode() == "full"
    assert not hasattr(bpy.types, "HG_PT_notice_twice")
    assert not hasattr(bpy.types, "HG_PT_notice_unsupported")


def test_notice_classes_have_their_own_names():
    from HumGen3D.user_interface import install_notices

    idnames = {}
    for mode in ("unsupported", "twice", "old_copy"):
        idnames[mode] = [getattr(cls, "bl_idname") for cls in install_notices.notice_classes(mode)]
    assert "hg3d.use_new_version" in idnames["twice"]
    assert "hg3d.switch_off_old_copy" in idnames["old_copy"]
    assert idnames["unsupported"][0] == "HG_PT_notice_unsupported"
    # The add-on's own classes are never among them
    assert not any(name in ("HG_PT_Panel", "HG_PT_SETUP") for names in idnames.values() for name in names)


def test_preference_values_round_trip():
    from HumGen3D.user_interface import install_notices

    prefs = bpy.context.preferences.addons["HumGen3D"].preferences
    before = (prefs.units, prefs.filepath_)
    try:
        prefs.units = "imperial"
        prefs.filepath_ = "/Volumes/Studio/HG/"
        values = install_notices.preference_values(prefs)
        assert values["filepath_"] == "/Volumes/Studio/HG/"
        prefs.units = "metric"
        prefs.filepath_ = ""
        install_notices.apply_preference_values(prefs, values)
        assert prefs.units == "imperial"
        assert prefs.filepath_ == "/Volumes/Studio/HG/"
    finally:
        prefs.units, prefs.filepath_ = before


# Startup


def test_hg_start_never_raises(monkeypatch):
    import HumGen3D
    from HumGen3D.backend.setup import migration, update_check

    scheduled = []

    def broken():
        raise PermissionError("the drive went away")

    monkeypatch.setattr(migration, "resolve_content_folder", broken)
    monkeypatch.setattr(update_check, "schedule", lambda *a, **k: scheduled.append(True))
    HumGen3D.HG_start(None)
    assert scheduled == [True]


# Drawing, with a stand-in layout that records the buttons


class FakeLayout:
    """Takes every UILayout call; records the labels and operators drawn."""

    def __init__(self, log=None):
        self.log = log if log is not None else []

    def __getattr__(self, name):
        def call(*args, **kwargs):
            if name == "label":
                self.log.append(("label", kwargs.get("text", "")))
            elif name == "operator":
                self.log.append(("operator", args[0] if args else kwargs.get("operator"), kwargs.get("text", "")))
            return FakeLayout(self.log)

        return call

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)


class DrawProxy:
    """The real preferences, drawing into a FakeLayout."""

    def __init__(self, prefs, layout):
        object.__setattr__(self, "_prefs", prefs)
        object.__setattr__(self, "layout", layout)

    def __getattr__(self, name):
        import types

        from HumGen3D.backend.preferences.preferences import HG_PREF

        attr = getattr(HG_PREF, name, None)
        if isinstance(attr, types.FunctionType):
            return types.MethodType(attr, self)
        return getattr(self._prefs, name)


def draw_prefs(folder, tab="cpacks"):
    from HumGen3D.backend.preferences.preferences import HG_PREF

    prefs = bpy.context.preferences.addons["HumGen3D"].preferences
    before = prefs.filepath_
    layout = FakeLayout()
    proxy = DrawProxy(prefs, layout)
    object.__setattr__(proxy, "pref_tabs", tab)
    try:
        prefs.filepath_ = folder
        content_state.clear()
        HG_PREF.draw(proxy, bpy.context)
    finally:
        prefs.filepath_ = before
    return layout.log


def texts(log):
    return [entry[-1] for entry in log]


def operators(log):
    return [entry[1] for entry in log if entry[0] == "operator"]


@pytest.fixture
def stored_credential():
    from HumGen3D.backend.setup import user_settings

    def store(**values):
        user_settings.save_credential("1f2e3d4c-aaaa-bbbb-cccc-1234567a1b2c", "jane@example.com", **values)

    yield store
    user_settings.forget_credential()


def test_prefs_unreachable_folder_card(tmp_path):
    log = draw_prefs(str(tmp_path / "unplugged"))
    assert "Can't find your content folder" in texts(log)
    assert {"hg3d.content_folder_retry", "hg3d.pathchange", "hg3d.setup_start"} <= set(operators(log))


def test_prefs_empty_folder_offers_the_setup_without_file_install(tmp_path):
    log = draw_prefs(str(tmp_path))
    assert "hg3d.setup_start" in operators(log)
    assert "hg3d.cpackselect" not in operators(log)
    assert not any("Superhive" in text for text in texts(log))


def test_prefs_installed_content_tab(tmp_path, stored_credential):
    write_pack(str(tmp_path), "Base_Humans", (4, 1))
    stored_credential(license="personal")
    log = draw_prefs(str(tmp_path))
    ops = operators(log)
    # An owner adding packs goes straight to the pack list
    assert "hg3d.setup_add_packs" in ops and "hg3d.setup_start" not in ops
    assert "Personal licence" in texts(log)
    assert {"hg3d.setup_open_upgrade", "hg3d.setup_change_licence", "hg3d.setup_forget_licence"} <= set(ops)
    # Packs of other creators: closed by default
    assert "hg3d.cpackselect" not in ops
    joined = " ".join(texts(log))
    assert "Superhive" not in joined and "First delete the Trial" not in joined and "!" not in joined


def test_prefs_commercial_licence_has_no_upgrade(tmp_path, stored_credential):
    write_pack(str(tmp_path), "Base_Humans", (4, 1))
    stored_credential(license="commercial")
    log = draw_prefs(str(tmp_path))
    assert "Commercial licence" in texts(log)
    assert "hg3d.setup_open_upgrade" not in operators(log)


def test_prefs_rejected_credential_alert(tmp_path, stored_credential):
    from HumGen3D.backend.setup import user_settings

    write_pack(str(tmp_path), "Base_Humans", (4, 1))
    stored_credential(license="personal")
    user_settings.mark_credential_rejected("refunded", "This order was refunded.")
    log = draw_prefs(str(tmp_path))
    assert "This order was refunded." in texts(log)
    assert "Enter again…" in texts(log) and "Contact support" in texts(log)
    assert "hg3d.setup_open_upgrade" not in operators(log)


def test_prefs_settings_tab_hides_the_obsolete_switch(tmp_path):
    write_pack(str(tmp_path), "Base_Humans", (4, 1))
    log = draw_prefs(str(tmp_path), tab="settings")
    assert log  # drew without raising
    prefs = bpy.context.preferences.addons["HumGen3D"].preferences
    assert prefs.bl_rna.properties["skip_url_request"].is_hidden


def test_main_panel_banner_never_stops_the_panel(monkeypatch):
    from HumGen3D.backend.setup import update_check
    from HumGen3D.user_interface.ui_baseclasses import HGPanel

    monkeypatch.setattr(type(update_check.status), "notice", lambda self: "required")
    panel = SimpleNamespace(layout=FakeLayout())
    assert HGPanel._update_notification(panel, panel.layout) is None
    assert "Content update needed" in texts(panel.layout.log) or (
        "A newer Human Generator is needed for the latest content." in texts(panel.layout.log)
    )


def test_main_panel_unreachable_card(tmp_path):
    from HumGen3D.user_interface.ui_baseclasses import HGPanel

    layout = FakeLayout()
    panel = SimpleNamespace(pref=SimpleNamespace(filepath=str(tmp_path / "unplugged")), _setup_prompt=HGPanel._setup_prompt)
    assert not HGPanel._content_found(panel, layout)
    assert "Can't find your content folder" in texts(layout.log)
    layout = FakeLayout()
    panel.pref.filepath = str(tmp_path)
    content_state.clear()
    assert not HGPanel._content_found(panel, layout)
    assert "No content installed yet" in texts(layout.log)
