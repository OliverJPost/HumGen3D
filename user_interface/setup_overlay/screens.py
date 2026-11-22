# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The screens of the setup overlay and the widgets they are made of.

A screen lays itself out in the card rectangle on every draw (the region size
and interface scale can change), draws, and answers mouse and keyboard events
through the widgets it placed. Screens talk to the operator through
`Controller`. Which screen shows is `state.screen`, so the sidebar fallback and
the overlay always show the same step.

Every step uses the same card: a header with the logo, the step's content and
a footer with its buttons, so moving through the setup never resizes or
rearranges the window. The welcome and slide screens split the card into a
picture and a text column instead.

Two steps are lists: `PacksScreen` shows the trial's packs, which are
downloaded, and `FilesScreen` the `.hgpack` files the user picked for the
full version.
"""
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import bpy

from ...common.documentation import docs_url
from ...common.i18n import tr
from . import state as setup_state
from .draw import Canvas, Color, TextureCache, ease_out, lerp
from .state import SUPPORT_EMAIL, error_text, format_bytes

Rect = Tuple[float, float, float, float]

# Pictures of the welcome screen ship with the add-on
SETUP_IMAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
LOGO = os.path.join(SETUP_IMAGE_DIR, "hg_logo.png")

# What shows while the content installs: the pages of the "Get started"
# tutorial the add-on has always had (1200 x 600, the words are in the picture)
TUTORIAL_IMAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "documentation", "tutorial_operator", "images", "get_started_tutorial"
)
TUTORIAL_PAGES = tuple(f"quick_start_{index:02d}.png" for index in range(6))
TUTORIAL_ASPECT = 2.0

FADE_SECONDS = 0.35
CLOSE_GLYPH = "✕"
CHECK_GLYPH = "✓"

# Layout, in design units
CARD_W, CARD_H = 820, 580
CARD_RADIUS = 12
PAD = 32  # left and right margin of the content
HEADER = 64
FOOTER = 76
CONTROL_H = 36  # buttons and fields
RADIUS = 8  # buttons, fields and lists

# Type scale, in design units
TITLE = 20
BODY = 13
SMALL = 12


def pack_count(count: int, size: str) -> str:
    if count == 1:
        return tr("1 pack, {size}").format(size=size)
    return tr("{count} packs, {size}").format(count=count, size=size)


def update_label(count: int) -> str:
    if count == 1:
        return tr("Update 1 pack")
    return tr("Update {count} packs").format(count=count)


def time_left(seconds: float) -> str:
    if seconds < 60:
        return tr("under a minute left")
    minutes = int(math.ceil(seconds / 60))
    if minutes < 60:
        return tr("{minutes} min left").format(minutes=minutes)
    return tr("{hours} h {minutes} min left").format(hours=minutes // 60, minutes=minutes % 60)


def download_detail(st) -> str:
    """The line under the progress bar: bytes, speed and time left, or the retry."""
    if st.retry_at:
        seconds = max(0, int(math.ceil(st.retry_at - time.monotonic())))
        return tr("Connection lost. Trying again in {seconds} s ({attempt} of {count})").format(seconds=seconds, attempt=st.retry_attempt, count=len(setup_state.RETRY_DELAYS))
    parts = [tr("{done} of {total}").format(done=format_bytes(st.done_bytes), total=format_bytes(st.total_bytes))]
    if st.phase == "downloading" and st.speed > 0:
        parts.append(tr("{speed}/s").format(speed=format_bytes(st.speed)))
        left = st.seconds_left
        if left is not None:
            parts.append(time_left(left))
    return " · ".join(parts)


def download_label(st, count: bool = True) -> str:
    pack = st.current
    name = tr(pack.name) if pack else ""
    total = len(st.selected)
    template = tr("Installing {pack}") if st.phase == "installing" else tr("Downloading {pack}")
    label = template.format(pack=name)
    if count and total > 1:
        label = tr("{label} ({index} of {count})").format(label=label, index=min(st.packs_done + 1, total), count=total)
    return label


def failure_title(st) -> str:
    """Nothing was downloaded when the packs came from files."""
    return tr("Install failed") if st.local else tr("Download failed")


def space_text(st) -> Tuple[str, bool]:
    """The disk line of the pack footer, and whether it is a problem."""
    needed, free = st.space()
    if free is None:
        return tr("Couldn't check the free space on this disk"), False
    if free >= needed:
        return tr("{free} free on this disk").format(free=format_bytes(free)), False
    return tr("Not enough space: {needed} needed, {free} free").format(needed=format_bytes(needed), free=format_bytes(free)), True


def packs_copy(st) -> Tuple[str, str]:
    """Title and subtitle of the trial's pack list."""
    if st.update_mode:
        return tr("Update the trial content"), tr("A newer version of the trial content is available. Your own content stays as it is.")
    if st.trial_installed_here:
        return tr("The trial is installed"), tr("Buy the full version for the whole library. Already bought it? Install it from the files of your purchase.")
    return tr("Install the free trial"), tr("One human, an outfit, a hairstyle and four poses. The rest of the library comes with the full version.")


def files_copy(st) -> Tuple[str, str]:
    """Title and subtitle of the file list, by why it shows."""
    if st.wanted:
        names = ", ".join(tr(name) for name in st.wanted)
        if st.update_mode and len(st.wanted) > 1:
            return tr("Update your content packs"), tr("Newer files are with your purchase: {names}. Download them, then select them here.").format(names=names)
        return tr("Install {names}").format(names=names), tr("This pack comes with your purchase. Download its .hgpack file, then select it here.")
    if st.add_packs or st.update_mode:
        return tr("Add content packs"), tr("Select the .hgpack files to add. Installed packs stay as they are.")
    if st.upgrading_trial:
        return tr("Install the full version"), tr("Download the content packs of your purchase, then select the .hgpack files here. They replace the trial content.")
    return tr("Install the full version"), tr("Download the content packs of your purchase, then select the .hgpack files here.")


def file_detail(pack) -> str:
    """The second line of a row of the file list."""
    version = tr("Version {version}").format(version=pack.version) if pack.version else ""
    if pack.status == "not_a_pack":
        return tr("Human Generator packs are .hgpack files")
    if pack.status == "not_needed":
        return tr("The full library replaces the trial content")
    if pack.status == "older" and pack.installed_version:
        return tr("Version {version}, installed is {installed}").format(version=pack.version, installed=".".join(str(n) for n in pack.installed_version))
    if pack.status == "update_available" and pack.installed_version:
        return tr("Installed {old}, update to {new}").format(old=".".join(str(n) for n in pack.installed_version), new=pack.version)
    if pack.needs_version:
        return tr("Version {version}. This add-on needs {needed} or newer").format(version=pack.version, needed=pack.needs_version)
    return " · ".join(part for part in (version, pack.file) if part)


