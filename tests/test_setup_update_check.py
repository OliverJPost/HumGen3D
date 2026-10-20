"""The update check's verdict for the situations real users are in, against a
copy of the live catalogue: what the sidebar banner says, and that a pack
that is not installed is never "required"."""
import copy
import time

import pytest
from setup_fakes import LIVE_CATALOGUE, write_pack

from HumGen3D.backend.setup import update_check
from HumGen3D.backend.setup.catalogue import Catalogue

ADDON = (4, 0, 38)  # the catalogue's addon.latest, so no add-on notice


@pytest.fixture
def folder(tmp_path, monkeypatch):
    monkeypatch.setattr(update_check, "content_folder", lambda: str(tmp_path))
    monkeypatch.setattr(update_check, "addon_version", lambda: ADDON)
    monkeypatch.setattr(update_check, "status", update_check.UpdateStatus())
    return tmp_path


def check(catalogue_dict=None):
    return update_check.apply(Catalogue.from_dict(catalogue_dict or LIVE_CATALOGUE))


def buyer(folder, humans=(4, 1)):
    """The typical buyer: the three base packs and the poses."""
    write_pack(folder, "Base_Humans", humans, ["models/HG_HUMAN.blend"])
    write_pack(folder, "Base_Clothes", (4, 1), ["outfits/a.blend"])
    write_pack(folder, "Base_Hair", (4, 1), ["hair/a.blend"])
    write_pack(folder, "Base_Poses", (4, 0), ["poses/a.blend"])


def test_trial_install_is_silent(folder):
    """B2: a trial install plans in trial mode; the full library is locked, not missing."""
    write_pack(folder, "Trial_Content", (4, 1), ["models/HG_HUMAN.blend"])
    st = check()
    assert st.mode == "trial"
    assert st.required == [] and st.updates == []
    assert st.notice() == ""
    assert {s.key: s.status for s in st.statuses}["Base_Humans"] == "locked"
    assert st.content_state == "installed"


def test_old_trial_pack_gets_its_update(folder):
    write_pack(folder, "Trial_Content", (4, 0), ["models/HG_HUMAN.blend"])
    st = check()
    assert [s.key for s in st.required] == ["Trial_Content"]
    assert st.notice() == "required"


def test_typical_buyer_is_silent(folder):
    buyer(folder)
    st = check()
    assert st.mode == "licensed"
    assert st.required == [] and st.updates == [] and st.notice() == ""


def test_early_v4_buyer_needs_base_humans(folder):
    """Base Humans 4.0 is below REQUIRED: "required", which is a banner now, not a lock."""
    buyer(folder, humans=(4, 0))
    st = check()
    assert [s.key for s in st.required] == ["Base_Humans"]
    assert st.notice() == "required"


def test_missing_pack_is_never_required(folder):
    """A buyer who never installed Base Hair: offered, not required."""
    buyer(folder)
    (folder / "content_packs" / "Base_Hair.json").unlink()
    st = check()
    assert st.required == []
    assert [s.key for s in st.updates] == ["Base_Hair"]
    assert st.notice() == "available"


def test_newer_addon_needed(folder, monkeypatch):
    """An installed required pack below REQUIRED that only exists for a newer add-on."""
    buyer(folder, humans=(4, 0))
    data = copy.deepcopy(LIVE_CATALOGUE)
    data["packs"][0]["versions"][0]["min_addon"] = "9.0.0"
    st = check(data)
    assert [s.key for s in st.required] == ["Base_Humans"] and st.blocked_by_addon
    assert st.notice() == "addon"


def test_addon_update_notice(folder):
    buyer(folder)
    data = copy.deepcopy(LIVE_CATALOGUE)
    data["addon"]["latest"] = "4.1.0"
    assert check(data).notice() == "addon"


def test_server_can_silence_notices(folder):
    buyer(folder, humans=(4, 0))
    data = copy.deepcopy(LIVE_CATALOGUE)
    data["addon"]["notices"] = False
    st = check(data)
    assert st.required and st.notice() == ""
    assert not st.notices_enabled


def test_unknown_schema_shows_nothing(folder):
    buyer(folder, humans=(4, 0))
    data = copy.deepcopy(LIVE_CATALOGUE)
    data["schema"] = 99
    data["addon"]["message"] = "From the future"
    st = check(data)
    assert st.notice() == "" and st.message == ""


def test_server_message(folder):
    buyer(folder)
    data = copy.deepcopy(LIVE_CATALOGUE)
    data["addon"]["message"] = "Downloads are slow today."
    data["addon"]["message_url"] = "https://humgen3d.com/status"
    st = check(data)
    assert st.message == "Downloads are slow today." and st.message_url == "https://humgen3d.com/status"
    assert st.notice() == ""
    data["addon"].pop("message")
    assert check(data).message_url == ""


def test_content_state_follows_the_folder(folder, monkeypatch):
    assert check().content_state == "empty"
    monkeypatch.setattr(update_check, "content_folder", lambda: "")
    assert check().content_state == "unset"
    monkeypatch.setattr(update_check, "content_folder", lambda: str(folder / "gone"))
    assert check().content_state == "unreachable"


def test_no_catalogue_no_notice(folder, monkeypatch):
    buyer(folder, humans=(4, 0))
    monkeypatch.setattr(update_check, "cached_catalogue", lambda: None)
    st = update_check.apply()
    assert st.statuses == [] and st.notice() == "" and st.content_state == "installed"


def test_due(monkeypatch):
    st = update_check.UpdateStatus()
    monkeypatch.setattr(update_check, "status", st)
    now = time.time()
    assert update_check.due()  # never checked
    st.checked_at = now - 60
    assert not update_check.due()
    st.checked_at = now - update_check.CHECK_INTERVAL - 1
    assert update_check.due()
    # A clock that was ahead left a check in the future: due at once
    st.checked_at = now + 30 * 24 * 3600
    assert update_check.due()
    st.checked_at = now + 60  # small skew is fine
    assert not update_check.due()
    # A failed check backs off for an hour
    st.checked_at = 0.0
    st.failed_at = now - 60
    assert not update_check.due()
    st.failed_at = now - update_check.FAILURE_BACKOFF - 1
    assert update_check.due()


def test_stop_removes_timers_and_abandons_a_running_check(monkeypatch):
    import bpy

    st = update_check.UpdateStatus()
    monkeypatch.setattr(update_check, "status", st)
    bpy.app.timers.register(update_check._scheduled_check, first_interval=3600)
    bpy.app.timers.register(update_check._drain, first_interval=3600)
    st.checking = True
    old = update_check._generation
    update_check.stop()
    assert not bpy.app.timers.is_registered(update_check._scheduled_check)
    assert not bpy.app.timers.is_registered(update_check._drain)
    assert not st.checking and update_check._generation == old + 1
    # A result from the abandoned thread arrives later: ignored
    applied = []
    monkeypatch.setattr(update_check, "apply", lambda *a: applied.append(a))
    update_check._results.put((old, "ok", None, "{}", None))
    assert update_check._drain() is None
    assert applied == [] and st.checked_at == 0.0
    update_check.stop()  # nothing registered: fine


def test_newer_addon_message():
    from HumGen3D.backend.setup import api_client

    assert api_client.pack_error_message("needs_newer_addon") == "A newer Human Generator is needed for this content."
