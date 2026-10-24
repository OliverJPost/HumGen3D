"""Which step the setup opens on, by what is already known, and how it
recovers: stored and rejected orders, retries, pauses, the server's switches."""
import json
import time

import pytest

from HumGen3D.backend.setup import api_client, downloader, online, user_settings
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


def finish(st):
    """Let the pending main-thread step run, as the poll does."""
    assert wait_for(lambda: not st.busy or st.pending)
    st.run_pending()


# Routing


def test_nothing_known_starts_on_welcome(st, folder):
    st.begin_setup(folder)
    assert st.screen == "welcome" and st.entry == "welcome" and st.prompted
    st.go("choose")
    st.choose("trial")
    assert st.screen == "packs" and st.mode == "trial"


def test_installed_content_opens_add_packs_without_trial(st, folder):
    install(folder, ("Base_Humans", (4, 1)), ("Base_Clothes", (4, 1)))
    st.begin_setup(folder)
    assert st.add_packs and st.screen == "packs" and st.mode == "licensed"
    assert not st.can_go_back  # no welcome or choice behind it
    loaded(st)
    keys = [p.key for p in st.packs]
    assert "Trial_Content" not in keys
    by_key = {p.key: p for p in st.packs}
    assert by_key["Base_Humans"].status == "up_to_date"
    assert not any(p.required for p in st.packs)  # an owner is never forced
    assert not by_key["8K_Textures"].selected


def test_a_licensed_install_never_gets_the_trial(st, folder):
    install(folder, ("Base_Humans", (4, 1)))
    st.choose("trial")
    assert st.mode == "licensed"
    user_settings.save_credential("g", "e@x.io")
    install(folder.replace("content", "other"), ("Trial_Content", (4, 1)))
    st.folder = folder.replace("content", "other")
    st.choose("trial")
    assert st.mode == "licensed"


def test_stored_order_skips_the_form(st, folder):
    user_settings.save_credential("g", "e@x.io", license="commercial")
    st.begin_setup(folder)
    assert st.screen == "packs" and st.mode == "licensed" and not st.add_packs


def test_trial_link_skips_the_choice(st, folder):
    user_settings.update(trial_rid="rid123")
    st.begin_setup(folder)
    assert st.screen == "welcome" and st.rid == "rid123"
    st.choose("trial")
    assert st.screen == "packs"
    st.back()
    assert st.screen == "welcome"
    st.choose("licensed")
    assert st.screen == "license"
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
    assert st.worker is None  # nothing downloaded
    assert not st.adopt_folder(folder.replace("content", "empty"))


def test_update_asks_the_order_only_at_install(st, folder):
    install(folder, ("Base_Humans", (4, 0)))
    st.begin_update(folder)
    assert st.screen == "packs" and st.update_mode
    loaded(st)
    assert {p.key for p in st.selected} >= {"Base_Humans"}
    st.start()
    assert st.screen == "license" and st.license_reason == "update" and st.phase == "idle"
    assert st.can_go_back
    st.back()  # "Not now"
    assert st.screen == "packs"
    st.start()
    assert st.activate("3f2b-9c1e", "a@b.co", True)
    assert wait_for(lambda: st.license_phase == "ok")
    assert st.pending == "start"
    st.run_pending()  # the poll goes on with the download the user chose
    assert st.phase in ("downloading", "installing", "done")
    assert wait_for(lambda: st.phase == "done")


def test_begin_upgrade_resets_a_finished_run(st, folder):
    install(folder, ("Trial_Content", (4, 1)))
    st.begin_setup(folder)
    loaded(st)
    st.phase = "done"
    st.screen = "done"
    st.begin_upgrade()
    assert st.phase == "idle" and st.screen == "license" and st.license_reason == "upgrade"
    assert st.mode == "licensed" and st.upgrading_trial
    st.back()
    assert st.screen == "packs" and st.mode == "trial"
    user_settings.save_credential("g", "e@x.io")
    st.begin_upgrade()
    assert st.screen == "packs" and st.mode == "licensed"


def test_change_credential_prefills_and_goes_on_in_update_mode(st, folder):
    user_settings.save_credential("old-order", "e@x.io")
    st.begin_change_credential()
    assert st.screen == "license" and st.license_reason == "change" and st.update_mode and st.prefill_due
    assert st.activate("new-order", "e@x.io", True)
    assert wait_for(lambda: st.license_phase == "ok")
    assert st.screen == "packs" and st.update_mode
    assert user_settings.credential().value == "new-order"


# Orders the server refuses


