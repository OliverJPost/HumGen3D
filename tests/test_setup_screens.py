"""Every step of the setup lays itself out, in the overlay and in the sidebar
panel, for the states a user can be in. The overlay draws on a stand-in
canvas that records its text (there is no GPU in a test run), the panel into
a stand-in layout; a click is a press on what was drawn."""
import json
import os
import time
from types import SimpleNamespace

import bpy
import pytest

from HumGen3D.backend.setup import online, update_check, user_settings
from HumGen3D.backend.setup.catalogue import Catalogue
from HumGen3D.user_interface.setup_overlay import operator, screens
from HumGen3D.user_interface.setup_overlay import state as setup_state
from HumGen3D.user_interface.setup_overlay.draw import Palette
from HumGen3D.user_interface.setup_overlay.state import FAKE_CATALOGUE, FakeServices, SetupState

FULL_FILES = ["/dl/Base_Humans_4_1.hgpack", "/dl/Base_Clothes_4_1.hgpack", "/dl/Base_Hair_4_1.hgpack"]
# Words of the activation that this build must not show anywhere
GONE = ("license", "licence", "activate", "order guid", "superhive")


class FakeCanvas:
    """The Canvas calls the screens make, with text six pixels a character."""

    def __init__(self):
        self.scale = 1.0
        self.alpha = 1.0
        self.palette = Palette()
        self.width, self.height = 1600, 1000
        self.texts = []

    def px(self, value):
        return value * self.scale

    def text_width(self, text, size, bold=False):
        return len(text) * size * 0.5

    def text(self, text, x, y, size, color, align="LEFT", bold=False):
        assert len(color) == 4
        self.texts.append(text)
        return self.text_width(text, size, bold)

    def ellipsize(self, text, size, max_width, bold=False):
        return text

    def wrap(self, text, size, max_width, bold=False):
        return [text]

    def paragraph(self, text, x, top, size, color, max_width, leading=1.45, align="LEFT", bold=False):
        self.text(text, x, top, size, color, align, bold)
        return self.px(size) * leading

    def rect(self, *args, **kwargs):
        pass

    shadow = outline = hline = image = clip = unclip = rect


class Recorder(screens.Controller):
    def __init__(self):
        self.calls = []

    def go(self, screen):
        setup_state.state.screen = screen
        self.calls.append(("go", screen))

    def open_url(self, url):
        self.calls.append(("url", url))

    def select_files(self):
        self.calls.append(("select_files",))

    def close(self):
        self.calls.append(("close",))


class FakeLayout:
    """Takes every UILayout call; records the labels and operators drawn."""

    def __init__(self, log=None):
        self.log = log if log is not None else []

    def __getattr__(self, name):
        def call(*args, **kwargs):
            if name in ("label", "progress"):
                self.log.append(("label", kwargs.get("text", "")))
            elif name == "operator":
                self.log.append(("operator", args[0] if args else kwargs.get("operator"), kwargs.get("text", "")))
            return FakeLayout(self.log)

        return call

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)


@pytest.fixture(scope="module", autouse=True)
def addon():
    if not bpy.context.preferences.addons.get("HumGen3D"):
        bpy.ops.preferences.addon_enable(module="HumGen3D")


@pytest.fixture
def st(monkeypatch, tmp_path):
    monkeypatch.setattr(setup_state, "FAKE_DURATION", 0.1)
    monkeypatch.setattr(setup_state, "FAKE_INSTALL_SECONDS", 0.01)
    monkeypatch.setattr(setup_state, "FAKE_CHECK_SECONDS", 0.02)
    monkeypatch.setattr(setup_state, "_start_poll", lambda: None)
    monkeypatch.setattr(setup_state, "RETRY_DELAYS", (0.0, 0.0, 0.0))
    monkeypatch.setenv(user_settings.ENV_OVERRIDE, str(tmp_path / "settings.json"))
    monkeypatch.setattr(setup_state.repository, "trial_rid", lambda: None)
    monkeypatch.setattr(setup_state.migration, "find_existing_content", lambda: None)
    monkeypatch.setattr(online, "allowed", lambda: True)
    monkeypatch.setattr(update_check.status, "catalogue", Catalogue.from_dict(FAKE_CATALOGUE))
    state = SetupState(services=FakeServices())
    state.folder = str(tmp_path / "content")
    monkeypatch.setattr(setup_state, "state", state)
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


def write_installed(folder, key, version):
    packs = os.path.join(str(folder), "content_packs")
    os.makedirs(packs, exist_ok=True)
    with open(os.path.join(packs, f"{key}.json"), "w") as f:
        json.dump({"config": {"pack_name": key.replace("_", " "), "pack_version": list(version)}}, f)