def files_notice(st) -> str:
    """The one notice the file list shows above the footer."""
    if st.drive_missing:
        return tr("That drive isn't connected. Connect it, or choose another folder.")
    if st.lock_blocked:
        return tr("Another Blender window is installing content.")
    if st.base_missing:
        if st.upgrading_trial:
            return tr("Base Humans isn't among these files. The trial content stays until it is installed.")
        return tr("Base Humans isn't among these files. Humans can't be made without it.")
    outdated = [p for p in st.selected if p.needs_version]
    if outdated:
        return tr("{pack} is an older file than this add-on needs. Download the current one from your purchase.").format(pack=tr(outdated[0].name))
    return ""


def paused_text() -> str:
    return tr("Downloads are paused right now. Try again later.")


def notice_text(st) -> Tuple[str, str]:
    """The one notice the pack list shows above the footer, and its link."""
    if st.downloads_paused:
        cat = st.catalogue
        if cat is not None and not cat.supported:
            return tr("A newer Human Generator is needed for the latest content."), ""
        return (tr(st.server_message) if st.server_message else paused_text()), (cat.message_url if cat is not None else "")
    if st.drive_missing:
        return tr("That drive isn't connected. Connect it, or choose another folder."), ""
    if st.lock_blocked:
        return tr("Another Blender window is downloading the content."), ""
    if st.addon_too_old:
        return tr("A newer Human Generator is needed for the latest content."), ""
    if st.server_message:
        return tr(st.server_message), st.catalogue.message_url
    return "", ""


def can_open_sidebar_tab() -> bool:
    """Blender versions where the sidebar tab can be switched from Python."""
    try:
        return not bpy.types.Region.bl_rna.properties["active_panel_category"].is_readonly
    except (KeyError, AttributeError):
        return False


def in_rect(rect: Rect, x: float, y: float) -> bool:
    rx, ry, rw, rh = rect
    return rx <= x <= rx + rw and ry <= y <= ry + rh


def centered_baseline(c: Canvas, y: float, h: float, size: float) -> float:
    """Baseline that centres a line of `size` text vertically in y..y+h."""
    return y + h / 2 - c.px(size) * 0.36


@dataclass
class Button:
    label: str
    rect: Rect
    on_click: Callable[[], None]
    kind: str = "secondary"  # primary, secondary, ghost, link
    enabled: bool = True
    hover: bool = False
    size: float = BODY

    def hit(self, x: float, y: float) -> bool:
        return in_rect(self.rect, x, y)

    def draw(self, c: Canvas) -> None:
        p = c.palette
        x, y, w, h = self.rect
        radius = c.px(RADIUS)
        hover = self.hover and self.enabled
        alpha = c.alpha
        if not self.enabled:
            c.alpha = alpha * 0.45
        bold = self.kind in ("primary", "secondary")
        if self.kind == "primary":
            c.rect(x, y, w, h, p.accent_hover if hover else p.accent, radius)
            text = p.on_accent
        elif self.kind == "secondary":
            c.outline(x, y, w, h, p.border, radius, max(1.0, round(c.scale)), p.hover if hover else p.card)
            text = p.text
        elif self.kind == "link":
            text = p.text if hover else p.link
        else:  # ghost
            if hover:
                c.rect(x, y, w, h, p.hover, radius)
            text = p.text if hover else p.muted
        c.text(self.label, x + w / 2, centered_baseline(c, y, h, self.size), self.size, text, "CENTER", bold=bold)
        c.alpha = alpha


class Controller:
    """What a screen may ask of the operator."""

    def go(self, screen: str) -> None: ...
    def close(self) -> None: ...
    def change_folder(self) -> None: ...
    def create_human(self) -> None: ...
    def open_url(self, url: str) -> None: ...
    def use_folder(self, folder: str) -> None: ...
    def select_existing_folder(self) -> None: ...
    def select_files(self) -> None: ...
    def contact_support(self) -> None: ...
    def to_sidebar(self) -> None: ...


