"""The setup flow state: modes, steps, catalogue, the trial download and the install from files, against fake services."""
import json
import os
import time

import pytest

from HumGen3D.backend.setup import online, update_check, user_settings
from HumGen3D.backend.setup.catalogue import Catalogue
from HumGen3D.user_interface.setup_overlay import state as setup_state
from HumGen3D.user_interface.setup_overlay.state import FAKE_CATALOGUE, FakeServices, SetupState


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(setup_state, "FAKE_DURATION", 0.2)
    monkeypatch.setattr(setup_state, "FAKE_INSTALL_SECONDS", 0.01)
    monkeypatch.setattr(setup_state, "FAKE_CHECK_SECONDS", 0.05)
    monkeypatch.setattr(setup_state, "_start_poll", lambda: None)
    monkeypatch.setenv(user_settings.ENV_OVERRIDE, str(tmp_path / "settings.json"))
    monkeypatch.setattr(setup_state, "RETRY_DELAYS", (0.0, 0.0, 0.0))
    monkeypatch.setattr(setup_state.repository, "trial_rid", lambda: None)
    monkeypatch.setattr(setup_state.migration, "find_existing_content", lambda: None)
    monkeypatch.setattr(online, "allowed", lambda: True)
    monkeypatch.setattr(update_check.status, "catalogue", None)
    monkeypatch.setattr(update_check, "cached_catalogue", lambda: None)


@pytest.fixture
def st(tmp_path):
    state = SetupState(services=FakeServices())
    state.folder = str(tmp_path / "content")
    return state