def show(st, controller=None):
    """Lay out the screen of the current step. Returns it and the text it drew."""
    controller = controller or Recorder()
    textures = SimpleNamespace(get=lambda path: None)
    screen = screens.SCREENS[st.screen](controller, textures)
    canvas = FakeCanvas()
    screen.draw(canvas, (390, 210, 820, 580))
    labels = [button.label for button in screen.buttons]
    return screen, canvas.texts + labels


def press(screen, label):
    button = next(b for b in screen.buttons if b.label == label)
    assert button.enabled, label
    button.on_click()


# A sidebar's context: in a test run Blender has no region and no interface scale
CONTEXT = SimpleNamespace(region=None, preferences=SimpleNamespace(system=SimpleNamespace(ui_scale=1.0)))


def panel_texts(st):
    """What the sidebar's own version of the current step draws."""
    layout = FakeLayout()
    panel = SimpleNamespace(layout=layout, draw_pack_row=operator.HG_PT_SETUP.draw_pack_row, draw_online_notice=lambda layout, st: None)
    getattr(operator.HG_PT_SETUP, "draw_" + st.screen)(panel, layout, CONTEXT, st)
    return [entry[-1] for entry in layout.log], [entry[1] for entry in layout.log if entry[0] == "operator"]


def no_activation(texts):
    joined = " ".join(texts).lower()
    return not any(word in joined for word in GONE)


def test_welcome_without_a_trial_id_offers_the_content_packs_alone(st):
    """The trial is offered only to an install from the trial page. Every
    other install gets one button, which opens the file list."""
    st.begin_setup()
    assert not st.rid
    screen, texts = show(st)
    assert "Install the content packs" in texts and no_activation(texts)
    assert not {"Install the free trial", "I bought it", "Get started", "Free trial"} & set(texts)
    assert "I already have the content installed" in texts
    # The sidebar's own welcome says the same
    panel, ops = panel_texts(st)
    assert "Install the content packs" in panel and "Install the free trial" not in panel
    assert "I already have the content installed" in panel and "hg3d.setup_go" not in ops
    press(screen, "Install the content packs")
    assert st.screen == "files" and st.mode == "full"
    texts, ops = panel_texts(st)
    assert "Install the full version" in texts and "hg3d.setup_select_files" in ops
    st.back()
    assert st.screen == "welcome"
    # There is no step that asks trial or full version
    assert "choose" not in screens.SCREENS and "choose" not in setup_state.SCREENS
    assert not hasattr(operator.HG_PT_SETUP, "draw_choose")


def test_welcome_from_a_trial_link_offers_both(st):
    user_settings.update(trial_rid="0123456789abcdef")
    st.begin_setup()
    screen, texts = show(st)
    assert "Install the free trial" in texts and "I bought it" in texts and "Install the content packs" not in texts
    press(screen, "I bought it")
    assert st.screen == "files"
    st.back()
    assert st.screen == "welcome"
    screen, _ = show(st)
    press(screen, "Install the free trial")
    assert st.screen == "packs" and st.mode == "trial"
    texts, ops = panel_texts(st)
    assert "Install the free trial" in texts


TRIAL_NOTICE = "This trial tells humgen3d.com when it is installed and when the full version replaces it."


def test_trial_screen_says_what_the_request_form_said(st, monkeypatch):
    """In the EU, the EEA and the UK the request form says that the trial lets
    us know when it is installed and upgraded; the zip then carries
    `notice: strict` and the trial screen says the same, in the window and in
    the sidebar. With `notice: none` it keeps its usual line, and it says it
    when the zip does not say which."""
    user_settings.update(trial_rid="0123456789abcdef")
    for notice, shown in (("strict", True), ("none", False), (None, True)):
        monkeypatch.setattr(setup_state.repository, "trial_notice", lambda notice=notice: notice)
        user_settings.update(trial_notice=None)
        st.begin_setup()
        st.choose("trial")
        loaded(st)
        _, texts = show(st)
        assert any(TRIAL_NOTICE in t for t in texts) == shown, notice
        assert any("Privacy policy" in t for t in texts)
        assert any("The download and a daily update check go to humgen3d.com." in t for t in texts)
        labels, _ = panel_texts(st)
        assert (TRIAL_NOTICE in " ".join(labels)) == shown, notice