class Screen:
    name = "screen"

    def __init__(self, controller: Controller, textures: TextureCache) -> None:
        self.controller = controller
        self.textures = textures
        self.buttons: List[Button] = []
        self.rows: List[Tuple[Rect, Callable[[], None]]] = []
        self.rect: Rect = (0, 0, 0, 0)
        self.mouse: Tuple[float, float] = (-1.0, -1.0)

    def card_size(self, c: Canvas) -> Tuple[float, float]:
        return c.px(CARD_W), c.px(CARD_H)

    def enter(self) -> None:
        """The screen was just switched to."""

    def draw(self, c: Canvas, rect: Rect) -> None:
        self.rect = rect
        self.buttons = []
        self.rows = []
        self.layout(c)
        for button in self.buttons:
            button.hover = button.enabled and button.hit(*self.mouse)
            button.draw(c)

    def layout(self, c: Canvas) -> None:  # draws and places widgets
        raise NotImplementedError

    # Input. Coordinates are region pixels.

    def hover(self, x: float, y: float) -> bool:
        """True when something under the mouse changed and a redraw is due."""
        before = self._hover_state()
        self.mouse = (x, y)
        return before != self._hover_state()

    def _hover_state(self) -> tuple:
        x, y = self.mouse
        return tuple(b.enabled and b.hit(x, y) for b in self.buttons) + tuple(in_rect(r, x, y) for r, _ in self.rows)

    def press(self, x: float, y: float) -> bool:
        for button in self.buttons:
            if button.enabled and button.hit(x, y):
                button.on_click()
                return True
        for rect, action in self.rows:
            if in_rect(rect, x, y):
                action()
                return True
        return False

    def drag(self, x: float, y: float) -> bool:
        return False

    def release(self, x: float, y: float) -> None:
        pass

    def key(self, event) -> bool:
        return False

    def scroll(self, pixels: float) -> bool:
        return False

    def tick(self, now: float) -> None:
        pass

    # Card structure

    def chrome(self, c: Canvas) -> Rect:
        """Header with logo and close button, dividers above the footer.
        Returns the content rectangle between them, without the side margins."""
        p = c.palette
        x, y, w, h = self.rect
        header_y = y + h - c.px(HEADER)
        self.brand(c, x + c.px(PAD), header_y, c.px(HEADER))
        self.close_button(c, header_y, c.px(HEADER))
        c.hline(x, header_y, w, p.line)
        c.hline(x, y + c.px(FOOTER), w, p.line)
        return (x + c.px(PAD), y + c.px(FOOTER), w - 2 * c.px(PAD), header_y - y - c.px(FOOTER))

    def brand(self, c: Canvas, x: float, y: float, h: float) -> None:
        """The logo and the product name, centred vertically in y..y+h."""
        size = c.px(24)
        logo_y = round(y + (h - size) / 2)
        self.logo(c, x, logo_y, size)
        c.text("Human Generator", x + size + c.px(10), centered_baseline(c, logo_y, size, BODY), BODY, c.palette.text, bold=True)

    def logo(self, c: Canvas, x: float, y: float, size: float) -> None:
        texture = self.textures.get(LOGO)
        if texture:
            c.image(texture, round(x), round(y), size, size, size * 0.18)
        else:
            c.rect(x, y, size, size, c.palette.accent, size * 0.18)

    def close_button(self, c: Canvas, y: float, h: float) -> None:
        x, _, w, _ = self.rect
        size = c.px(30)
        self.button(CLOSE_GLYPH, x + w - c.px(PAD) + c.px(8) - size, y + (h - size) / 2, size, size, self.controller.close, "ghost", size=SMALL)

    def title_block(self, c: Canvas, content: Rect, title: str, subtitle: str) -> float:
        """Title and one sentence under it, at the top of the content. Returns
        the y below them where the next element can start."""
        x, y, w, h = content
        top = y + h - c.px(28)
        used = c.paragraph(title, x, top, TITLE, c.palette.text, w, leading=1.25, bold=True)
        top -= used + c.px(10)
        if subtitle:
            used = c.paragraph(subtitle, x, top, BODY, c.palette.muted, w * 0.85, leading=1.45)
            top -= used
        return top - c.px(24)

    def footer_actions(self, c: Canvas, actions: List[Tuple[str, Callable[[], None], str, bool]]) -> float:
        """Buttons right-aligned in the footer, (label, action, kind, enabled)
        from left to right. Returns the x where the leftmost one starts."""
        x, y, w, h = self.rect
        right = x + w - c.px(PAD)
        button_y = y + (c.px(FOOTER) - c.px(CONTROL_H)) / 2
        for label, action, kind, enabled in reversed(actions):
            bw = self.button_width(c, label, kind)
            right -= bw
            self.button(label, right, button_y, bw, c.px(CONTROL_H), action, kind, enabled)
            right -= c.px(8)
        return right

    def back_or_close(self) -> Tuple[str, Callable[[], None], str, bool]:
        """The leftmost footer button: Back within the run, Close where it started."""
        st = setup_state.state
        if st.can_go_back:
            return (tr("Back"), self._back, "ghost", not st.busy)
        return (tr("Close"), self.controller.close, "ghost", True)

    def _back(self) -> None:
        setup_state.state.back()
        self.controller.go(setup_state.state.screen)

    @staticmethod
    def button_width(c: Canvas, label: str, kind: str) -> float:
        if kind == "ghost":
            return c.text_width(label, BODY) + c.px(28)
        return max(c.text_width(label, BODY, bold=True) + c.px(40), c.px(96))

    # Widgets

    def button(self, label: str, x: float, y: float, w: float, h: float, on_click: Callable[[], None], kind: str = "secondary", enabled: bool = True, size: float = BODY) -> Button:
        button = Button(label, (round(x), round(y), round(w), round(h)), on_click, kind, enabled, size=size)
        self.buttons.append(button)
        return button

    def link(self, c: Canvas, label: str, x: float, y: float, size: float, on_click: Callable[[], None], align: str = "LEFT") -> float:
        """A text link with its baseline at y. Returns its width."""
        width = c.text_width(label, size)
        if align == "RIGHT":
            x -= width
        self.buttons.append(Button(label, (x, y - c.px(5), width, c.px(size) + c.px(8)), on_click, "link", size=size))
        return width

    def draw_progress_bar(self, c: Canvas, x: float, y: float, w: float, fraction: float, color: Optional[Color] = None) -> None:
        h = c.px(4)
        c.rect(x, y, w, h, c.palette.line, h / 2)
        if fraction > 0:
            c.rect(x, y, max(w * fraction, h), h, color or c.palette.accent, h / 2)

    def checkbox(self, c: Canvas, x: float, y: float, checked: bool, on_toggle: Callable[[], None], enabled: bool = True, soft: bool = False) -> float:
        """A 16-unit checkbox with its bottom-left at x, y. Returns its size."""
        p = c.palette
        size = c.px(16)
        x, y = round(x), round(y)
        if checked:
            c.rect(x, y, size, size, p.with_alpha(p.accent, 0.5) if soft else p.accent, c.px(4))
            c.text(CHECK_GLYPH, x + size / 2, centered_baseline(c, y, size, 11), 11, p.on_accent, "CENTER", bold=True)
        else:
            c.outline(x, y, size, size, p.border, c.px(4), max(1.0, round(c.scale)), p.inset)
        if enabled:
            self.rows.append(((x - c.px(4), y - c.px(4), size + c.px(8), size + c.px(8)), on_toggle))
        return size

    def lock_glyph(self, c: Canvas, x: float, y: float, color: Color) -> None:
        """A small padlock, 12 units wide, with its bottom-left at x, y."""
        body_w, body_h = c.px(12), c.px(9)
        ring = c.px(8)
        c.outline(x + (body_w - ring) / 2, y + body_h - c.px(2), ring, ring, color, ring / 2, c.px(1.6), (0, 0, 0, 0))
        c.rect(x, y, body_w, body_h, color, c.px(2))

    def notice_box(self, c: Canvas, x: float, y: float, w: float, text: str, button: Optional[Tuple[str, Callable[[], None]]] = None) -> float:
        """A one-line notice in an inset box with its bottom-left at x, y, and
        an optional button on the right. Returns the height used."""
        p = c.palette
        h = c.px(52)
        c.outline(x, y, w, h, p.line, c.px(RADIUS), max(1.0, round(c.scale)), p.inset)
        text_w = w - c.px(32)
        if button is not None:
            label, action = button
            bw, bh = self.button_width(c, label, "secondary"), c.px(32)
            self.button(label, x + w - bw - c.px(10), y + (h - bh) / 2, bw, bh, action, "secondary")
            text_w -= bw + c.px(16)
        lines = c.wrap(text, BODY, text_w)
        baseline = centered_baseline(c, y, h, BODY)
        if len(lines) <= 1:
            c.text(text, x + c.px(16), baseline, BODY, p.text)
        else:
            # Two lines at most; the box keeps its height
            gap = c.px(BODY) * 0.68
            c.text(lines[0], x + c.px(16), baseline + gap, BODY, p.text)
            c.text(c.ellipsize(" ".join(lines[1:]), BODY, text_w), x + c.px(16), baseline - gap, BODY, p.text)
        return h

    def online_notice(self, c: Canvas, x: float, y: float, w: float) -> float:
        """Blender's online access is off: one sentence and the button that turns it on.
        Drawn with its bottom-left at x, y. Returns the height used, 0 when not needed."""
        st = setup_state.state
        if not st.online_blocked:
            return 0.0
        from ...backend.setup import online

        if online.locked():
            return self.notice_box(c, x, y, w, tr("Blender was started in offline mode. Start it normally to download content."))
        return self.notice_box(c, x, y, w, tr("Downloading needs Blender's online access, which is turned off."), (tr("Allow online access"), st.allow_online))

    def error_paragraph(self, c: Canvas, text: str, x: float, bottom: float, w: float, color: Optional[Color] = None, support: bool = False, measure: bool = False) -> float:
        """Wrapped error text whose last line sits just above `bottom`; the
        support address in it is a link, and `support` adds a "Contact
        support" link when the text doesn't name the address. Returns the
        height used (only measured with `measure`)."""
        p = c.palette
        color = color or p.danger
        lines = c.wrap(text, BODY, w)
        extra = support and SUPPORT_EMAIL not in text
        line_h = c.px(BODY) * 1.45
        height = line_h * (len(lines) + (1 if extra else 0))
        if measure:
            return height
        y = bottom + height - c.px(BODY)
        for line in lines:
            if SUPPORT_EMAIL in line:
                before, _, after = line.partition(SUPPORT_EMAIL)
                cursor = x + c.text(before, x, y, BODY, color)
                cursor += self.link(c, SUPPORT_EMAIL, cursor, y, BODY, self.controller.contact_support)
                c.text(after, cursor, y, BODY, color)
            else:
                c.text(line, x, y, BODY, color)
            y -= line_h
        if extra:
            self.link(c, tr("Contact support"), x, y, BODY, self.controller.contact_support)
        return height

    def rich_text(self, c: Canvas, text: str, x: float, y: float, size: float, color: Color, links: List[str]) -> float:
        """Draw a line whose [bracketed] parts are clickable links, in order. Returns the width."""
        cursor = x
        link_index = 0
        for part in re.split(r"(\[[^\]]+\])", text):
            if not part:
                continue
            if part.startswith("[") and part.endswith("]"):
                label = part[1:-1]
                url = links[link_index] if link_index < len(links) else ""
                link_index += 1
                cursor += self.link(c, label, cursor, y, size, lambda url=url: self.controller.open_url(url))
            else:
                cursor += c.text(part, cursor, y, size, color)
        return cursor - x

    def picture_column(self, c: Canvas, image: str, alpha: float = 1.0) -> float:
        """A picture filling the left part of the card. Returns the x where it ends."""
        x, y, w, h = self.rect
        image_w = round(w * 0.46)
        radius = c.px(CARD_RADIUS)
        line = max(1.0, round(c.scale))
        c.rect(x + line, y + line, image_w - line, h - 2 * line, c.palette.inset, radius)
        texture = self.textures.get(image)
        if texture:
            # Rounded on the card's corners only: draw wider and clip at the column edge
            c.clip(x, y, image_w, h)
            c.image(texture, x + line, y + line, image_w + radius, h - 2 * line, radius - line, alpha=alpha)
            c.unclip()
        return x + image_w


