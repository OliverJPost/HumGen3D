"""The setup flow state: modes, steps, catalogue, licence check and the download, against fake services."""
import json
import os
import time

import pytest

from HumGen3D.backend.setup import online, user_settings
from HumGen3D.backend.setup.catalogue import Catalogue
from HumGen3D.user_interface.setup_overlay import state as setup_state
from HumGen3D.user_interface.setup_overlay.state import FakeServices, SetupState


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


def test_trial_packs_lock_the_library(st):
    st.choose("trial")
    loaded(st)
    assert st.packs[0].key == "Trial_Content" and st.packs[0].required and st.packs[0].selected
    assert all(p.locked and not p.selected for p in st.packs[1:])
    assert all(p.tag == "Full version" for p in st.packs[1:])


def test_licensed_packs(st):
    st.set_mode("licensed")
    loaded(st)
    keys = [p.key for p in st.packs]
    assert keys[0] == "Base_Humans" and st.packs[0].required
    assert "Trial_Content" not in keys
    assert all(not p.locked for p in st.packs)


def test_choose_and_back(st):
    assert st.screen == "welcome" and st.mode == ""
    st.go("choose")
    st.back()
    assert st.screen == "welcome"
    st.go("choose")
    st.choose("trial")
    assert st.screen == "packs" and st.mode == "trial"
    st.back()
    assert st.screen == "choose"
    st.choose("licensed")
    assert st.screen == "license"
    st.screen = "packs"
    st.back()
    assert st.screen == "license"
    st.back()
    assert st.screen == "choose"


def test_guid_cleaning():
    from HumGen3D.user_interface.setup_overlay.state import clean_guid, looks_like_guid

    assert clean_guid('  {3F2B-9C1E}\n') == "3F2B-9C1E"
    assert looks_like_guid("#12345")
    assert looks_like_guid("3f2b9c1e-7d4a-4c1b-9e2f-5a6b7c8d9e0f")
    assert not looks_like_guid("")
    assert not looks_like_guid(" 12 ")


def test_activate_validates_the_form(st):
    assert not st.activate("", "a@b.co", True)
    assert "license key" in st.license_error
    assert not st.activate("3f2b9c1e-7d4a", "nope", True)
    assert "email" in st.license_error
    assert not st.activate("3f2b9c1e-7d4a", "a@b.co", False)
    assert "Accept" in st.license_error
    assert st.license_phase == "idle"


def test_activate_ok_goes_to_packs_and_remembers(st):
    st.choose("licensed")
    assert st.activate("3f2b9c1e-7d4a", "a@b.co", True, newsletter=True)
    assert st.checking
    assert wait_for(lambda: st.license_phase == "ok")
    assert st.mode == "licensed" and st.screen == "packs"
    saved = user_settings.load()
    assert saved["order_guid"] == "3f2b9c1e-7d4a" and saved["email"] == "a@b.co" and saved["newsletter"] is True
    assert saved["license"] == "commercial" and saved["activated_at"] and saved["terms_accepted_at"]
    assert user_settings.credential().status == "ok"
    assert st.activated
    # Next time, the licence screen is skipped
    st2 = SetupState(services=FakeServices())
    st2.choose("licensed")
    assert st2.screen == "packs"
    st2.screen = "packs"
    st2.back()
    assert st2.screen == "choose"


def test_activate_failed_stays(st):
    st.choose("licensed")
    assert st.activate("0000-fails", "a@b.co", True)
    assert wait_for(lambda: st.license_phase == "failed")
    assert st.screen == "license" and "couldn't find" in st.license_error
    assert not st.activated


class Form:
    def __init__(self, order_guid="", email="", accept_terms=False):
        self.order_guid = order_guid
        self.email = email
        self.accept_terms = accept_terms


def test_prefill_form(st):
    user_settings.save_credential("g", "e@x.io")
    form = Form(email="typed@x.io")
    st.prefill_form(form)
    assert form.order_guid == "g" and form.email == "typed@x.io"
    # Right after a step asked for it, the stored order replaces what was typed
    st.begin_change_credential()
    assert st.screen == "license" and st.prefill_due
    st.prefill_form(form)
    assert form.email == "e@x.io" and not st.prefill_due


def test_licence_keys_pass_the_form_check():
    from HumGen3D.user_interface.setup_overlay.state import clean_guid, looks_like_guid

    assert clean_guid(" HG3D-ABCDE-FGHJK-MNPQR-STVW \n") == "HG3D-ABCDE-FGHJK-MNPQR-STVW"
    assert looks_like_guid("hg3d-abcde")


def test_fake_download_runs_to_done(st):
    st.choose("trial")
    loaded(st)
    st.start()
    assert st.active and st.screen == "slides"
    assert wait_for(lambda: st.phase == "done")
    assert st.fraction == 1.0 and st.packs_done == 1
    st.finish_on_main_thread()  # fake services: no folder work, but it must not raise
    assert st.finalized


def test_abort_goes_back_to_packs(st):
    user_settings.save_credential("g", "e@x.io")
    st.set_mode("licensed")
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
    user_settings.save_credential("g", "e@x.io")
    st.set_mode("licensed")
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


def test_update_mode_preselects_updates(st, tmp_path):
    """Packs already in the folder count: old ones are selected, current ones shown as installed."""
    packs = tmp_path / "content" / "content_packs"
    packs.mkdir(parents=True)
    for key, version in (("Base_Humans", [4, 0]), ("Base_Poses", [4, 0])):
        (packs / f"{key}.json").write_text(json.dumps({"config": {"pack_name": key.replace("_", " "), "pack_version": version}}))
    st.begin_update()
    assert st.update_mode and st.prompted and st.screen == "packs" and st.mode == "licensed"
    loaded(st)
    by_key = {p.key: p for p in st.packs}
    assert by_key["Base_Humans"].status == "update_required" and by_key["Base_Humans"].selected
    assert by_key["Base_Humans"].installed_version == (4, 0) and by_key["Base_Humans"].version == "4.1"
    assert by_key["Base_Poses"].status == "up_to_date" and not by_key["Base_Poses"].selected
    # A standard pack this install lacks is offered too, but can be unticked
    assert by_key["Base_Clothes"].status == "missing" and by_key["Base_Clothes"].selected and not by_key["Base_Clothes"].required
    assert by_key["8K_Textures"].status == "missing" and not by_key["8K_Textures"].selected
    # Update mode starts on the pack list: there is nothing to go back to
    assert not st.can_go_back
    st.back()
    assert st.screen == "packs"


def test_links_are_fetched_per_pack_and_again_on_retry(st):
    """Signed links expire: ask right before each download, and again after a failure."""
    requests = []
    original = st.services.content_urls

    def content_urls(keys, credential, email, rid):
        requests.append(list(keys))
        return original(keys, credential, email, rid)

    st.services.content_urls = content_urls
    user_settings.save_credential("g", "e@x.io")
    st.set_mode("licensed")
    loaded(st)
    for pack in st.packs:
        pack.selected = pack.key in ("Base_Poses", "HG_Export")
    st.start()
    assert wait_for(lambda: st.phase == "done")
    assert requests == [["Base_Poses"], ["HG_Export"]]
    for pack in st.packs:
        pack.state = "pending"
    st.start()  # a new run asks again instead of reusing old links
    assert wait_for(lambda: st.phase == "done")
    assert len(requests) == 4


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
        monkeypatch.setattr(api_client, "fetch_catalogue", lambda: catalogue)
        calls = []

        def content_urls(keys, credential="", email="", rid=""):
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
