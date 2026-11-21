"""The three events of an install from the trial page: the setup opened, the
trial is installed, the full version is installed. Each its own request, at
its moment, once; nothing for an install without a trial link, and nothing
about a trial on the update check."""
import http.server
import json
import threading
import time

import pytest

from HumGen3D.backend.setup import api_client, online, repository, trial_events, update_check, user_settings
from HumGen3D.tests.setup_fakes import write_pack
from HumGen3D.user_interface.setup_overlay import state as setup_state
from HumGen3D.user_interface.setup_overlay.state import FakeServices, SetupState

CATALOGUE = {"schema": 1, "addon": {"latest": "4.0.38"}, "packs": [{"key": "Trial_Content", "name": "Trial Content", "access": "trial", "required": True, "versions": [{"version": [4, 1], "size": 10, "min_addon": "4.0.0", "file": "HG_Trial_Content.hgpack"}]}]}
RID = "0123456789abcdef"
BARE_CHECK = ("GET", "/api/addon/catalogue", None)


class Server(http.server.BaseHTTPRequestHandler):
    requests = []  # (method, path, body)

    def log_message(self, *args):
        pass

    def _answer(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length)) if length else None
        Server.requests.append((self.command, self.path, body))
        data = json.dumps(CATALOGUE if self.command == "GET" else {"ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = _answer
    do_POST = _answer


@pytest.fixture(scope="module")
def server():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Server)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


@pytest.fixture
def folder(tmp_path, monkeypatch, server):
    """An empty content folder, an empty settings file, the client pointed at the local server."""
    monkeypatch.setenv(user_settings.ENV_OVERRIDE, str(tmp_path / "settings.json"))
    monkeypatch.setenv(api_client.ENV_BASE_URL, server)
    monkeypatch.delenv("HUMGEN_FAKE_SETUP", raising=False)
    monkeypatch.setattr(repository, "trial_rid", lambda: None)
    monkeypatch.setattr(online, "allowed", lambda: True)
    content = tmp_path / "content"
    content.mkdir()
    monkeypatch.setattr(update_check, "content_folder", lambda: str(content))
    monkeypatch.setattr(update_check, "_save_cache", lambda text: None)
    Server.requests = []
    yield str(content)
    assert wait_for(trial_events.idle)
    update_check.stop()  # the check's timer, which nothing runs in a test


def wait_for(predicate, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def run_check():
    """One update check, as the daily timer runs it, drained as the main thread does."""
    assert update_check.check_now()
    assert wait_for(lambda: not update_check._results.empty())
    while update_check.status.checking:
        update_check._drain()
    assert not update_check.status.error, update_check.status.error


def report(folder, send=None):
    """A moment at which something may have become true; waits for the thread."""
    started = trial_events.report(folder, send=send)
    assert wait_for(trial_events.idle)
    return started


def events():
    """The events the server got: (event, trial id)."""
    return [(body["event"], body["trial"]) for method, path, body in Server.requests if path == "/api/trial"]


def test_content_state_of_a_folder(tmp_path):
    folder = str(tmp_path)
    assert trial_events.content(folder) == "none" and trial_events.content("") == "none"
    write_pack(folder, "Trial_Content", (4, 1))
    assert trial_events.content(folder) == "trial"
    write_pack(folder, "Base_Humans", (4, 1))
    assert trial_events.content(folder) == "full"


def test_what_is_due(folder):
    # No trial link: no id, nothing to say, whatever is installed or shown
    user_settings.mark_setup_shown()
    assert trial_events.due(folder, None) == [] and trial_events.due(folder, "") == []
    # Not an id as the trial links carry it: nothing either
    assert trial_events.due(folder, "rid123") == []
    assert trial_events.due(folder, RID) == ["setup_opened"]
    write_pack(folder, "Trial_Content", (4, 1))
    assert trial_events.due(folder, RID) == ["setup_opened", "trial_installed"]
    trial_events._store(RID, "sent", ["setup_opened", "trial_installed"])
    assert trial_events.due(folder, RID) == []
    write_pack(folder, "Base_Humans", (4, 1))
    assert trial_events.due(folder, RID) == ["full_installed"]
    trial_events._store(RID, "sent", ["full_installed"])
    assert trial_events.due(folder, RID) == []
    everything = list(trial_events.EVENTS)
    assert user_settings.get(trial_events.STORE_KEY) == {"trial": RID, "seen": everything, "sent": everything}
    # Another trial link is another trial
    assert trial_events.due(folder, "fedcba9876543210") == ["setup_opened", "full_installed"]


def test_the_setup_not_shown_yet_is_not_an_event(folder):
    assert trial_events.due(folder, RID) == []
    write_pack(folder, "Trial_Content", (4, 1))
    assert trial_events.due(folder, RID) == ["trial_installed"]


def test_the_trial_id_comes_from_the_file_in_the_zip(tmp_path, monkeypatch):
    """The site adds `trial.json` to the zip a trial lead downloads; any other
    install has none, and a file that is not that says nothing."""
    monkeypatch.setattr(repository, "addon_root", lambda: str(tmp_path))
    assert repository.trial_rid() is None
    file = tmp_path / repository.TRIAL_FILE
    file.write_text(json.dumps({"trial": RID}) + "\n")
    assert repository.trial_rid() == RID
    for content in ("", "not json", "[]", '{"trial": 5}', '{"trial": "RID123"}', json.dumps({"trial": RID + "0"}), json.dumps({"rid": RID})):
        file.write_text(content)
        assert repository.trial_rid() is None, content


def test_a_stray_trial_file_never_ships():
    """A developer's own `trial.json` stays out of the released zip."""
    import tomllib

    from HumGen3D.package import manifest_path

    with open(manifest_path(), "rb") as f:
        manifest = tomllib.load(f)
    assert "/" + repository.TRIAL_FILE in manifest["build"]["paths_exclude_pattern"]


def test_trial_rid_is_remembered(folder, monkeypatch):
    assert trial_events.trial_rid() is None
    monkeypatch.setattr(repository, "trial_rid", lambda: RID)
    assert trial_events.trial_rid() == RID
    # The repository was removed later: the id stays known
    monkeypatch.setattr(repository, "trial_rid", lambda: None)
    assert trial_events.trial_rid() == RID


def test_an_install_without_a_trial_link_sends_nothing(folder):
    """Someone who installed the zip, or bought without a trial: no event at
    any of the moments, and the bare update check."""
    user_settings.mark_setup_shown()
    assert not report(folder)
    write_pack(folder, "Base_Humans", (4, 1))
    assert not report(folder)
    update_check._report_trial_events()
    run_check()
    assert Server.requests == [BARE_CHECK]
    assert user_settings.get(trial_events.STORE_KEY) is None


def test_each_event_is_its_own_request_at_its_moment_and_once(folder, monkeypatch):
    """The whole path of a trial lead, as the server sees it."""
    monkeypatch.setattr(repository, "trial_rid", lambda: RID)
    assert not report(folder)  # nothing happened yet
    user_settings.mark_setup_shown()
    assert report(folder)
    assert events() == [("setup_opened", RID)]
    assert not report(folder)
    write_pack(folder, "Trial_Content", (4, 1))
    assert report(folder)
    assert not report(folder)
    assert events() == [("setup_opened", RID), ("trial_installed", RID)]
    # The full version is installed from files: its event is the only request of that
    write_pack(folder, "Base_Humans", (4, 1))
    assert len(Server.requests) == 2
    assert report(folder)
    assert not report(folder)
    update_check._report_trial_events()
    assert wait_for(trial_events.idle)
    assert events() == [("setup_opened", RID), ("trial_installed", RID), ("full_installed", RID)]
    # The update check says nothing about the trial
    run_check()
    assert Server.requests[3:] == [BARE_CHECK]


def test_the_request_reads_as_what_it_is(folder, monkeypatch):
    """What the privacy policy describes: a plainly named event, the trial
    id under its own name, the versions, and nothing else."""
    monkeypatch.setattr(repository, "trial_rid", lambda: RID)
    write_pack(folder, "Trial_Content", (4, 1))
    assert report(folder)
    method, path, body = Server.requests[0]
    assert (method, path) == ("POST", "/api/trial")
    assert body == dict(api_client.client_info(), event="trial_installed", trial=RID)
    assert set(body) == {"event", "trial", "addon", "blender", "platform"}


def test_a_failed_send_stays_due(folder, monkeypatch):
    monkeypatch.setattr(repository, "trial_rid", lambda: RID)
    write_pack(folder, "Trial_Content", (4, 1))
    live = api_client.base_url()
    monkeypatch.setenv(api_client.ENV_BASE_URL, "http://127.0.0.1:9")
    assert report(folder)
    assert events() == [] and trial_events.due(folder, RID) == ["trial_installed"]
    # The full version was installed before the server could be reached
    # again: the trial's event is not lost, and comes first
    write_pack(folder, "Base_Humans", (4, 1))
    assert report(folder)
    assert events() == [] and trial_events.due(folder, RID) == ["trial_installed", "full_installed"]
    # The next start of Blender sends both
    monkeypatch.setenv(api_client.ENV_BASE_URL, live)
    update_check._report_trial_events()
    assert wait_for(trial_events.idle)
    assert events() == [("trial_installed", RID), ("full_installed", RID)] and trial_events.due(folder, RID) == []


def test_nothing_while_online_access_is_off(folder, monkeypatch):
    monkeypatch.setattr(repository, "trial_rid", lambda: RID)
    write_pack(folder, "Base_Humans", (4, 1))
    monkeypatch.setattr(online, "allowed", lambda: False)
    assert not report(folder)
    assert not update_check.check_now()
    assert Server.requests == []
    assert user_settings.get(trial_events.STORE_KEY) == {"trial": RID, "seen": ["full_installed"], "sent": []}
    # Switched on later: the event is still due
    monkeypatch.setattr(online, "allowed", lambda: True)
    assert report(folder)
    assert events() == [("full_installed", RID)]


def test_the_prototype_mode_sends_nothing(folder, monkeypatch):
    monkeypatch.setattr(repository, "trial_rid", lambda: RID)
    write_pack(folder, "Trial_Content", (4, 1))
    monkeypatch.setenv("HUMGEN_FAKE_SETUP", "1")
    assert not report(folder)
    assert Server.requests == []


def test_a_moment_during_a_send_is_not_lost(folder, monkeypatch):
    """The trial finished installing while the setup's event was on its way."""
    monkeypatch.setattr(repository, "trial_rid", lambda: RID)
    user_settings.mark_setup_shown()
    sent, gate = [], threading.Event()

    def slow_send(event, rid):
        gate.wait(5)
        sent.append(event)

    assert trial_events.report(folder, send=slow_send)
    write_pack(folder, "Trial_Content", (4, 1))
    assert trial_events.report(folder, send=slow_send)
    gate.set()
    assert wait_for(trial_events.idle)
    assert sent == ["setup_opened", "trial_installed"]


def test_the_setup_says_so_when_an_install_finished(folder, monkeypatch):
    """The setup's own moments go through its services: the end of an install
    and a content folder that was taken over."""
    monkeypatch.setattr(repository, "trial_rid", lambda: RID)
    monkeypatch.setattr(setup_state, "_start_poll", lambda: None)
    monkeypatch.setattr(setup_state, "_refresh_update_status", lambda: None)
    st = SetupState(services=FakeServices())
    st.folder = folder
    st.report_trial_events()  # the setup opened, before it was marked as shown
    assert wait_for(trial_events.idle) and st.services.events == []
    user_settings.mark_setup_shown()
    st.report_trial_events()
    assert wait_for(trial_events.idle) and st.services.events == [("setup_opened", RID)]
    write_pack(folder, "Trial_Content", (4, 1))
    st.phase, st.finalized = "done", False
    st.finish_on_main_thread()
    assert wait_for(trial_events.idle)
    assert st.services.events == [("setup_opened", RID), ("trial_installed", RID)]
    write_pack(folder, "Base_Humans", (4, 1))
    st.phase, st.finalized = "done", False
    st.finish_on_main_thread()
    assert wait_for(trial_events.idle)
    assert st.services.events[2:] == [("full_installed", RID)]
    assert Server.requests == []  # the fake services reach no server
    # An event the server refused is sent again at the next moment
    user_settings.update(**{trial_events.STORE_KEY: None})
    st.services.events, st.services.event_error = [], "unavailable"
    st.report_trial_events()
    assert wait_for(trial_events.idle) and st.services.events == []
    st.services.event_error = None
    st.report_trial_events()
    assert wait_for(trial_events.idle)
    assert st.services.events == [("setup_opened", RID), ("full_installed", RID)]