class WelcomeScreen(Screen):
    """The first thing a new user sees: a picture, a few words and one button.
    An install from the trial page is offered the trial (and "I bought it");
    every other install is offered the content packs alone. Content found
    elsewhere on the computer can be used as it is."""

    name = "welcome"

    def layout(self, c: Canvas) -> None:
        st = setup_state.state
        p = c.palette
        x, y, w, h = self.rect
        column_x = self.picture_column(c, os.path.join(SETUP_IMAGE_DIR, "welcome.jpg")) + c.px(48)
        column_w = x + w - c.px(48) - column_x
        self.close_button(c, y + h - c.px(HEADER), c.px(HEADER))

        top = y + h - c.px(72)
        logo = c.px(44)
        self.logo(c, column_x, top - logo, logo)
        top -= logo + c.px(32)
        top -= c.paragraph(tr("Welcome to Human Generator"), column_x, top, 26, p.text, column_w, leading=1.2, bold=True) + c.px(20)
        body = tr("Make realistic humans in Blender: shape the body and face, then add clothing, hair, poses and expressions.")
        top -= c.paragraph(body, column_x, top, 14, p.muted, column_w, leading=1.55) + c.px(18)
        if st.rid:
            offer = tr("Start with the free trial, or install the full version from the files of your purchase.")
        else:
            offer = tr("Install the content packs from the files of your purchase.")
        c.paragraph(offer, column_x, top, 14, p.muted, column_w, leading=1.55)

        button_y = y + c.px(48)
        if st.rid:
            # Only an install from the trial page is offered the trial
            label = tr("Install the free trial")
            bw = self.button_width(c, label, "primary") + c.px(16)
            self.button(label, column_x, button_y, bw, c.px(40), self._trial, "primary")
            other = tr("I bought it")
            self.button(other, column_x + bw + c.px(8), button_y, self.button_width(c, other, "ghost"), c.px(40), self._full, "ghost")
        else:
            label = tr("Install the content packs")
            bw = self.button_width(c, label, "primary") + c.px(16)
            self.button(label, column_x, button_y, bw, c.px(40), self._full, "primary")

        # Content that is already on this computer
        line = c.px(SMALL) * 1.5
        baseline = button_y + c.px(40) + c.px(28)
        if st.found_folder:
            self.link(c, tr("Use this folder"), column_x, baseline, SMALL, lambda: self.controller.use_folder(st.found_folder))
            c.text(c.ellipsize(st.found_folder, SMALL, column_w), column_x, baseline + line, SMALL, p.text)
            c.text(tr("Found Human Generator content in"), column_x, baseline + 2 * line, SMALL, p.muted)
        else:
            used = c.text(tr("I already have the content installed"), column_x, baseline, SMALL, p.muted)
            self.link(c, tr("Select folder"), column_x + used + c.px(8), baseline, SMALL, self.controller.select_existing_folder)

    def _trial(self) -> None:
        setup_state.state.choose("trial")
        self.controller.go(setup_state.state.screen)

    def _full(self) -> None:
        setup_state.state.choose("full")
        self.controller.go(setup_state.state.screen)

    def key(self, event) -> bool:
        if event.type in ("RET", "NUMPAD_ENTER", "SPACE"):
            if setup_state.state.rid:
                self._trial()
            else:
                self._full()
            return True
        return False


FOLD = "fold"  # the "In the full version" row of the trial list


