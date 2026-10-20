"""The content catalogue: parsing, version picking, the plan against a content folder."""
import json
import os

import pytest

from HumGen3D.backend.setup import catalogue as cat
from HumGen3D.backend.setup.catalogue import Catalogue, PackStatus, installed_packs, plan

SAMPLE = {
    "schema": 1,
    "addon": {"latest": "4.1.0", "min_blender": "4.0.0"},
    "packs": [
        {"key": "Base_Humans", "name": "Base Humans", "access": "licensed", "required": True, "order": 10,
         "versions": [
             {"version": [4, 1], "size": 100, "sha256": "ab", "min_addon": "4.0.0", "file": "Base_Humans_4_1.hgpack"},
             {"version": [5, 0], "size": 200, "sha256": "cd", "min_addon": "4.2.0", "file": "Base_Humans_5_0.hgpack"},
         ]},
        {"key": "Base_Poses", "name": "Base Poses", "access": "licensed", "order": 40,
         "versions": [{"version": [4, 0], "size": 50, "sha256": None, "min_addon": "4.0.0", "file": "Base_Poses_4_0.hgpack"}]},
        {"key": "HG_Export", "name": "HG Export", "access": "licensed", "required": True, "order": 70,
         "versions": [{"version": [1, 0], "size": 10, "sha256": None, "min_addon": "4.0.30", "file": "HG_Export_1_0.hgpack"}]},
        {"key": "8K_Textures", "name": "8K Textures", "access": "licensed", "required": False, "preselected": False, "order": 80,
         "versions": [{"version": [4, 0], "size": 2124241021, "sha256": None, "min_addon": "4.0.0", "file": "8K_Textures_OPTIONAL_V4_0.hgpack"}]},
        {"key": "Trial_Content", "name": "Trial Content", "access": "trial", "required": True, "order": 5,
         "versions": [{"version": [1, 0], "size": 300, "sha256": "ef", "min_addon": "4.0.0", "file": "HG_Trial_Content.hgpack", "url": "https://downloads.example/HG_Trial_Content.hgpack"}]},
    ],
}


def write_pack(folder, key, version, name=None, files=()):
    packs = os.path.join(folder, "content_packs")
    os.makedirs(packs, exist_ok=True)
    with open(os.path.join(packs, key + ".json"), "w") as f:
        json.dump({"config": {"pack_name": name or key.replace("_", " "), "pack_version": list(version), "creator": "HumGen"}, "files": list(files)}, f)


@pytest.fixture
def catalogue():
    return Catalogue.from_dict(SAMPLE)


def test_parse_versions():
    assert cat.parse_version("4.1.0") == (4, 1, 0)
    assert cat.parse_version([4, 1]) == (4, 1)
    assert cat.parse_version("junk") == (0,)
    assert cat.pad((4, 1)) == (4, 1, 0)
    assert cat.version_text((4, 1)) == "4.1"


def test_catalogue_sorted_and_versions_newest_first(catalogue):
    assert [p.key for p in catalogue.packs] == ["Trial_Content", "Base_Humans", "Base_Poses", "HG_Export", "8K_Textures"]
    assert catalogue.get("8K_Textures").preselected is False and catalogue.get("Base_Poses").preselected is True
    humans = catalogue.get("Base_Humans")
    assert [v.version for v in humans.versions] == [(5, 0), (4, 1)]
    assert catalogue.latest_addon == (4, 1, 0)
    assert catalogue.get("Trial_Content").free and not humans.free


def test_best_version_respects_min_addon(catalogue):
    humans = catalogue.get("Base_Humans")
    assert humans.best_for((4, 0, 38)).version == (4, 1)
    assert humans.best_for((4, 2, 0)).version == (5, 0)
    assert catalogue.get("HG_Export").best_for((4, 0, 27)) is None
    assert catalogue.get("HG_Export").best_for((4, 0, 30)).version == (1, 0)


def test_bad_catalogue_rejected():
    with pytest.raises(ValueError):
        Catalogue.from_dict({"nope": 1})
    with pytest.raises(ValueError):
        Catalogue.from_json("not json")