def wait_for(predicate, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def loaded(st):
    st.ensure_catalogue()
    assert wait_for(lambda: st.catalogue_phase == "ok"), st.catalogue_error
    return st


def write_installed(folder, key, version):
    packs = os.path.join(str(folder), "content_packs")
    os.makedirs(packs, exist_ok=True)
    with open(os.path.join(packs, f"{key}.json"), "w") as f:
        json.dump({"config": {"pack_name": key.replace("_", " "), "pack_version": list(version)}}, f)


FULL_FILES = ["/dl/Base_Humans_4_1.hgpack", "/dl/Base_Clothes_4_1.hgpack", "/dl/Base_Hair_4_1.hgpack"]


# The trial: a download


def test_trial_packs_lock_the_library(st):
    st.choose("trial")
    loaded(st)
    assert st.packs[0].key == "Trial_Content" and st.packs[0].required and st.packs[0].selected
    assert all(p.locked and not p.selected for p in st.packs[1:])
    assert all(p.tag == "Full version" for p in st.packs[1:])
    # Only the trial can be downloaded, whatever gets ticked
    for pack in st.packs:
        pack.selected = True
    assert [p.key for p in st.selected] == ["Trial_Content"]


def test_choose_and_back(st):
    """The welcome leads to the trial's pack list or to the file list, and
    back leads to the welcome: there is no step in between."""
    assert st.screen == "welcome" and st.mode == ""
    st.choose("trial")
    assert st.screen == "packs" and st.mode == "trial"
    st.back()
    assert st.screen == "welcome"
    st.choose("full")
    assert st.screen == "files" and st.mode == "full"
    st.back()
    assert st.screen == "welcome"
    assert "choose" not in setup_state.SCREENS


def test_fake_download_runs_to_done(st):
    st.choose("trial")
    loaded(st)
    st.start()
    assert st.active and st.screen == "slides" and st.phase == "downloading"
    assert wait_for(lambda: st.phase == "done")
    assert st.fraction == 1.0 and st.packs_done == 1
    st.finish_on_main_thread()  # fake services: no folder work, but it must not raise
    assert st.finalized


def test_abort_goes_back_to_packs(st):
    st.choose("trial")
    loaded(st)
    st.start()
    assert wait_for(lambda: st.done_bytes > 0)
    st.abort()
    assert st.phase == "idle" and st.screen == "packs"
    assert st.done_bytes == 0 and all(p.state == "pending" for p in st.packs)
    assert not st.worker.is_alive()
    st.start()
    assert wait_for(lambda: st.phase == "done")


def test_fake_download_failure_and_reset(st):
    st.choose("trial")
    loaded(st)
    st.start()
    st.fail()
    assert wait_for(lambda: st.phase == "failed")
    assert st.error
    st.reset()
    assert st.phase == "idle" and st.screen == "welcome" and st.mode == ""
    assert not st.prompted and not st.fallback_open and st.catalogue is None


def test_catalogue_failure_and_retry(st):
    st.services.catalogue_error = "down"
    st.choose("trial")
    assert wait_for(lambda: st.catalogue_phase == "failed")
    assert st.packs == [] and "down" in st.catalogue_error
    st.services.catalogue_error = None
    st.load_catalogue()
    assert wait_for(lambda: st.catalogue_phase == "ok")
    assert st.packs


def test_online_access_gate(st, monkeypatch):
    allowed = {"value": False}
    monkeypatch.setattr(online, "allowed", lambda: allowed["value"])
    monkeypatch.setattr(online, "allow", lambda: allowed.__setitem__("value", True) or True)
    st.choose("trial")
    assert st.online_blocked == "catalogue" and st.catalogue_phase == "idle"
    st.allow_online()
    assert st.online_blocked == "" and wait_for(lambda: st.catalogue_phase == "ok")
    allowed["value"] = False
    st.start()
    assert st.online_blocked == "start" and st.phase == "idle"
    st.allow_online()
    assert wait_for(lambda: st.phase == "done")


def test_trial_update_is_a_download(st, tmp_path):
    """An older trial pack in the folder: the update notice opens the trial's
    list with the newer version ticked."""
    write_installed(tmp_path / "content", "Trial_Content", (4, 0))
    st.begin_update()
    assert st.update_mode and st.prompted and st.screen == "packs" and st.mode == "trial"
    loaded(st)
    trial = st.packs[0]
    assert trial.key == "Trial_Content" and trial.status == "update_required" and trial.selected
    assert trial.installed_version == (4, 0) and trial.version == "4.1"
    # Update mode starts on the pack list: there is nothing to go back to
    assert not st.can_go_back
    st.back()
    assert st.screen == "packs"


def test_link_is_asked_right_before_the_download_and_again_on_a_new_run(st):
    """Signed links expire: ask right before the download, and again for a new run."""
    requests = []
    original = st.services.content_urls

    def content_urls(keys, rid, retry=""):
        requests.append(list(keys))
        return original(keys, rid)

    st.services.content_urls = content_urls
    st.choose("trial")
    loaded(st)
    st.start()
    assert wait_for(lambda: st.phase == "done")
    assert requests == [["Trial_Content"]]
    for pack in st.packs:
        pack.state = "pending"
    st.start()  # a new run asks again instead of reusing the old link
    assert wait_for(lambda: st.phase == "done")
    assert requests == [["Trial_Content"], ["Trial_Content"]]


def test_a_retry_tells_the_server_why(st):
    """The link request after a failed attempt carries that attempt's error
    code, also after the automatic retries ran out and the user presses Retry,
    so the server can count failed downloads by reason."""
    st.choose("trial")
    loaded(st)
    st.services.fail_times = 2
    st.start()
    assert wait_for(lambda: st.phase == "done")
    assert st.services.retries == ["", "offline", "offline"]
    st.services.retries.clear()
    for pack in st.packs:
        pack.state = "pending"
    st.services.fail_times = 99
    st.start()
    assert wait_for(lambda: st.phase == "failed")
    st.services.fail_times = 0
    st.services.retries.clear()
    st.start()
    assert wait_for(lambda: st.phase == "done")
    assert st.services.retries == ["offline"]


def test_the_trial_request_id_travels_with_the_link_request(st, monkeypatch):
    seen = []
    original = st.services.content_urls
    st.services.content_urls = lambda keys, rid, retry="": seen.append(rid) or original(keys, rid)
    monkeypatch.setattr(setup_state.repository, "trial_rid", lambda: "0123456789abcdef")
    st.begin_setup()
    st.choose("trial")
    loaded(st)
    st.start()
    assert wait_for(lambda: st.phase == "done")
    assert seen == ["0123456789abcdef"]
    assert user_settings.get("trial_rid") == "0123456789abcdef"


# The full version: files, and no request


def test_the_full_version_asks_no_server(st, monkeypatch):
    """Choosing the full version, picking files and installing them works
    with Blender's online access off, and nothing is requested."""
    monkeypatch.setattr(online, "allowed", lambda: False)
    st.services.fetch_catalogue = lambda: pytest.fail("the catalogue was requested")
    st.services.send_event = lambda *a, **k: pytest.fail("an event was sent")
    st.services.content_urls = lambda *a, **k: pytest.fail("a download link was requested")
    st.services.download = lambda *a, **k: pytest.fail("something was downloaded")
    st.choose("full")
    assert st.screen == "files" and st.local and st.packs == [] and not st.can_install
    assert st.catalogue_phase == "idle" and st.online_blocked == ""
    st.add_files(FULL_FILES)
    assert [p.key for p in st.packs] == ["Base_Humans", "Base_Clothes", "Base_Hair"]
    assert all(p.selected and p.installable and p.path for p in st.packs) and st.can_install
    st.start()
    assert st.phase == "installing" and st.screen == "slides" and st.online_blocked == ""
    assert wait_for(lambda: st.phase == "done"), st.error
    assert st.services.installed_from == FULL_FILES
    assert st.fraction == 1.0 and st.packs_done == 3


def test_file_rows_say_what_installing_does(st, tmp_path):
    folder = tmp_path / "content"
    write_installed(folder, "Base_Humans", (4, 0))
    write_installed(folder, "Base_Hair", (4, 1))
    write_installed(folder, "Base_Poses", (4, 1))
    st.begin_add_packs()
    st.add_files(FULL_FILES + ["/dl/Base_Poses_4_0.hgpack", "/dl/holiday.zip"])
    by_key = {p.key: p for p in st.packs}
    humans, clothes, hair, poses = (by_key[k] for k in ("Base_Humans", "Base_Clothes", "Base_Hair", "Base_Poses"))
    assert humans.status == "update_available" and humans.selected and humans.installed_version == (4, 0) and humans.tag == ""
    assert clothes.status == "missing" and clothes.selected
    assert hair.status == "up_to_date" and not hair.selected and hair.tag == "Installed"
    assert poses.status == "older" and poses.left_out and not poses.installable and poses.tag == "Older than installed"
    other = by_key["/dl/holiday.zip"]
    assert other.status == "not_a_pack" and other.left_out and other.tag == "Not a content pack"
    assert [p.key for p in st.selected] == ["Base_Humans", "Base_Clothes"]


def test_the_newest_file_of_a_pack_wins(st):
    st.choose("full")
    st.add_files(["/dl/Base_Humans_4_0.hgpack"])
    st.add_files(["/dl/Base_Humans_4_1.hgpack", "/dl/Base_Humans_4_1.hgpack"])
    assert [(p.key, p.version) for p in st.packs] == [("Base_Humans", "4.1")]
    assert st.packs[0].path == "/dl/Base_Humans_4_1.hgpack"


def test_an_unticked_file_stays_unticked_when_more_are_added(st):
    st.choose("full")
    st.add_files(FULL_FILES[:2])
    st.packs[1].selected = False
    st.add_files(FULL_FILES[2:])
    assert [p.selected for p in st.packs] == [True, False, True]
    st.clear_files()
    assert st.packs == [] and st.files == []


def test_a_file_older_than_the_add_on_needs_is_flagged_not_refused(st):
    st.choose("full")
    st.add_files(["/dl/Base_Humans_4_0.hgpack"])
    humans = st.packs[0]
    assert humans.installable and humans.selected and humans.needs_version == "4.1"


def test_base_humans_is_missed_when_absent(st, tmp_path):
    st.choose("full")
    assert not st.base_missing  # nothing picked yet
    st.add_files(FULL_FILES[1:])
    assert st.base_missing and st.can_install  # a remark, not a block
    st.add_files(FULL_FILES[:1])
    assert not st.base_missing
    st.clear_files()
    write_installed(tmp_path / "content", "Base_Humans", (4, 1))
    st.add_files(FULL_FILES[1:])
    assert not st.base_missing


def test_trial_user_installs_the_full_version_from_files(st, tmp_path):
    write_installed(tmp_path / "content", "Trial_Content", (4, 1))
    st.begin_full()
    assert st.screen == "files" and st.mode == "full" and st.upgrading_trial
    # The trial pack as a file is left out once the base pack is among the files
    st.add_files(["/dl/HG_Trial_Content.hgpack"] + FULL_FILES)
    by_key = {p.key: p for p in st.packs}
    assert by_key["Trial_Content"].status == "not_needed" and by_key["Trial_Content"].left_out
    st.start()
    assert wait_for(lambda: st.phase == "done"), st.error
    assert st.upgrading_trial and st.services.installed_from == FULL_FILES
    # Back from the file list returns to the trial's list
    st2 = SetupState(services=FakeServices())
    st2.folder = st.folder
    st2.begin_full()
    assert st2.can_go_back
    st2.back()
    assert st2.screen == "packs" and st2.mode == "trial"


def test_the_trial_pack_installs_from_a_file_too(st):
    """Without a connection the trial is a file like any other."""
    st.choose("full")
    st.add_files(["/dl/HG_Trial_Content.hgpack"])
    assert st.packs[0].key == "Trial_Content" and st.packs[0].status == "missing" and st.packs[0].selected
    assert not st.base_missing or st.can_install


def test_update_of_a_full_install_asks_for_the_files_by_name(st, tmp_path, monkeypatch):
    folder = tmp_path / "content"
    write_installed(folder, "Base_Humans", (4, 0))
    write_installed(folder, "Base_Clothes", (4, 1))
    write_installed(folder, "Base_Hair", (4, 1))
    monkeypatch.setattr(update_check.status, "catalogue", Catalogue.from_dict(FAKE_CATALOGUE))
    st.begin_update()
    assert st.screen == "files" and st.mode == "full" and st.update_mode and not st.can_go_back
    assert st.wanted == ("Base Humans 4.1",)
    assert st.catalogue_phase == "idle"  # the names come from the last check, nothing is fetched
    # A button that wants one pack
    st.begin_update(keys=["HG_Export"])
    assert st.screen == "files" and st.wanted == ("HG Export 1.0",)
    # Without any catalogue the key still names it
    monkeypatch.setattr(update_check.status, "catalogue", None)
    st.begin_update(keys=["HG_Export"])
    assert st.wanted == ("HG Export",)


def test_dropped_files_open_the_file_list(st, tmp_path):
    assert st.begin_files(FULL_FILES[:1])
    assert st.screen == "files" and st.mode == "full" and st.prompted and not st.add_packs
    assert [p.key for p in st.packs] == ["Base_Humans"]
    # More files on the open list are added to it
    assert st.begin_files(FULL_FILES[1:2])
    assert [p.key for p in st.packs] == ["Base_Humans", "Base_Clothes"]
    # An owner who drops a pack adds it
    write_installed(tmp_path / "content", "Base_Humans", (4, 1))
    st2 = SetupState(services=FakeServices())
    assert st2.begin_files(FULL_FILES[2:], str(tmp_path / "content"))
    assert st2.add_packs and st2.screen == "files" and [p.key for p in st2.packs] == ["Base_Hair"]
    # Not while an install runs
    st.start()
    assert not st.begin_files(FULL_FILES[2:])
    assert wait_for(lambda: st.phase == "done")


def test_a_failed_file_install_names_the_pack_and_can_be_retried(st):
    st.choose("full")
    st.add_files(FULL_FILES[:2])
    st.services.install_error = "disk"
    st.start()
    assert wait_for(lambda: st.phase == "failed")
    assert st.failure_code == "disk" and st.error.startswith("Base Humans: ") and "content folder" in st.error
    assert st.services.retries == []  # nothing is reported: no server is involved
    st.services.install_error = None
    st.start()
    assert wait_for(lambda: st.phase == "done"), st.error
    assert st.packs_done == 2


def test_files_need_room_for_what_they_unpack_to(st, monkeypatch):
    st.choose("full")
    st.add_files(FULL_FILES[:1])
    size = st.packs[0].size
    monkeypatch.setattr(setup_state.downloader, "free_space", lambda folder: 2 * size)
    assert st.space() == (2 * size, 2 * size) and st.space_ok and st.can_install
    st._free_key = ("", 0.0)
    monkeypatch.setattr(setup_state.downloader, "free_space", lambda folder: size)
    assert not st.space_ok and not st.can_install


def test_contact_support_fills_in_the_details(st):
    st.phase, st.failure_code, st.error = "failed", "checksum", "The download was damaged."
    details = st.support_details()
    assert "Download failed: checksum: The download was damaged." in details and "Blender " in details
    assert st.folder in details
    url = st.support_url()
    assert url.startswith("mailto:" + setup_state.SUPPORT_EMAIL + "?subject=Human%20Generator%20setup&body=")
    assert " " not in url and "checksum" in url
    # An install from a file says so, and names the file
    st.choose("full")
    st.add_files(FULL_FILES[:1])
    st.current = st.packs[0]
    st.phase, st.failure_code, st.error = "failed", "disk", "No room."
    details = st.support_details()
    assert "Install from file failed: disk: No room." in details and "File: Base_Humans_4_1.hgpack" in details


# Against the real downloader and installer


def test_real_services_download_flow_against_fake_server(tmp_path, monkeypatch):
    """The real worker with the real downloader and installer, URLs from a fake API."""
    from setup_fakes import Handler, make_pack
    import http.server
    import threading

    from HumGen3D.backend.setup import api_client
    from HumGen3D.user_interface.setup_overlay.state import RealServices

    pack_bytes = make_pack("Trial_Content", (1, 0), {"models/trial.blend": b"t"})
    Handler.files = {"/HG_Trial_Content.hgpack": pack_bytes}
    Handler.hits = []
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_port}/HG_Trial_Content.hgpack"
    try:
        catalogue = Catalogue.from_dict({"packs": [{"key": "Trial_Content", "name": "Trial Content", "access": "trial", "required": True, "versions": [{"version": [1, 0], "size": len(pack_bytes), "min_addon": "4.0.0", "file": "HG_Trial_Content.hgpack", "url": url}]}]})
        monkeypatch.setattr(api_client, "fetch_catalogue", lambda fields=None: catalogue)
        calls = []

        def content_urls(keys, rid="", retry=""):
            calls.append(list(keys))
            return {"files": {k: {"url": url, "size": len(pack_bytes)} for k in keys}, "errors": {}}

        monkeypatch.setattr(api_client, "content_urls", content_urls)
        st = SetupState(services=RealServices())
        st.folder = str(tmp_path / "content")
        st.choose("trial")
        loaded(st)
        st.start()
        assert wait_for(lambda: st.phase in ("done", "failed")), st.phase
        assert st.phase == "done", st.error
        assert os.path.exists(tmp_path / "content" / "models" / "trial.blend")
        assert os.path.exists(tmp_path / "content" / "content_packs" / "Trial_Content.json")
        assert not os.path.exists(tmp_path / "content" / "content_packs" / "downloads" / "HG_Trial_Content.hgpack")
        assert calls == [["Trial_Content"]]  # one request per pack, right before its download
    finally:
        httpd.shutdown()