class PacksScreen(Screen):
    name = "packs"
    ROW = 52

    def __init__(self, controller, textures) -> None:
        super().__init__(controller, textures)
        self.offset = 0.0  # scroll, in pixels
        self._max_offset = 0.0
        self._thumb: Rect = (0, 0, 0, 0)
        self._track: Rect = (0, 0, 0, 0)
        self._drag: Optional[Tuple[float, float]] = None  # mouse y and offset at the press

    def scroll(self, pixels: float) -> bool:
        before = self.offset
        self.offset = max(0.0, min(self._max_offset, self.offset + pixels))
        return self.offset != before

    def press(self, x: float, y: float) -> bool:
        if self._max_offset > 0 and in_rect(self._thumb, x, y):
            self._drag = (y, self.offset)
            return True
        if self._max_offset > 0 and in_rect(self._track, x, y):
            tx, ty, tw, th = self._track
            self.offset = (1 - (y - ty) / th) * self._max_offset
            self.scroll(0)
            return True
        return super().press(x, y)

    def drag(self, x: float, y: float) -> bool:
        if self._drag is None:
            return False
        start_y, start_offset = self._drag
        travel = self._track[3] - self._thumb[3]
        if travel > 0:
            self.offset = start_offset + (start_y - y) * self._max_offset / travel
            self.scroll(0)
        return True

    def release(self, x: float, y: float) -> None:
        self._drag = None

    @staticmethod
    def rows_of(st) -> list:
        """The rows of the list. The trial shows its own packs and one folded
        line for the locked rest, which unfolds on a click."""
        if st.mode != "trial":
            return list(st.packs)
        free = [p for p in st.packs if not p.locked]
        locked = [p for p in st.packs if p.locked]
        if not locked:
            return free
        return free + [FOLD] + (locked if st.locked_open else [])

    def layout(self, c: Canvas) -> None:
        st = setup_state.state
        p = c.palette
        content = self.chrome(c)
        cx, cy, cw, ch = content
        line = max(1.0, round(c.scale))
        title, subtitle = self.copy(st)
        cursor = self.title_block(c, content, title, subtitle)

        # Folder: a read-only field and the button that changes it
        row_h = c.px(CONTROL_H)
        cursor -= row_h
        change = tr("Change…")
        button_w = self.button_width(c, change, "secondary")
        field_w = cw - button_w - c.px(8)
        c.outline(cx, cursor, field_w, row_h, p.line, c.px(RADIUS), line, p.inset)
        folder_label = tr("Content folder")
        baseline = centered_baseline(c, cursor, row_h, BODY)
        label_w = c.text(folder_label, cx + c.px(12), baseline, BODY, p.muted)
        path_x = cx + c.px(12) + label_w + c.px(12)
        c.text(c.ellipsize(st.folder, BODY, cx + field_w - c.px(12) - path_x), path_x, baseline, BODY, p.text)
        self.button(change, cx + cw - button_w, cursor, button_w, row_h, self.controller.change_folder, "secondary", enabled=not st.in_progress)
        cursor -= c.px(16)
        cursor -= self.toolbar(c, st, cx, cursor, cw)

        # The list, in a clipped, scrollable box between the folder and the footer
        list_bottom = cy + c.px(24)
        if st.online_blocked and not st.local:
            list_bottom += self.online_notice(c, cx, list_bottom, cw) + c.px(12)
        else:
            text, url = self.notice(st)
            if text:
                button = (tr("Learn more"), lambda: self.controller.open_url(url)) if url else None
                list_bottom += self.notice_box(c, cx, list_bottom, cw, text, button) + c.px(12)
        list_top = cursor
        area_h = list_top - list_bottom
        c.outline(cx, list_bottom, cw, area_h, p.line, c.px(RADIUS), line, p.inset)
        rows = self.rows_of(st)
        if not rows:
            self._track = self._thumb = (0, 0, 0, 0)
            self._max_offset = 0.0
            self.empty(c, st, cx, list_bottom, cw, area_h)
            self._footer(c, st)
            return

        row_h = c.px(self.ROW)
        content_h = row_h * len(rows)
        self._max_offset = max(0.0, content_h - (area_h - 2 * line))
        self.offset = max(0.0, min(self._max_offset, self.offset))
        scrolls = self._max_offset > 0
        right = cx + cw - c.px(28 if scrolls else 16)
        row_y = list_top - line + self.offset
        c.clip(cx + line, list_bottom + line, cw - 2 * line, area_h - 2 * line)
        for index, pack in enumerate(rows):
            row_y -= row_h
            if row_y + row_h < list_bottom or row_y > list_top:
                continue
            visible = (cx, max(row_y, list_bottom), cw, min(row_y + row_h, list_top) - max(row_y, list_bottom))
            if index:
                c.hline(cx + c.px(16), row_y + row_h, cw - c.px(32), p.line)
            if pack == FOLD:
                self._fold_row(c, st, cx, row_y, cw, row_h, right, visible)
                continue
            self._pack_row(c, st, pack, cx, row_y, cw, row_h, right, visible)
        c.unclip()
        if scrolls:
            bar_w = c.px(4)
            inset = c.px(6)
            track_h = area_h - 2 * inset
            thumb_h = max(c.px(28), track_h * area_h / content_h)
            thumb_y = list_top - inset - thumb_h - (track_h - thumb_h) * (self.offset / self._max_offset)
            bar_x = cx + cw - inset - bar_w
            self._track = (bar_x - c.px(6), list_bottom + inset, bar_w + c.px(12), track_h)
            self._thumb = (bar_x - c.px(6), thumb_y, bar_w + c.px(12), thumb_h)
            grabbed = self._drag is not None or in_rect(self._thumb, *self.mouse)
            c.rect(bar_x, thumb_y, bar_w, thumb_h, p.muted if grabbed else p.border, bar_w / 2)
        else:
            self._track = self._thumb = (0, 0, 0, 0)
            self.below_rows(c, st, cx, list_bottom, cw, list_top - content_h - list_bottom)

        self._footer(c, st)

    # What differs between the trial's pack list and the file list

    def copy(self, st) -> Tuple[str, str]:
        return packs_copy(st)

    def notice(self, st) -> Tuple[str, str]:
        return notice_text(st)

    def toolbar(self, c: Canvas, st, cx: float, top: float, cw: float) -> float:
        """A strip between the folder and the list. Returns the height it used."""
        return 0.0

    def empty(self, c: Canvas, st, cx: float, bottom: float, cw: float, area_h: float) -> None:
        """What the list box shows when it has no rows."""
        p = c.palette
        mid = bottom + area_h / 2
        if st.loading:
            c.text(tr("Loading the pack list…"), cx + cw / 2, mid, BODY, p.muted, "CENTER")
        elif st.catalogue_phase == "failed":
            c.paragraph(tr("Could not load the pack list.") + " " + tr(st.catalogue_error), cx + cw / 2, mid + c.px(36), BODY, p.danger, cw - c.px(80), align="CENTER")
            label = tr("Try again")
            bw = self.button_width(c, label, "secondary")
            self.button(label, cx + (cw - bw) / 2, mid - c.px(36), bw, c.px(CONTROL_H), st.load_catalogue, "secondary")
        elif not st.online_blocked:
            c.text(tr("Nothing to install."), cx + cw / 2, mid, BODY, p.muted, "CENTER")

    def below_rows(self, c: Canvas, st, cx: float, bottom: float, cw: float, room: float) -> None:
        """The room the rows leave in the list box: what goes to humgen3d.com,
        with the policy. Where the request form said that the trial lets us
        know when it is installed and upgraded (`shows_trial_notice`), this
        screen says it too; it comes first when there is room for one line only."""
        if room < c.px(44):
            return
        x, y = cx + c.px(16), bottom + c.px(16)
        usual = tr("The download and a daily update check go to humgen3d.com. [Privacy policy]")
        if not setup_state.shows_trial_notice():
            self.rich_text(c, usual, x, y, SMALL, c.palette.faint, [setup_state.PRIVACY_URL])
            return
        self.rich_text(c, tr(setup_state.TRIAL_NOTICE), x, y, SMALL, c.palette.faint, [setup_state.PRIVACY_URL])
        if room >= c.px(66):
            c.text(usual.replace(" [Privacy policy]", ""), x, y + c.px(SMALL) * 1.6, SMALL, c.palette.faint)

    def _pack_row(self, c: Canvas, st, pack, cx, row_y, cw, row_h, right, visible) -> None:
        p = c.palette
        line = max(1.0, round(c.scale))
        toggleable = pack.installable and not pack.required and pack.status != "up_to_date" and not st.in_progress
        if toggleable and in_rect(visible, *self.mouse):
            c.rect(cx + c.px(4), row_y + c.px(3), cw - c.px(8), row_h - c.px(6), p.hover, c.px(6))
        mid = row_y + row_h / 2
        lead_x = cx + c.px(16)
        if pack.locked:
            self.lock_glyph(c, lead_x + c.px(2), mid - c.px(7), p.faint)
            name_color = p.muted
        elif pack.left_out:
            c.text("–", lead_x + c.px(8), centered_baseline(c, mid - c.px(8), c.px(16), BODY), BODY, p.faint, "CENTER", bold=True)
            name_color = p.muted
        elif pack.status == "up_to_date" or pack.state == "done":
            c.text(CHECK_GLYPH, lead_x + c.px(8), centered_baseline(c, mid - c.px(8), c.px(16), BODY), BODY, p.success, "CENTER", bold=True)
            name_color = p.muted
        else:
            self.checkbox(c, lead_x, mid - c.px(8), pack.selected, self._toggler(pack), enabled=False, soft=pack.required)
            name_color = p.text
            if toggleable:
                self.rows.append((visible, self._toggler(pack)))
        text_x = lead_x + c.px(30)
        name_baseline = mid + c.px(3)
        detail_baseline = mid - c.px(14)

        tag = tr(pack.tag) if pack.tag else ""
        if pack.path:
            detail = file_detail(pack)
        elif pack.status in ("update_available", "update_required") and pack.installed_version:
            detail = tr("Installed {old}, update to {new}").format(old=".".join(str(n) for n in pack.installed_version), new=pack.version)
        else:
            detail = tr(pack.blurb)
        right_w = c.px(90)
        if tag:
            tag_w = c.text_width(tag, 11.5) + c.px(18)
            tag_h = c.px(20)
            c.outline(right - tag_w, mid - tag_h / 2, tag_w, tag_h, p.border, tag_h / 2, line, p.inset)
            c.text(tag, right - tag_w / 2, centered_baseline(c, mid - tag_h / 2, tag_h, 11.5), 11.5, p.muted, "CENTER")
            right_w = tag_w
        elif pack.installable and pack.status != "up_to_date":
            c.text(format_bytes(pack.size) if pack.size else "", right, name_baseline, BODY, p.text, "RIGHT")
            if pack.required:
                c.text(tr("Required"), right, detail_baseline, SMALL, p.faint, "RIGHT")
        text_w = right - right_w - c.px(16) - text_x
        c.text(c.ellipsize(tr(pack.name), BODY, text_w, bold=True), text_x, name_baseline, BODY, name_color, bold=True)
        c.text(c.ellipsize(detail, SMALL, text_w), text_x, detail_baseline, SMALL, p.warning if pack.needs_version and pack.installable else p.muted)

    def _fold_row(self, c: Canvas, st, cx, row_y, cw, row_h, right, visible) -> None:
        p = c.palette
        locked = [pk for pk in st.packs if pk.locked]
        if in_rect(visible, *self.mouse):
            c.rect(cx + c.px(4), row_y + c.px(3), cw - c.px(8), row_h - c.px(6), p.hover, c.px(6))
        mid = row_y + row_h / 2
        lead_x = cx + c.px(16)
        self.lock_glyph(c, lead_x + c.px(2), mid - c.px(7), p.faint)
        text_x = lead_x + c.px(30)
        toggle = tr("Hide") if st.locked_open else tr("Show")
        toggle_w = c.text_width(toggle, SMALL)
        c.text(toggle, right, mid - c.px(4), SMALL, p.text if in_rect(visible, *self.mouse) else p.link, "RIGHT")
        text_w = right - toggle_w - c.px(16) - text_x
        title = tr("In the full version: {count} more packs").format(count=len(locked))
        c.text(c.ellipsize(title, BODY, text_w, bold=True), text_x, mid + c.px(3), BODY, p.muted, bold=True)
        names = ", ".join(tr(pk.name) for pk in locked)
        c.text(c.ellipsize(names, SMALL, text_w), text_x, mid - c.px(14), SMALL, p.faint)
        self.rows.append((visible, self._toggle_locked))

    @staticmethod
    def _toggle_locked() -> None:
        st = setup_state.state
        st.locked_open = not st.locked_open

    def _footer(self, c: Canvas, st) -> None:
        p = c.palette
        x, y, w, h = self.rect
        if st.trial_installed_here and not st.in_progress:
            left = self.footer_actions(c, [
                (tr("Close"), self.controller.close, "ghost", True),
                (tr("I bought it"), self._full, "secondary", True),
                (tr("Buy full version"), lambda: self.controller.open_url(setup_state.buy_url(st.rid)), "primary", True),
            ])
            mid = y + c.px(FOOTER) / 2
            c.text(c.ellipsize(tr("Trial installed"), BODY, left - c.px(16) - x - c.px(PAD), bold=True), x + c.px(PAD), mid - c.px(4), BODY, p.text, bold=True)
            return
        if st.paused:
            left = self.footer_actions(c, [(tr("Discard download"), self._discard, "ghost", True), (tr("Resume"), self._install, "primary", True)])
            summary = tr("Download paused")
            detail = tr("{done} of {total}").format(done=format_bytes(st.done_bytes), total=format_bytes(st.total_bytes))
            warn = False
        else:
            label = update_label(len(st.selected)) if st.update_mode and st.selected else tr("Install")
            left = self.footer_actions(c, [self.back_or_close(), (label, self._install, "primary", st.can_install)])
            if st.local and not st.selected:
                summary = tr("No files to install yet")
            else:
                summary = pack_count(len(st.selected), format_bytes(st.total_bytes))
            detail, warn = space_text(st)
        text_x = x + c.px(PAD)
        text_w = left - c.px(16) - text_x
        mid = y + c.px(FOOTER) / 2
        c.text(c.ellipsize(summary, BODY, text_w, bold=True), text_x, mid + c.px(3), BODY, p.text, bold=True)
        c.text(c.ellipsize(detail, SMALL, text_w), text_x, mid - c.px(14), SMALL, p.danger if warn else p.muted)

    def _toggler(self, pack):
        def toggle():
            pack.selected = not pack.selected
        return toggle

    def _install(self) -> None:
        st = setup_state.state
        st.start()
        self.controller.go(st.screen)

    def _discard(self) -> None:
        setup_state.state.abort()
        self.controller.go(setup_state.state.screen)

    def _full(self) -> None:
        setup_state.state.begin_full()
        self.controller.go(setup_state.state.screen)