def test_rejection_keeps_the_credential_and_routes_to_the_form(st, folder):
    user_settings.save_credential("g", "e@x.io")
    st.set_mode("licensed")
    loaded(st)
    st.services.content_error = "not_found"
    st.start()
    assert wait_for(lambda: st.phase == "failed")
    assert st.credential_failed and st.failure_code == "not_found"
    cred = user_settings.credential()
    assert cred is not None and cred.value == "g" and cred.status == "rejected" and cred.error_code == "not_found"
    # Retry and "Enter license key" both lead to the form, filled in
    st.start()
    assert st.screen == "license" and st.license_reason == "rejected"
    assert "couldn't find" in st.license_error and st.prefill_due
    # The form check of the same order, refused again, marks it again; never forgets
    st.services.content_error = None
    assert st.activate("0-bad", "e@x.io", True)
    assert wait_for(lambda: st.license_phase == "failed")
    assert user_settings.credential().value == "g"


def test_activation_of_the_stored_order_marks_it_rejected(st):
    user_settings.save_credential("0abc", "e@x.io")
    assert st.activate("0abc", "e@x.io", True)
    assert wait_for(lambda: st.license_phase == "failed")
    cred = user_settings.credential()
    assert cred.value == "0abc" and cred.status == "rejected"


def test_transient_errors_keep_the_order(st):
    user_settings.save_credential("g", "e@x.io")
    st.set_mode("licensed")
    loaded(st)
    st.services.content_error = "unavailable"
    st.start()
    assert wait_for(lambda: st.phase == "failed")
    assert not st.credential_failed and st.failure_code == "unavailable"
    assert user_settings.credential().status == "ok"


def test_per_pack_errors_are_sentences(st):
    st.set_mode("trial")
    loaded(st)
    st.services.content_urls = lambda keys, c, e, r: {"files": {}, "errors": {k: "license_required" for k in keys}}
    for pack in st.packs:
        pack.url = None
        if pack.target is not None:
            pack.target.url = None
    st.start()
    assert wait_for(lambda: st.phase == "failed")
    assert "license_required" not in st.error and "Trial Content" in st.error


# Downloads


def test_retry_skips_packs_already_done(st):
    user_settings.save_credential("g", "e@x.io")
    st.set_mode("licensed")
    loaded(st)
    for pack in st.packs:
        pack.selected = pack.key in ("Base_Poses", "HG_Export")
    calls = []
    original = st.services.download

    def download(pack, url, dest, progress, cancel):
        calls.append(pack.key)
        if pack.key == "HG_Export" and calls.count("HG_Export") == 1:
            raise downloader.DownloadError("checksum")  # not retried automatically
        return original(pack, url, dest, progress, cancel)

    st.services.download = download
    st.start()
    assert wait_for(lambda: st.phase == "failed")
    assert calls == ["Base_Poses", "HG_Export"]
    st.start()
    assert wait_for(lambda: st.phase == "done")
    assert calls == ["Base_Poses", "HG_Export", "HG_Export"]
    assert st.fraction == 1.0


def test_dropped_connection_is_retried_with_a_fresh_link(st):
    st.set_mode("trial")
    loaded(st)
    links = []
    original = st.services.content_urls

    def content_urls(keys, credential, email, rid):
        links.append(list(keys))
        return original(keys, credential, email, rid)

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


def test_unknown_free_space_does_not_block(st, monkeypatch):
    monkeypatch.setattr(downloader, "free_space", lambda folder: None)
    st.set_mode("trial")
    loaded(st)
    needed, free = st.space()
    assert free is None and needed > 0 and st.space_ok and st.can_install


def test_license_tier_is_stored_after_every_link_request(st, monkeypatch):
    calls = []
    monkeypatch.setattr(user_settings, "update_license", lambda license, url: calls.append((license, url)) or True)
    user_settings.save_credential("g", "e@x.io", license="personal")
    st.services.license = "commercial"
    st.set_mode("licensed")
    loaded(st)
    for pack in st.packs:
        pack.selected = pack.key in ("Base_Poses", "HG_Export")
    st.start()
    assert wait_for(lambda: st.phase == "done")
    assert calls == [("commercial", None), ("commercial", None)]


def test_activation_stores_the_tier(st):
    st.services.license = "personal"
    assert st.activate("abcd-1234", "a@b.co", True)
    assert wait_for(lambda: st.license_phase == "ok")
    cred = user_settings.credential()
    assert cred.is_personal and cred.upgrade_url == setup_state.UPGRADE_URL


def test_update_can_tick_one_pack(st, folder):
    """The Process tab's "Install HG Export" opens update mode with only that pack ticked."""
    install(folder, ("Base_Humans", (4, 0)))
    st.begin_update(folder, keys=["HG_Export"])
    loaded(st)
    assert [p.key for p in st.selected] == ["HG_Export"]
    st.begin_update(folder)  # an ordinary update forgets it
    assert st.preselect == ()


def test_overlay_never_passes_input_through():
    """The overlay swallows every event while open: a key that reached the
    viewport (I, X, G, ...) would change the scene behind it."""
    import inspect

    from HumGen3D.user_interface.setup_overlay import operator

    source = inspect.getsource(operator.HG_OT_setup_overlay.modal)
    assert "PASS_THROUGH" not in source
    assert source.count("return {") == source.count('return {"RUNNING_MODAL"}') + source.count('return {"FINISHED"}')