def test_real_services_install_the_full_version_from_files_over_the_trial(tmp_path, monkeypatch):
    """Real `.hgpack` files, the real installer: the packs land in the folder,
    the files stay where they were, and the trial pack goes once the base
    pack is in. No request of any kind."""
    from setup_fakes import exists, make_pack, write_pack

    from HumGen3D.backend.setup import api_client, migration
    from HumGen3D.user_interface.setup_overlay.state import RealServices

    for name in ("request_json", "fetch_catalogue", "content_urls"):
        monkeypatch.setattr(api_client, name, lambda *a, **k: pytest.fail("a request was made"))
    monkeypatch.setattr(online, "allowed", lambda: False)

    folder = tmp_path / "content"
    write_pack(folder, "Trial_Content", (4, 1), ["models/HG_HUMAN.blend", "textures/trial_skin.png"])
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    files = {
        "Base_Humans_4_1.hgpack": make_pack("Base_Humans", (4, 1), {"models/HG_HUMAN.blend": b"full", "textures/skin.png": b"s"}),
        "Base_Hair_4_1.hgpack": make_pack("Base_Hair", (4, 1), {"hair/long.json": b"h"}),
        "notes.zip": b"not a zip at all",
    }
    for name, data in files.items():
        (downloads / name).write_bytes(data)

    st = SetupState(services=RealServices())
    st.folder = str(folder)
    st.begin_full()
    assert st.upgrading_trial
    st.add_files([str(downloads / name) for name in files])
    by_key = {p.key: p for p in st.packs}
    assert by_key["Base_Humans"].version == "4.1" and by_key["Base_Humans"].size == len(files["Base_Humans_4_1.hgpack"])
    assert by_key[str(downloads / "notes.zip")].status == "not_a_pack"
    assert [p.key for p in st.selected] == ["Base_Humans", "Base_Hair"]
    st.start()
    assert wait_for(lambda: st.phase in ("done", "failed")), st.phase
    assert st.phase == "done", st.error
    assert open(folder / "models" / "HG_HUMAN.blend", "rb").read() == b"full"
    assert exists(folder, "hair/long.json") and exists(folder, "content_packs/Base_Humans.json") and exists(folder, "content_packs/Base_Hair.json")
    # The picked files are the user's: untouched
    assert all((downloads / name).read_bytes() == data for name, data in files.items())
    assert not exists(folder, "content_packs/downloads")
    # What the main thread does next: the trial leaves, the shared model stays
    assert migration.cleanup_trial(str(folder))
    assert not exists(folder, "content_packs/Trial_Content.json") and not exists(folder, "textures/trial_skin.png")
    assert open(folder / "models" / "HG_HUMAN.blend", "rb").read() == b"full"
    # Picking the same files again: nothing left to do
    st.begin_add_packs()
    st.add_files([str(downloads / "Base_Humans_4_1.hgpack")])
    assert st.packs[0].status == "up_to_date" and not st.can_install