class FilesScreen(PacksScreen):
    """The full version: the `.hgpack` files the user picked, as a list, with
    what installing each one does. Nothing here asks a server anything."""

    name = "files"

    @staticmethod
    def rows_of(st) -> list:
        return list(st.packs)

    def copy(self, st) -> Tuple[str, str]:
        return files_copy(st)

    def notice(self, st) -> Tuple[str, str]:
        return files_notice(st), ""

    def empty(self, c: Canvas, st, cx: float, bottom: float, cw: float, area_h: float) -> None:
        p = c.palette
        mid = bottom + area_h / 2
        label = tr("Select .hgpack files…")
        bw = self.button_width(c, label, "primary") + c.px(16)
        self.button(label, cx + (cw - bw) / 2, mid - c.px(4), bw, c.px(40), self.controller.select_files, "primary")
        c.text(tr("You can select several files at once."), cx + cw / 2, mid - c.px(32), SMALL, p.muted, "CENTER")
        self.link(c, tr("Where are my files?"), cx + cw / 2 - c.text_width(tr("Where are my files?"), SMALL) / 2, mid - c.px(56), SMALL, self._help)

    def toolbar(self, c: Canvas, st, cx: float, top: float, cw: float) -> float:
        """Above the rows, so it shows however long the list is: the way to
        add more files, and where the files of a purchase are."""
        if not st.packs:
            return 0.0
        baseline = top - c.px(SMALL) - c.px(2)
        if not st.in_progress:
            self.link(c, tr("Select more files…"), cx, baseline, SMALL, self.controller.select_files)
        self.link(c, tr("Where are my files?"), cx + cw, baseline, SMALL, self._help, align="RIGHT")
        return c.px(SMALL) + c.px(16)

    def below_rows(self, c: Canvas, st, cx: float, bottom: float, cw: float, room: float) -> None:
        """The room the rows leave: these packs come from this computer."""
        if room < c.px(44):
            return
        c.text(tr("Installed from the files on this computer. Nothing is downloaded."), cx + c.px(16), bottom + c.px(16), SMALL, c.palette.faint)

    def _help(self) -> None:
        self.controller.open_url(docs_url(setup_state.FILES_HELP))

    def key(self, event) -> bool:
        if event.type in ("RET", "NUMPAD_ENTER") and not setup_state.state.packs:
            self.controller.select_files()
            return True
        return False


