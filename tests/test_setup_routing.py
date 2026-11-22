"""Which step the setup opens on, by what is already known, and how it
recovers: retries, pauses, the server's switches."""
import json
import time

import pytest

from HumGen3D.backend.setup import downloader, online, update_check, user_settings
from HumGen3D.user_interface.setup_overlay import state as setup_state
from HumGen3D.user_interface.setup_overlay.state import FakeServices, SetupState


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(setup_state, "FAKE_DURATION", 0.1)
    monkeypatch.setattr(setup_state, "FAKE_INSTALL_SECONDS", 0.01)
    monkeypatch.setattr(setup_state, "FAKE_CHECK_SECONDS", 0.02)
    monkeypatch.setattr(setup_state, "RETRY_DELAYS", (0.0, 0.0, 0.0))
    monkeypatch.setattr(setup_state, "_start_poll", lambda: None)
    monkeypatch.setenv(user_settings.ENV_OVERRIDE, str(tmp_path / "settings.json"))
    monkeypatch.setattr(setup_state.repository, "trial_rid", lambda: None)
    monkeypatch.setattr(setup_state.migration, "find_existing_content", lambda: None)
    monkeypatch.setattr(online, "allowed", lambda: True)
    monkeypatch.setattr(update_check.status, "catalogue", None)
    monkeypatch.setattr(update_check, "cached_catalogue", lambda: None)


@pytest.fixture
def folder(tmp_path):
    return str(tmp_path / "content")


@pytest.fixture
def st(folder):
    state = SetupState(services=FakeServices())
    state.folder = folder
    return state


def install(folder, *packs):
    """Pack JSONs as an install leaves them: (key, version) pairs."""
    import os

    os.makedirs(os.path.join(folder, "content_packs"), exist_ok=True)
    for key, version in packs:
        with open(os.path.join(folder, "content_packs", key + ".json"), "w") as f:
            json.dump({"config": {"pack_name": key.replace("_", " "), "pack_version": list(version)}, "files": []}, f)


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


# Routing


def test_nothing_known_starts_on_welcome(st, folder):
    st.begin_setup(folder)
    assert st.screen == "welcome" and st.entry == "welcome" and st.prompted
    st.choose("trial")
    assert st.screen == "packs" and st.mode == "trial"


def test_installed_content_opens_the_file_list_without_trial(st, folder):
    install(folder, ("Base_Humans", (4, 1)), ("Base_Clothes", (4, 1)))
    st.begin_setup(folder)
    assert st.add_packs and st.screen == "files" and st.mode == "full"
    assert not st.can_go_back  # no welcome or choice behind it
    assert st.packs == [] and st.catalogue_phase == "idle"  # an owner's setup asks no server


def test_an_install_with_the_full_library_never_gets_the_trial(st, folder):
    install(folder, ("Base_Humans", (4, 1)))
    st.choose("trial")
    assert st.mode == "full" and st.screen == "files"


def test_trial_link_skips_the_choice(st, folder):
    user_settings.update(trial_rid="rid123")
    st.begin_setup(folder)
    assert st.screen == "welcome" and st.rid == "rid123"
    st.choose("trial")
    assert st.screen == "packs"
    st.back()
    assert st.screen == "welcome"
    st.choose("full")
    assert st.screen == "files"
    st.back()
    assert st.screen == "welcome"


def test_trial_install_shows_its_pack_list(st, folder):
    install(folder, ("Trial_Content", (4, 1)))
    st.begin_setup(folder)
    assert st.mode == "trial" and st.screen == "packs"
    loaded(st)
    assert st.trial_installed_here
    assert [p.key for p in st.packs if not p.locked] == ["Trial_Content"]


def test_found_content_is_offered_and_adopted(st, folder, monkeypatch):
    install(folder, ("Base_Humans", (4, 1)))
    monkeypatch.setattr(setup_state.migration, "find_existing_content", lambda: folder)
    st.folder = folder.replace("content", "empty")
    st.begin_setup()
    assert st.screen == "welcome" and st.found_folder == folder
    assert st.adopt_folder(folder)
    assert st.phase == "done" and st.screen == "done" and st.adopted and st.folder == folder
    assert st.worker is None  # nothing installed
    assert not st.adopt_folder(folder.replace("content", "empty"))


def test_begin_full_resets_a_finished_run(st, folder):
    install(folder, ("Trial_Content", (4, 1)))
    st.begin_setup(folder)
    loaded(st)
    st.phase = "done"
    st.screen = "done"
    st.begin_full()
    assert st.phase == "idle" and st.screen == "files"
    assert st.mode == "full" and st.upgrading_trial and st.packs == []
    st.back()
    assert st.screen == "packs" and st.mode == "trial"
    assert [p.key for p in st.packs if not p.locked] == ["Trial_Content"]


def test_a_new_way_in_forgets_the_files_of_the_last(st, folder):
    st.begin_full(folder)
    st.add_files(["/dl/Base_Humans_4_1.hgpack"])
    assert st.packs
    st.begin_full(folder)
    assert st.packs == [] and st.files == []


def test_update_of_a_trial_downloads_and_of_an_owner_asks_for_files(st, folder):
    install(folder, ("Trial_Content", (4, 0)))
    st.begin_update(folder)
    assert st.screen == "packs" and st.mode == "trial" and st.update_mode
    other = folder.replace("content", "owner")
    install(other, ("Base_Humans", (4, 0)))
    st.begin_update(other)
    assert st.screen == "files" and st.mode == "full" and st.update_mode
    # A button that wants one pack opens the file list for it, also from a trial
    st.begin_update(folder, keys=["HG_Export"])
    assert st.screen == "files" and st.wanted == ("HG Export",)
    st.begin_update(other)  # an ordinary update forgets it
    assert st.wanted == ()