def test_trial_list_and_its_download(st):
    st.choose("trial")
    loaded(st)
    screen, texts = show(st)
    assert "Install the free trial" in texts and "Trial Content" in texts
    assert "In the full version: 6 more packs" in texts and no_activation(texts)
    # What the download sends is said where it starts
    assert any("Privacy policy" in t for t in texts) and any("humgen3d.com" in t for t in texts)
    # An add-on that did not come from an install guide has nothing more to say
    assert not any(TRIAL_NOTICE in t for t in texts)
    press(screen, "Install")
    assert st.screen == "slides" and st.phase == "downloading"
    _, texts = show(st)
    assert any(t.startswith("Downloading Trial Content") for t in texts)
    assert wait_for(lambda: st.phase == "done")
    st.screen = "done"
    _, texts = show(st)
    assert "Human Generator is ready" in texts and no_activation(texts)
    assert "Get started" in texts and "Create your first human" not in texts


def test_the_tutorial_pages_show_while_the_content_installs(st):
    """No slideshow: the pages of the Get started tutorial, turned by hand."""
    st.choose("trial")
    loaded(st)
    st.start()
    assert st.screen == "slides"
    asked = []
    textures = SimpleNamespace(get=lambda path: asked.append(path))
    screen = screens.SCREENS["slides"](Recorder(), textures)
    canvas = FakeCanvas()
    screen.draw(canvas, (390, 210, 820, 580))
    pages = [os.path.join(screens.TUTORIAL_IMAGE_DIR, name) for name in screens.TUTORIAL_PAGES]
    assert len(pages) == 6 and all(os.path.isfile(page) for page in pages)
    assert pages[0] in asked
    # The progress is still there, and the pages don't turn by themselves
    assert any(t.startswith("Downloading Trial Content") for t in canvas.texts)
    screen.tick(time.monotonic() + 3600)
    assert screen.index == 0
    press(screen, "›")
    assert screen.index == 1
    asked.clear()
    screen.draw(FakeCanvas(), (390, 210, 820, 580))
    assert pages[1] in asked
    press(screen, "‹")
    press(screen, "‹")
    assert screen.index == 5
    assert not hasattr(screens, "DECKS")
    assert wait_for(lambda: st.phase == "done")


def test_installed_trial_offers_to_buy_or_install(st, tmp_path):
    write_installed(tmp_path / "content", "Trial_Content", (4, 1))
    st.begin_setup()
    loaded(st)
    controller = Recorder()
    screen, texts = show(st, controller)
    assert "The trial is installed" in texts and "Buy full version" in texts and "I bought it" in texts
    press(screen, "Buy full version")
    assert controller.calls[-1][0] == "url" and "humgen3d.com/pricing" in controller.calls[-1][1]
    press(screen, "I bought it")
    assert st.screen == "files" and st.upgrading_trial
    _, texts = show(st)
    assert "Install the full version" in texts and any("replace the trial content" in t for t in texts)
    texts, ops = panel_texts(st)
    assert "hg3d.setup_select_files" in ops and "hg3d.setup_back" in ops


def test_empty_file_list_asks_for_the_files(st):
    st.choose("full")
    controller = Recorder()
    screen, texts = show(st, controller)
    assert "Select .hgpack files…" in texts and "Where are my files?" in texts and "No files to install yet" in texts
    assert no_activation(texts)
    install = next(b for b in screen.buttons if b.label == "Install")
    assert not install.enabled
    press(screen, "Select .hgpack files…")
    assert controller.calls[-1] == ("select_files",)
    press(screen, "Where are my files?")
    assert controller.calls[-1][0] == "url" and controller.calls[-1][1].endswith("/guide/installation#install-the-full-version")


def test_file_list_rows_and_install(st, tmp_path):
    write_installed(tmp_path / "content", "Base_Hair", (4, 1))
    write_installed(tmp_path / "content", "Base_Poses", (4, 1))
    st.begin_add_packs()
    st.add_files(FULL_FILES + ["/dl/Base_Poses_4_0.hgpack", "/dl/Base_Humans_4_0.hgpack", "/dl/holiday.zip"])
    screen, texts = show(st)
    assert "Add content packs" in texts
    assert {"Base Humans", "Base Clothes", "Base Hair", "Base Poses", "holiday.zip"} <= set(texts)
    assert "Version 4.1 · Base_Clothes_4_1.hgpack" in texts
    assert "Installed" in texts and "Older than installed" in texts and "Not a content pack" in texts
    assert "Version 4.0, installed is 4.1" in texts and "Human Generator packs are .hgpack files" in texts
    # The list is longer than its box here: adding files stays in reach above it
    assert "Select more files…" in texts and "Where are my files?" in texts and no_activation(texts)
    texts, ops = panel_texts(st)
    assert ops.count("hg3d.setup_toggle_pack") == 2 and "hg3d.setup_clear_files" in ops and "Not a content pack" in texts
    press(screen, "Install")
    assert st.screen == "slides" and st.phase == "installing"
    _, texts = show(st)
    assert any(t.startswith("Installing Base ") for t in texts)
    assert wait_for(lambda: st.phase == "done")
    st.screen = "done"
    _, texts = show(st)
    assert "Human Generator is ready" in texts