class SlidesScreen(Screen):
    """What shows while the content installs, and from "Show me around": the
    pages of the Get started tutorial, turned by hand, above the progress."""

    name = "slides"
    PROGRESS = 100  # height of the progress block
    NAV = 46  # height of the row with the dots and the arrows

    def __init__(self, controller, textures) -> None:
        super().__init__(controller, textures)
        self.index = 0
        self.changed_at = time.monotonic()
        self.bar_shown = 0.0

    def enter(self) -> None:
        self.changed_at = time.monotonic()

    def go_to(self, index: int) -> None:
        self.index = index % len(TUTORIAL_PAGES)
        self.changed_at = time.monotonic()

    def key(self, event) -> bool:
        if event.type in ("RIGHT_ARROW", "RET", "SPACE"):
            self.go_to(self.index + 1)
            return True
        if event.type == "LEFT_ARROW":
            self.go_to(self.index - 1)
            return True
        return False

    def close_button(self, c: Canvas, y: float, h: float) -> None:
        """While the download runs the corner says what closing does."""
        if not setup_state.state.active:
            super().close_button(c, y, h)
            return
        x, _, w, _ = self.rect
        label = tr("Continue in background")
        bw, bh = self.button_width(c, label, "secondary"), c.px(30)
        self.button(label, x + w - c.px(PAD) - bw, y + (h - bh) / 2, bw, bh, self.controller.close, "secondary")

    def layout(self, c: Canvas) -> None:
        st = setup_state.state
        p = c.palette
        x, y, w, h = self.rect
        column_x = x + c.px(PAD)
        column_w = w - 2 * c.px(PAD)
        right = column_x + column_w

        header_y = y + h - c.px(HEADER)
        self.brand(c, column_x, header_y, c.px(HEADER))
        self.close_button(c, header_y, c.px(HEADER))

        # The tutorial page, as large as fits between the header and the dots
        block_top = y + c.px(self.PROGRESS)
        area_y = block_top + c.px(self.NAV)
        area_h = header_y - area_y
        image_w = round(min(column_w, area_h * TUTORIAL_ASPECT))
        image_h = round(image_w / TUTORIAL_ASPECT)
        image_x = round(x + (w - image_w) / 2)
        image_y = round(area_y + (area_h - image_h) / 2)
        radius = c.px(RADIUS)
        c.rect(image_x, image_y, image_w, image_h, p.inset, radius)
        texture = self.textures.get(os.path.join(TUTORIAL_IMAGE_DIR, TUTORIAL_PAGES[self.index % len(TUTORIAL_PAGES)]))
        if texture:
            fade = ease_out((time.monotonic() - self.changed_at) / FADE_SECONDS)
            c.image(texture, image_x, image_y, image_w, image_h, radius, alpha=fade)

        # Dots and arrows
        arrow = c.px(30)
        arrows_y = block_top + (c.px(self.NAV) - arrow) / 2
        dot = c.px(6)
        dx = column_x
        for i in range(len(TUTORIAL_PAGES)):
            current = i == self.index
            c.rect(dx, arrows_y + (arrow - dot) / 2, dot * 3 if current else dot, dot, p.text if current else p.border, dot / 2)
            dx += dot * (3 if current else 1) + c.px(6)
        self.button("‹", right - 2 * arrow - c.px(4), arrows_y, arrow, arrow, lambda: self.go_to(self.index - 1), "ghost", size=16)
        self.button("›", right - arrow, arrows_y, arrow, arrow, lambda: self.go_to(self.index + 1), "ghost", size=16)

        # Progress
        c.hline(x, block_top, w, p.line)
        actions: List[Tuple[str, Callable[[], None], str]] = []
        if st.active:
            label, detail, fraction, color = download_label(st), download_detail(st), st.fraction, None
            if st.phase == "downloading":
                # Extraction can't stop halfway, so there is no button meanwhile
                actions = [(tr("Pause"), self._pause, "secondary")]
        elif st.paused:
            label, fraction, color = tr("Download paused"), st.fraction, p.faint
            detail = tr("{done} of {total}").format(done=format_bytes(st.done_bytes), total=format_bytes(st.total_bytes))
            actions = [(tr("Packs"), self._list, "ghost"), (tr("Resume"), self._resume, "primary")]
        elif st.phase == "done":
            label, detail, fraction, color = tr("All packs installed"), tr("Ready to use"), 1.0, p.success
            actions = [(tr("Continue"), lambda: self.controller.go("done"), "primary")]
        elif st.phase == "failed":
            label, detail, fraction, color = failure_title(st), error_text(st.error, tr), st.fraction, p.danger
            actions = [(tr("Continue"), lambda: self.controller.go("done"), "primary")]
        else:
            label, detail, fraction, color = tr("Not started"), "", st.fraction, p.faint
            actions = [(tr("Packs"), self._list, "primary")]
        widths = [self.button_width(c, a[0], a[2]) for a in actions]
        buttons_w = sum(widths) + c.px(8) * max(0, len(widths) - 1)
        bar_w = column_w - buttons_w - (c.px(24) if actions else 0)
        mid = y + c.px(self.PROGRESS) / 2
        self.bar_shown = lerp(self.bar_shown, fraction, 0.15)
        percent = f"{self.bar_shown:.0%}"
        percent_w = c.text(percent, column_x + bar_w, mid + c.px(12), BODY, p.muted, "RIGHT")
        room = bar_w - percent_w - c.px(10)
        if st.active and c.text_width(label, BODY, bold=True) > room:
            label = download_label(st, count=False)
        c.text(c.ellipsize(label, BODY, room, bold=True), column_x, mid + c.px(12), BODY, p.text, bold=True)
        self.draw_progress_bar(c, column_x, mid - c.px(2), bar_w, self.bar_shown, color)
        c.text(c.ellipsize(detail, SMALL, bar_w), column_x, mid - c.px(22), SMALL, p.muted)
        bx = right - buttons_w
        for (text, action, kind), bw in zip(actions, widths):
            self.button(text, bx, mid - c.px(CONTROL_H) / 2, bw, c.px(CONTROL_H), action, kind)
            bx += bw + c.px(8)

    def _pause(self) -> None:
        """Stop and keep what was fetched; Resume continues from there."""
        setup_state.state.pause()

    def _list(self) -> None:
        """Back to the list this install came from."""
        self.controller.go("files" if setup_state.state.local else "packs")

    def _resume(self) -> None:
        st = setup_state.state
        st.start()
        self.controller.go(st.screen)