# Errors


def test_per_pack_errors_are_sentences(st):
    st.set_mode("trial")
    loaded(st)
    st.services.content_urls = lambda keys, rid, retry="": {"files": {}, "errors": {k: "license_required" for k in keys}}
    for pack in st.packs:
        pack.url = None
        if pack.target is not None:
            pack.target.url = None
    st.start()
    assert wait_for(lambda: st.phase == "failed")
    assert "license_required" not in st.error and "Trial Content" in st.error and "full version" in st.error


def test_a_server_problem_ends_the_download_with_its_code(st):
    st.set_mode("trial")
    loaded(st)
    st.services.content_error = "unavailable"
    st.start()
    assert wait_for(lambda: st.phase == "failed")
    assert st.failure_code == "unavailable" and st.error


# Downloads


def test_retry_skips_packs_already_done(st):
    """Two files, the second fails once: Retry installs only that one."""
    st.choose("full")
    st.add_files(["/dl/Base_Poses_4_0.hgpack", "/dl/HG_Export_1_0.hgpack"])
    calls = []
    original = st.services.install

    def install_file(zip_path, folder, cancel, progress=None):
        calls.append(zip_path)
        if "HG_Export" in zip_path and len(calls) == 2:
            raise downloader.DownloadError("disk")
        return original(zip_path, folder, cancel, progress)

    st.services.install = install_file
    st.start()
    assert wait_for(lambda: st.phase == "failed")
    assert calls == ["/dl/Base_Poses_4_0.hgpack", "/dl/HG_Export_1_0.hgpack"]
    st.start()
    assert wait_for(lambda: st.phase == "done")
    assert calls[2:] == ["/dl/HG_Export_1_0.hgpack"]
    assert st.fraction == 1.0


def test_dropped_connection_is_retried_with_a_fresh_link(st):
    st.set_mode("trial")
    loaded(st)
    links = []
    original = st.services.content_urls

    def content_urls(keys, rid, retry=""):
        links.append(list(keys))
        return original(keys, rid)

    st.services.content_urls = content_urls
    st.services.fail_times = 2
    st.start()
    assert wait_for(lambda: st.phase in ("done", "failed"))
    assert st.phase == "done", st.error
    assert links == [["Trial_Content"]] * 3
    assert st.retry_attempt == 0 and not st.retry_at


def test_retries_give_up(st):
    st.set_mode("trial")
    loaded(st)
    st.fail()
    st.start()
    assert wait_for(lambda: st.phase == "failed")
    assert st.failure_code == "offline"


def test_pause_keeps_progress_and_resumes(st, monkeypatch):
    monkeypatch.setattr(setup_state, "FAKE_DURATION", 3.0)
    st.set_mode("trial")
    loaded(st)
    st.start()
    assert wait_for(lambda: st.done_bytes > 0)
    st.pause()
    assert wait_for(lambda: st.phase == "paused")
    assert st.in_progress and not st.active
    kept = st.done_bytes
    assert kept > 0
    monkeypatch.setattr(setup_state, "FAKE_DURATION", 0.1)
    st.start()
    assert st.done_bytes >= kept  # resumes, does not start over
    assert wait_for(lambda: st.phase == "done")


def test_an_install_from_files_can_not_be_paused(st, monkeypatch):
    """Extraction doesn't stop halfway: Pause does nothing while files install."""
    monkeypatch.setattr(setup_state, "FAKE_INSTALL_SECONDS", 0.3)
    st.choose("full")
    st.add_files(["/dl/Base_Humans_4_1.hgpack"])
    st.start()
    st.pause()
    assert st.phase == "installing"
    assert wait_for(lambda: st.phase == "done")


def test_download_lock_held_elsewhere(st):
    st.set_mode("trial")
    loaded(st)
    st.services.lock_taken = True
    st.start()
    assert st.lock_blocked and st.phase == "idle"
    st.services.lock_taken = False
    st.start()
    assert not st.lock_blocked and wait_for(lambda: st.phase == "done")


def test_setup_disabled_by_the_server(st):
    st.services.catalogue_extra = {"setup": False, "message": "Back on Monday."}
    st.set_mode("trial")
    loaded(st)
    assert st.downloads_paused and st.server_message == "Back on Monday."
    assert not st.can_install
    st.start()
    assert st.phase == "idle" and st.worker is not None and not st.worker.is_alive()
    # The switch stops downloads. Files on this computer install regardless
    st.choose("full")
    st.add_files(["/dl/Base_Humans_4_1.hgpack"])
    assert st.can_install
    st.start()
    assert wait_for(lambda: st.phase == "done")


def test_unknown_free_space_does_not_block(st, monkeypatch):
    monkeypatch.setattr(downloader, "free_space", lambda folder: None)
    st.set_mode("trial")
    loaded(st)
    needed, free = st.space()
    assert free is None and needed > 0 and st.space_ok and st.can_install


def test_update_of_the_trial_can_tick_one_pack(st, folder):
    install(folder, ("Trial_Content", (4, 0)))
    st.begin_update(folder)
    loaded(st)
    assert [p.key for p in st.selected] == ["Trial_Content"]


def test_overlay_never_passes_input_through():
    """The overlay swallows every event while open: a key that reached the
    viewport (I, X, G, ...) would change the scene behind it."""
    import inspect

    from HumGen3D.user_interface.setup_overlay import operator

    source = inspect.getsource(operator.HG_OT_setup_overlay.modal)
    assert "PASS_THROUGH" not in source
    assert source.count("return {") == source.count('return {"RUNNING_MODAL"}') + source.count('return {"FINISHED"}')