def test_file_list_remarks(st, tmp_path):
    st.choose("full")
    st.add_files(FULL_FILES[1:])
    _, texts = show(st)
    assert "Base Humans isn't among these files. Humans can't be made without it." in texts
    st.clear_files()
    st.add_files(["/dl/Base_Humans_4_0.hgpack"])
    _, texts = show(st)
    assert "Version 4.0. This add-on needs 4.1 or newer" in texts
    assert any(t.startswith("Base Humans is an older file than this add-on needs.") for t in texts)
    texts, _ = panel_texts(st)
    assert "Base Humans is an older file" in " ".join(texts)


def test_update_of_an_owner_names_the_files_to_get(st, tmp_path):
    for key in ("Base_Humans", "Base_Clothes", "Base_Hair"):
        write_installed(tmp_path / "content", key, (4, 0) if key != "Base_Hair" else (4, 1))
    st.begin_update()
    _, texts = show(st)
    assert "Update your content packs" in texts
    assert any("Base Humans 4.1, Base Clothes 4.1" in t for t in texts)
    st.begin_update(keys=["HG_Export"])
    _, texts = show(st)
    assert "Install HG Export 1.0" in texts and any(".hgpack" in t for t in texts)


def test_failed_file_install_says_so_without_download_words(st):
    st.choose("full")
    st.add_files(FULL_FILES[:1])
    st.services.install_error = "not_a_pack"
    st.start()
    assert wait_for(lambda: st.phase == "failed")
    _, texts = show(st)  # the progress step
    assert "Install failed" in texts and "Download failed" not in texts
    st.screen = "done"
    screen, texts = show(st)
    assert "Install failed" in texts and "Retry" in texts and "Contact support" in texts
    assert any("Your files are not changed" in t for t in texts) and not any("download resumes" in t for t in texts)
    layout = FakeLayout()
    operator.HG_PT_SETUP.draw_finished(SimpleNamespace(), layout, CONTEXT, st)
    assert ("label", "Install failed") in layout.log


def test_failed_download_keeps_its_words(st):
    st.choose("trial")
    loaded(st)
    st.fail()
    st.start()
    assert wait_for(lambda: st.phase == "failed")
    st.screen = "done"
    _, texts = show(st)
    assert "Download failed" in texts and any("download resumes" in t for t in texts)


def test_setup_panel_is_gone_once_content_is_installed(st, tmp_path, monkeypatch):
    """The sidebar's Setup panel is there while something is to be set up and
    leaves when the content is installed, also for a trial, whose buy buttons
    are at the top of the main panel."""
    poll = lambda: operator.HG_PT_SETUP.poll(None)  # noqa: E731
    installed = {"packs": {}}
    monkeypatch.setattr(operator, "_installed", lambda: installed["packs"])
    # On the class: a patch on the instance would stay behind as an attribute
    monkeypatch.setattr(type(update_check.status), "notice", lambda self: "")
    assert poll()  # nothing installed yet
    write_installed(tmp_path / "content", "Trial_Content", (4, 1))
    installed["packs"] = operator.installed_packs(str(tmp_path / "content"))
    assert operator.content_installed() and not poll()
    assert not hasattr(operator.HG_PT_SETUP, "draw_trial_card")
    # A setup that was started, or runs, or ended and is still on screen, shows it
    st.prompted = True
    assert poll()
    st.prompted = False
    st.phase = "done"
    assert poll()
    # An update notice shows it too
    st.phase = "idle"
    monkeypatch.setattr(type(update_check.status), "notice", lambda self: "available")
    assert poll()


def test_closing_the_window_on_a_finished_install_ends_the_setup(st, monkeypatch):
    """Get started, the cross or Escape on the finished setup: the card in the
    sidebar does not stay behind waiting for its own Done."""
    monkeypatch.setattr(setup_state, "redraw_viewports", lambda: None)
    finished = []
    monkeypatch.setattr(st.services, "finish", lambda folder: finished.append(folder))
    monkeypatch.setattr(setup_state, "_refresh_update_status", lambda: None)
    window = SimpleNamespace(_hook=None, _textures=SimpleNamespace(release=lambda: None))
    close = lambda: operator.HG_OT_setup_overlay._finish(window, None)  # noqa: E731
    # Closed while it runs: the setup goes on
    st.begin_setup()
    st.phase = "downloading"
    close()
    assert st.phase == "downloading" and st.prompted
    # Closed when it is done: over, and the folder was handed to the add-on
    st.phase, st.screen, st.finalized = "done", "done", False
    close()
    assert st.phase == "idle" and not st.prompted and st.screen == "welcome"
    assert finished == [st.folder]