class DoneScreen(Screen):
    name = "done"
    GROUP_H = 200  # mark, title, text and folder, roughly

    def layout(self, c: Canvas) -> None:
        st = setup_state.state
        p = c.palette
        content = self.chrome(c)
        cx, cy, cw, ch = content
        failed = st.phase == "failed"
        mark = c.px(40)
        # The few lines of this screen sit in the middle of the card, not at its top
        ch -= max(0.0, (ch - c.px(self.GROUP_H)) / 2 - c.px(28))
        top = cy + ch - c.px(28)
        color = p.danger if failed else p.success
        c.rect(cx, top - mark, mark, mark, p.with_alpha(color, 0.16), mark / 2)
        c.text("!" if failed else CHECK_GLYPH, cx + mark / 2, centered_baseline(c, top - mark, mark, 18), 18, color, "CENTER", bold=True)
        title_area = (cx, cy, cw, ch - mark - c.px(16))
        if failed:
            self._failed(c, st, title_area)
            return
        packs = pack_count(len(st.selected), format_bytes(st.total_bytes))
        if st.adopted:
            title, subtitle = tr("Human Generator is ready"), tr("Using the content in this folder:")
        elif st.update_mode:
            title, subtitle = tr("Content updated"), tr("{packs}, updated in this folder:").format(packs=packs)
        elif st.upgrading_trial:
            title, subtitle = tr("Human Generator is ready"), tr("The trial content is replaced by the full library, in this folder:")
        else:
            title, subtitle = tr("Human Generator is ready"), tr("{packs}, installed in this folder:").format(packs=packs)
        cursor = self.title_block(c, title_area, title, subtitle) + c.px(8)
        row_h = c.px(CONTROL_H)
        c.outline(cx, cursor - row_h, cw, row_h, p.line, c.px(RADIUS), max(1.0, round(c.scale)), p.inset)
        c.text(c.ellipsize(st.folder, BODY, cw - c.px(24)), cx + c.px(12), centered_baseline(c, cursor - row_h, row_h, BODY), BODY, p.text)
        cursor -= row_h + c.px(28)
        if can_open_sidebar_tab():
            primary = tr("Get started")
        else:
            primary = tr("Close")
            c.text(tr("Open the HumGen tab in the sidebar (N)"), cx, cursor, SMALL, p.muted)
        actions = [(primary, self.controller.create_human, "primary", True)]
        if not st.update_mode and not st.adopted:
            actions.insert(0, (tr("Show me around"), self._tour, "secondary", True))
        self.footer_actions(c, actions)

    def _failed(self, c: Canvas, st, area: Rect) -> None:
        p = c.palette
        cx, cy, cw, ch = area
        message = error_text(st.error, tr)
        cursor = self.title_block(c, area, failure_title(st), "")
        height = self.error_paragraph(c, message, cx, 0, cw * 0.9, p.muted, measure=True)
        self.error_paragraph(c, message, cx, cursor + c.px(12) - height, cw * 0.9, p.muted)
        cursor += c.px(12) - height - c.px(8)
        if st.local:
            rest = tr("Packs that finished stay installed. Your files are not changed.")
        else:
            rest = tr("Packs that finished stay installed, and the download resumes where it stopped.")
        c.paragraph(rest, cx, cursor, BODY, p.muted, cw * 0.9)
        self.footer_actions(c, [
            (tr("Contact support"), self.controller.contact_support, "ghost", True),
            (tr("Retry"), self._retry, "primary", True),
        ])

    def _retry(self) -> None:
        st = setup_state.state
        st.start()
        self.controller.go(st.screen)

    def _tour(self) -> None:
        self.controller.go("slides")


class TooSmallScreen(Screen):
    """Instead of the card when the viewport can't hold it, even scaled down."""

    name = "too_small"
    W, H = 340, 150

    def card_size(self, c: Canvas) -> Tuple[float, float]:
        return c.px(self.W), c.px(self.H)

    def layout(self, c: Canvas) -> None:
        p = c.palette
        x, y, w, h = self.rect
        pad = c.px(20)
        top = y + h - pad
        top -= c.paragraph(tr("This viewport is too small for the setup."), x + pad, top, BODY, p.text, w - 2 * pad, bold=True) + c.px(6)
        c.paragraph(tr("Make it larger, or go on in the sidebar."), x + pad, top, BODY, p.muted, w - 2 * pad)
        label = tr("Continue in the sidebar")
        bw = self.button_width(c, label, "primary")
        self.button(label, x + w - pad - bw, y + pad, bw, c.px(CONTROL_H), self.controller.to_sidebar, "primary")
        self.button(tr("Close"), x + pad - c.px(10), y + pad, self.button_width(c, tr("Close"), "ghost"), c.px(CONTROL_H), self.controller.close, "ghost")


SCREENS = {cls.name: cls for cls in (WelcomeScreen, PacksScreen, FilesScreen, SlidesScreen, DoneScreen)}