def test_installed_packs(tmp_path):
    write_pack(tmp_path, "Base_Humans", (4, 0), files=["models/HG_HUMAN.blend"])
    write_pack(tmp_path, "My_Pack", (1, 0), name="My Pack")
    with open(tmp_path / "content_packs" / "broken.json", "w") as f:
        f.write("{")
    found = installed_packs(str(tmp_path))
    assert set(found) == {"Base_Humans", "My_Pack"}
    assert found["Base_Humans"].version == (4, 0)
    assert found["Base_Humans"].files == ["models/HG_HUMAN.blend"]
    assert found["My_Pack"].name == "My Pack"
    assert installed_packs("") == {} and installed_packs(str(tmp_path / "nothing")) == {}


def test_trial_detection(tmp_path):
    write_pack(tmp_path, "Trial_Content", (1, 0))
    assert cat.is_trial_install(installed_packs(str(tmp_path)))
    write_pack(tmp_path, "Base_Humans", (4, 1))
    assert not cat.is_trial_install(installed_packs(str(tmp_path)))
    assert cat.has_humans(installed_packs(str(tmp_path)))


def test_plan_fresh_licensed(catalogue):
    statuses = plan(catalogue, {}, (4, 0, 38), "licensed")
    by_key = {s.key: s for s in statuses}
    assert "Trial_Content" not in by_key
    assert by_key["Base_Humans"].status == "missing" and by_key["Base_Humans"].target.version == (4, 1)
    assert by_key["HG_Export"].status == "missing"
    assert by_key["Base_Poses"].status == "missing"


def test_plan_trial_locks_the_library(catalogue):
    statuses = plan(catalogue, {}, (4, 0, 38), "trial")
    by_key = {s.key: s for s in statuses}
    assert by_key["Trial_Content"].status == "missing" and by_key["Trial_Content"].target.url
    assert all(by_key[k].status == "locked" for k in ("Base_Humans", "Base_Poses", "HG_Export", "8K_Textures"))


def test_plan_after_auto_update(catalogue, tmp_path):
    """A user on old packs after the add-on updated: required, available and missing."""
    write_pack(tmp_path, "Base_Humans", (4, 0))
    write_pack(tmp_path, "Base_Poses", (4, 0))
    installed = installed_packs(str(tmp_path))
    by_key = {s.key: s for s in plan(catalogue, installed, (4, 0, 38), "licensed")}
    assert by_key["Base_Humans"].status == "update_required"  # REQUIRED says 4.1
    assert by_key["Base_Poses"].status == "up_to_date"
    assert by_key["HG_Export"].status == "missing"
    ups = cat.updates(by_key.values())
    assert [u.key for u in ups] == ["Base_Humans", "HG_Export"]  # HG Export is new and part of a standard install
    assert not cat.version_blocks_packs(by_key.values())


def test_plan_needs_newer_addon(catalogue, tmp_path):
    """The catalogue only has versions for a newer add-on: say so instead of offering them."""
    by_key = {s.key: s for s in plan(catalogue, {}, (4, 0, 27), "licensed")}
    assert by_key["HG_Export"].status == "needs_newer_addon" and by_key["HG_Export"].target is None
    assert cat.version_blocks_packs(by_key.values())
    assert cat.addon_update_available(catalogue, (4, 0, 27))
    assert not cat.addon_update_available(catalogue, (4, 1, 0))


def test_plan_update_available_not_required(catalogue, tmp_path):
    write_pack(tmp_path, "Base_Humans", (4, 1))
    by_key = {s.key: s for s in plan(catalogue, installed_packs(str(tmp_path)), (4, 2, 0), "licensed")}
    assert by_key["Base_Humans"].status == "update_available"
    assert by_key["Base_Humans"].target.version == (5, 0)
    assert isinstance(by_key["Base_Humans"], PackStatus) and by_key["Base_Humans"].needs_install


def test_catalogue_switches_and_schema():
    plain = Catalogue.from_dict(SAMPLE)
    assert plain.schema == 1 and plain.supported
    assert plain.notices and plain.setup_enabled
    assert plain.message == plain.message_url == plain.upgrade_url == ""
    data = dict(SAMPLE, addon={"latest": "4.1.0", "notices": False, "setup": False, "message": "Downloads are slow today.", "message_url": "https://humgen3d.com/status", "upgrade_url": "https://humgen3d.com/upgrade"})
    switched = Catalogue.from_dict(data)
    assert not switched.notices and not switched.setup_enabled
    assert switched.message == "Downloads are slow today." and switched.message_url.endswith("/status")
    assert switched.upgrade_url == "https://humgen3d.com/upgrade"
    newer = Catalogue.from_dict(dict(SAMPLE, schema=cat.SUPPORTED_SCHEMA + 1))
    assert not newer.supported and newer.get("Base_Humans") is not None  # the pack list is still read
    assert not Catalogue.from_dict(dict(SAMPLE, schema="1")).supported
    assert Catalogue.from_dict({k: v for k, v in SAMPLE.items() if k != "schema"}).supported
    assert Catalogue.from_dict(dict(SAMPLE, addon=None)).notices
    with pytest.raises(ValueError):
        Catalogue.from_dict({"packs": None})


def test_unpacked_size_and_required_space():
    data = json.loads(json.dumps(SAMPLE))
    data["packs"][0]["versions"][0]["unpacked_size"] = 150  # Base_Humans 4.1
    catalogue = Catalogue.from_dict(data)
    statuses = {s.key: s for s in plan(catalogue, {}, (4, 0, 38), "licensed")}
    assert statuses["Base_Humans"].target.unpacked_size == 150
    assert statuses["Base_Poses"].target.unpacked_size is None
    # Every pack unpacked (twice the zip when unknown), plus the largest zip
    selected = [statuses["Base_Humans"], statuses["Base_Poses"]]
    assert cat.required_space(selected) == 150 + 2 * 50 + 100
    assert cat.required_space([]) == 0
    assert cat.required_space([statuses["HG_Export"], statuses["Base_Poses"]]) == 2 * 10 + 2 * 50 + 50


def test_install_mode(tmp_path):
    assert cat.install_mode({}) == "licensed"
    write_pack(tmp_path, "Trial_Content", (4, 1))
    assert cat.install_mode(installed_packs(str(tmp_path))) == "trial"
    write_pack(tmp_path, "Base_Humans", (4, 1))
    assert cat.install_mode(installed_packs(str(tmp_path))) == "licensed"
    assert cat.REQUIRED["Trial_Content"] == (4, 1)


def test_malformed_pack_json_is_skipped(tmp_path):
    write_pack(tmp_path, "Base_Humans", (4, 1), files=["models/HG_HUMAN.blend"])
    packs = tmp_path / "content_packs"
    (packs / "NullConfig.json").write_text(json.dumps({"config": None, "files": ["a"]}))
    (packs / "BadFiles.json").write_text(json.dumps({"config": {"pack_name": "x"}, "files": "abc"}))
    (packs / "List.json").write_text("[1, 2]")
    (packs / "BadConfig.json").write_text(json.dumps({"config": "nope"}))
    (packs / "Odd.json").write_text(json.dumps({"config": {"pack_name": None, "pack_version": "x"}, "files": ["a", 3, None]}))
    found = installed_packs(str(tmp_path))
    assert set(found) == {"Base_Humans", "NullConfig", "Odd"}
    assert found["NullConfig"].name == "NullConfig" and found["NullConfig"].files == ["a"]
    assert found["Odd"].version == (0,) and found["Odd"].files == ["a"]


def test_plan_trial_locks_unknown_access(catalogue):
    data = json.loads(json.dumps(SAMPLE))
    data["packs"].append({"key": "Future", "name": "Future", "access": "members", "versions": [{"version": [1, 0], "file": "f", "min_addon": "4.0.0"}]})
    by_key = {s.key: s for s in plan(Catalogue.from_dict(data), {}, (4, 0, 38), "trial")}
    assert by_key["Future"].status == "locked"
