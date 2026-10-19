# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The screens of the setup overlay and the widgets they are made of.

A screen lays itself out in the card rectangle on every draw (the region size
and interface scale can change), draws, and answers mouse and keyboard events
through the widgets it placed. Screens talk to the operator through
`Controller`. Which screen shows is `state.screen`, so the sidebar fallback and
the overlay always show the same step.
"""
import os
import re
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import bpy

from ...common.i18n import tr
from . import state as setup_state
from .draw import Canvas, Color, TextureCache, ease_out, lerp
from .state import format_bytes, free_space

Rect = Tuple[float, float, float, float]

SLIDE_IMAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons"
)
# Pictures of the welcome and choice screens ship with the add-on
SETUP_IMAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")

# PROTOTYPE decks. The real ones are fetched from the server as JSON + WebP.
# Texts are English keys, translated through tr() when drawn.
DECKS = {
    "licensed": [
        ("haircards_high.png", "Start with a human", "Pick one of 42 starting humans and change the body, face and age with the sliders. Everything stays editable, also after you add clothing."),
        ("haircards_medium.png", "Dress and style", "Outfits and footwear fit the body you made. Hair, beards and eyebrows come as particle systems you can comb."),
        ("haircards_low.png", "Pose and express", "Poses from the library, Rigify for your own, and expressions you can mix and key."),
        ("haircards_ultra.png", "Export to your engine", "The Process tab bakes textures, builds hair cards and LODs, and writes a manifest the Unity, Unreal and Godot companions read."),
        ("livekey.png", "Make it yours", "Save your own humans, outfits, poses and textures as content packs and share them with your team."),
    ],
    "trial": [
        ("haircards_high.png", "Welcome to the trial", "One of each: a human, a skin, an outfit, a hairstyle and four poses. Everything else is visible but locked, so you can see what the full library holds."),
        ("haircards_medium.png", "200+ outfits and hairstyles", "The full version unlocks the whole library, in 4K, without watermark."),
        ("haircards_low.png", "Batch generation", "Generate crowds with randomised bodies, faces, clothing and poses in one go."),
        ("haircards_ultra.png", "Game export", "Bake, reduce and rig for Unity, Unreal and Godot. Full version only."),
    ],
}

SLIDE_SECONDS = 7.0
FADE_SECONDS = 0.35
CLOSE_GLYPH = "✕"
CHECK_GLYPH = "✓"


def props():
    """The licence form, shared with the sidebar panel through the window manager."""
    return bpy.context.window_manager.hg_setup


def pack_count(count: int, size: str) -> str:
    if count == 1:
        return tr("1 pack · {size}").format(size=size)
    return tr("{count} packs · {size}").format(count=count, size=size)


def in_rect(rect: Rect, x: float, y: float) -> bool:
    rx, ry, rw, rh = rect
    return rx <= x <= rx + rw and ry <= y <= ry + rh


@dataclass
class Button:
    label: str
    rect: Rect
    on_click: Callable[[], None]
    kind: str = "secondary"  # primary, secondary, ghost, danger, link
    enabled: bool = True
    hover: bool = False
    size: float = 13

    def hit(self, x: float, y: float) -> bool:
        return in_rect(self.rect, x, y)

    def draw(self, c: Canvas) -> None:
        p = c.palette
        x, y, w, h = self.rect
        radius = c.px(8)
        if self.kind == "primary":
            fill = p.accent_hover if self.hover else p.accent
            text = p.on_accent
        elif self.kind == "danger":
            fill = p.danger
            text = p.on_accent
        elif self.kind == "secondary":
            fill = p.panel_hover if self.hover else p.panel
            text = p.text
        elif self.kind == "link":
            fill = (0, 0, 0, 0)
            text = p.accent_hover if self.hover else p.accent
        else:  # ghost
            fill = p.panel if self.hover else (0, 0, 0, 0)
            text = p.muted if not self.hover else p.text
        if not self.enabled:
            fill = (fill[0], fill[1], fill[2], fill[3] * 0.4)
            text = (text[0], text[1], text[2], text[3] * 0.5)
        c.rect(x, y, w, h, fill, radius)
        baseline = y + h / 2 - c.px(self.size * 0.38)
        c.text(self.label, x + w / 2, baseline, self.size, text, "CENTER")
        if self.kind == "link":
            tw = c.text_width(self.label, self.size)
            c.rect(x + w / 2 - tw / 2, baseline - c.px(3), tw, c.px(1), text)


class TextField:
    """A single-line text input bound to a property of the licence form."""

    def __init__(self, prop: str, placeholder: str) -> None:
        self.prop = prop
        self.placeholder = placeholder
        self.rect: Rect = (0, 0, 0, 0)
        self.focused = False
        self.select_all = False
        self.enabled = True

    @property
    def value(self) -> str:
        return getattr(props(), self.prop)

    @value.setter
    def value(self, text: str) -> None:
        setattr(props(), self.prop, text)

    def focus(self, on: bool = True) -> None:
        self.focused = on
        self.select_all = False

    def draw(self, c: Canvas, x: float, y: float, w: float, h: float) -> None:
        p = c.palette
        self.rect = (x, y, w, h)
        radius = c.px(8)
        if self.focused:
            c.outline(x, y, w, h, p.accent, radius, c.px(1.5), p.panel_hover_solid)
        else:
            c.rect(x, y, w, h, p.panel, radius)
        if not self.enabled:
            c.rect(x, y, w, h, (p.card[0], p.card[1], p.card[2], 0.5), radius)
        text = self.value
        size = 13.5
        pad = c.px(12)
        baseline = y + h / 2 - c.px(5)
        c.clip(x + c.px(2), y, w - c.px(4), h)
        if text:
            tw = c.text_width(text, size)
            shift = max(0.0, tw - (w - 2 * pad))  # keep the end in view
            if self.select_all and self.focused:
                c.rect(x + pad - shift, baseline - c.px(4), tw, c.px(size) + c.px(4), (p.accent[0], p.accent[1], p.accent[2], 0.35), c.px(2))
            c.text(text, x + pad - shift, baseline, size, p.text)
            caret_x = x + pad - shift + tw + c.px(1)
        else:
            c.text(self.placeholder, x + pad, baseline, size, p.muted)
            caret_x = x + pad
        if self.focused and int(time.monotonic() * 2) % 2 == 0:
            c.rect(caret_x, baseline - c.px(3), c.px(1.5), c.px(size) + c.px(2), p.text)
        c.unclip()

    def key(self, event) -> bool:
        """Edit on a key press. Returns True when the event was used."""
        if not self.focused:
            return False
        command = event.ctrl or event.oskey
        if command and event.type == "V":
            self._insert(bpy.context.window_manager.clipboard.replace("\n", " ").strip())
            return True
        if command and event.type == "A":
            self.select_all = bool(self.value)
            return True
        if event.type == "BACK_SPACE":
            self.value = "" if self.select_all else self.value[:-1]
            self.select_all = False
            return True
        if event.type == "DEL":
            if self.select_all:
                self.value = ""
                self.select_all = False
            return True
        if not command and len(event.unicode) == 1 and event.unicode.isprintable():
            self._insert(event.unicode)
            return True
        return False

    def _insert(self, text: str) -> None:
        self.value = text if self.select_all else self.value + text
        self.select_all = False


class Controller:
    """What a screen may ask of the operator."""

    def go(self, screen: str) -> None: ...
    def close(self) -> None: ...
    def change_folder(self) -> None: ...
    def create_human(self) -> None: ...
    def open_url(self, url: str) -> None: ...


class Screen:
    name = "screen"
    show_close = True

    def __init__(self, controller: Controller, textures: TextureCache) -> None:
        self.controller = controller
        self.textures = textures
        self.buttons: List[Button] = []
        self.rows: List[Tuple[Rect, Callable[[], None]]] = []
        self.rect: Rect = (0, 0, 0, 0)
        self.mouse: Tuple[float, float] = (-1.0, -1.0)

    def card_size(self, c: Canvas) -> Tuple[float, float]:
        return c.px(820), c.px(560)

    def enter(self) -> None:
        """The screen was just switched to."""

    def draw(self, c: Canvas, rect: Rect) -> None:
        self.rect = rect
        self.buttons = []
        self.rows = []
        self.layout(c)
        if self.show_close:
            self.close_button(c)
        for button in self.buttons:
            button.hover = button.enabled and button.hit(*self.mouse)
            button.draw(c)

    def layout(self, c: Canvas) -> None:  # draws and places widgets
        raise NotImplementedError

    def close_button(self, c: Canvas) -> None:
        x, y, w, h = self.rect
        size = c.px(32)
        inset = c.px(12)
        self.button(CLOSE_GLYPH, x + w - inset - size, y + h - inset - size, size, size, self.controller.close, "ghost", size=14)

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

    # Helpers

    def button(self, label: str, x: float, y: float, w: float, h: float, on_click: Callable[[], None], kind: str = "secondary", enabled: bool = True, size: float = 13) -> Button:
        button = Button(label, (x, y, w, h), on_click, kind, enabled, size=size)
        self.buttons.append(button)
        return button

    def header(self, c: Canvas, title: str, subtitle: str) -> float:
        x, y, w, h = self.rect
        pad = c.px(36)
        top = y + h - pad
        c.text(title, x + pad, top - c.px(22), 24, c.palette.text)
        used = c.paragraph(subtitle, x + pad, top - c.px(34), 13.5, c.palette.muted, w - 2 * pad - c.px(40), leading=1.4)
        return top - c.px(34) - used - c.px(14)

    def draw_progress_bar(self, c: Canvas, x: float, y: float, w: float, fraction: float, color: Optional[Color] = None) -> None:
        h = c.px(6)
        c.rect(x, y, w, h, c.palette.faint, h / 2)
        if fraction > 0:
            c.rect(x, y, max(w * fraction, h), h, color or c.palette.accent, h / 2)

    def checkbox(self, c: Canvas, x: float, y: float, checked: bool, on_toggle: Callable[[], None], enabled: bool = True, soft: bool = False) -> float:
        """An 18-unit checkbox with its bottom-left at x, y. Returns its size."""
        p = c.palette
        size = c.px(18)
        if checked:
            fill = p.accent if not soft else (p.accent[0], p.accent[1], p.accent[2], 0.55)
            c.rect(x, y, size, size, fill, c.px(4))
            c.text(CHECK_GLYPH, x + size / 2, y + c.px(3.5), 12, p.on_accent, "CENTER")
        else:
            c.outline(x, y, size, size, p.faint, c.px(4), c.px(1.2), p.card)
        if enabled:
            self.rows.append(((x - c.px(4), y - c.px(4), size + c.px(8), size + c.px(8)), on_toggle))
        return size

    def lock_glyph(self, c: Canvas, x: float, y: float, color: Color) -> None:
        """A small padlock, 14 units wide, with its bottom-left at x, y."""
        body_w, body_h = c.px(14), c.px(10)
        ring = c.px(9)
        c.outline(x + (body_w - ring) / 2, y + body_h - c.px(2), ring, ring, color, ring / 2, c.px(2), (0, 0, 0, 0))
        c.rect(x, y, body_w, body_h, color, c.px(2.5))

    def online_notice(self, c: Canvas, x: float, y: float, w: float) -> float:
        """Blender's online access is off: one sentence and the button that turns it on.
        Drawn with its bottom-left at x, y. Returns the height used, 0 when not needed."""
        st = setup_state.state
        if not st.online_blocked:
            return 0.0
        p = c.palette
        h = c.px(56)
        c.rect(x, y, w, h, p.panel, c.px(8))
        from ...backend.setup import online

        if online.locked():
            text = tr("Blender was started in offline mode. Start it normally to download content.")
            c.paragraph(text, x + c.px(14), y + h - c.px(14), 12.5, p.text, w - c.px(28), leading=1.35)
            return h
        text = tr("Downloading needs Blender's online access, which is turned off.")
        bw, bh = c.px(170), c.px(32)
        c.paragraph(text, x + c.px(14), y + h - c.px(14), 12.5, p.text, w - bw - c.px(40), leading=1.35)
        self.button(tr("Allow online access"), x + w - bw - c.px(12), y + (h - bh) / 2, bw, bh, st.allow_online, "primary", size=12.5)
        return h

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
                width = c.text_width(label, size)
                self.button(label, cursor - c.px(2), y - c.px(6), width + c.px(4), c.px(size) + c.px(8), lambda url=url: self.controller.open_url(url), "link", size=size)
                cursor += width
            else:
                cursor += c.text(part, cursor, y, size, color)
        return cursor - x


class WelcomeScreen(Screen):
    """The first thing a new user sees: a picture and one button."""

    name = "welcome"

    def card_size(self, c: Canvas) -> Tuple[float, float]:
        return c.px(720), c.px(560)

    def layout(self, c: Canvas) -> None:
        p = c.palette
        x, y, w, h = self.rect
        pad = c.px(36)
        c.text(tr("Welcome to Human Generator"), x + w / 2, y + h - pad - c.px(22), 24, p.text, "CENTER")
        bw, bh = c.px(260), c.px(48)
        button_y = y + pad
        image_y = button_y + bh + c.px(28)
        image_h = y + h - pad - c.px(50) - image_y
        image_w = w - 2 * pad
        c.rect(x + pad, image_y, image_w, image_h, p.panel, c.px(14))
        texture = self.textures.get(os.path.join(SETUP_IMAGE_DIR, "welcome.jpg"))
        if texture:
            c.image(texture, x + pad, image_y, image_w, image_h, c.px(14))
        self.button(tr("Get started"), x + (w - bw) / 2, button_y, bw, bh, lambda: self.controller.go("choose"), "primary", size=15)

    def key(self, event) -> bool:
        if event.type in ("RET", "NUMPAD_ENTER", "SPACE"):
            self.controller.go("choose")
            return True
        return False


class ChooseScreen(Screen):
    """Free trial or licence, as two picture tiles."""

    name = "choose"

    def card_size(self, c: Canvas) -> Tuple[float, float]:
        return c.px(760), c.px(520)

    def layout(self, c: Canvas) -> None:
        x, y, w, h = self.rect
        pad = c.px(36)
        cursor = self.header(c, tr("How do you want to start?"), tr("A licence can be activated later at any time."))
        gap = c.px(16)
        tile_w = (w - 2 * pad - gap) / 2
        tile_h = cursor - y - pad - c.px(8)
        tile_y = y + pad
        self.tile(c, x + pad, tile_y, tile_w, tile_h, "trial.jpg", tr("Free trial"), tr("One human, an outfit, a hairstyle and four poses, so you can try the workflow. No account needed."), tr("Start the trial"), lambda: self._choose("trial"))
        self.tile(c, x + pad + tile_w + gap, tile_y, tile_w, tile_h, "license.jpg", tr("Activate licence"), tr("Bought Human Generator on Superhive? Enter your order to install the full library."), tr("Enter your order"), lambda: self._choose("licensed"))

    def tile(self, c: Canvas, x: float, y: float, w: float, h: float, image: str, title: str, blurb: str, action: str, on_click: Callable[[], None]) -> None:
        p = c.palette
        hovered = in_rect((x, y, w, h), *self.mouse)
        radius = c.px(12)
        if hovered:
            c.outline(x, y, w, h, p.accent, radius, c.px(1.5), p.panel_hover_solid)
        else:
            c.rect(x, y, w, h, p.panel, radius)
        inset = c.px(8)
        image_h = h * 0.42
        image_y = y + h - inset - image_h
        c.rect(x + inset, image_y, w - 2 * inset, image_h, p.faint, radius - inset)
        texture = self.textures.get(os.path.join(SETUP_IMAGE_DIR, image))
        if texture:
            c.image(texture, x + inset, image_y, w - 2 * inset, image_h, radius - inset)
        inner = c.px(22)
        top = image_y - c.px(18)
        c.text(title, x + inner, top - c.px(16), 18, p.text)
        c.paragraph(blurb, x + inner, top - c.px(32), 13, p.muted, w - 2 * inner, leading=1.45)
        c.text(action + "  ›", x + inner, y + inner, 13.5, p.accent_hover if hovered else p.accent)
        self.rows.append(((x, y, w, h), on_click))

    def _choose(self, mode: str) -> None:
        setup_state.state.choose(mode)
        self.controller.go(setup_state.state.screen)


class LicenseScreen(Screen):
    name = "license"

    def __init__(self, controller, textures) -> None:
        super().__init__(controller, textures)
        self.guid = TextField("order_guid", tr("From your Superhive order email"))
        self.email = TextField("email", tr("The address of your Superhive account"))
        self.fields = [self.guid, self.email]

    def card_size(self, c: Canvas) -> Tuple[float, float]:
        return c.px(700), c.px(560 if setup_state.state.online_blocked else 500)

    def enter(self) -> None:
        setup_state.state.prefill_form(props())
        for field in self.fields:
            field.focus(False)
        (self.guid if not self.guid.value else self.email).focus()

    def layout(self, c: Canvas) -> None:
        st = setup_state.state
        p = c.palette
        f = props()
        x, y, w, h = self.rect
        pad = c.px(36)
        cursor = self.header(c, tr("Activate your licence"), tr("Enter the order you placed on Superhive. We check it once and remember it on this computer."))
        inner_w = w - 2 * pad
        field_h = c.px(40)
        checking = st.checking
        for field in self.fields:
            field.enabled = not checking

        cursor -= c.px(14)
        c.text(tr("Order GUID"), x + pad, cursor, 12.5, p.muted)
        help_label = tr("Where do I find it?")
        help_w = c.text_width(help_label, 12.5) + c.px(8)
        self.button(help_label, x + w - pad - help_w, cursor - c.px(7), help_w, c.px(24), lambda: self.controller.open_url(setup_state.ORDER_HELP_URL), "link", size=12.5)
        cursor -= c.px(10) + field_h
        self.guid.draw(c, x + pad, cursor, inner_w, field_h)
        cursor -= c.px(26)
        c.text(tr("Email"), x + pad, cursor, 12.5, p.muted)
        why_label = tr("Why is this needed?")
        why_w = c.text_width(why_label, 12.5) + c.px(8)
        self.button(why_label, x + w - pad - why_w, cursor - c.px(7), why_w, c.px(24), lambda: self.controller.open_url(setup_state.EMAIL_HELP_URL), "link", size=12.5)
        cursor -= c.px(10) + field_h
        self.email.draw(c, x + pad, cursor, inner_w, field_h)
        for field in self.fields:
            self.rows.append((field.rect, lambda field=field: self._focus(field)))

        cursor -= c.px(32)
        size = self.checkbox(c, x + pad, cursor - c.px(4), f.accept_terms, lambda: self._toggle("accept_terms"), enabled=not checking)
        self.rich_text(c, tr("I accept the [Human Generator Asset License] and the [Privacy policy]"), x + pad + size + c.px(12), cursor, 13, p.text, [setup_state.LICENSE_URL, setup_state.PRIVACY_URL])
        cursor -= c.px(30)
        self.checkbox(c, x + pad, cursor - c.px(4), f.newsletter, lambda: self._toggle("newsletter"), enabled=not checking)
        c.text(tr("Let me know about updates and offers"), x + pad + size + c.px(12), cursor, 13, p.text)

        # Footer: error on the left, Back and Activate on the right
        bw, bh = c.px(150), c.px(40)
        foot_y = y + pad
        back_w = c.px(80)
        if st.online_blocked:
            self.online_notice(c, x + pad, foot_y + bh + c.px(12), inner_w)
        elif st.license_error:
            c.paragraph(tr(st.license_error), x + pad, foot_y + bh, 12.5, p.danger, inner_w - bw - back_w - c.px(30), leading=1.35)
        self.button(tr("Back"), x + w - pad - bw - c.px(10) - back_w, foot_y, back_w, bh, self._back, "ghost", enabled=not checking)
        label = tr("Checking your order…") if checking else tr("Activate")
        self.button(label, x + w - pad - bw, foot_y, bw, bh, self._activate, "primary", enabled=not checking)

    def _focus(self, field: TextField) -> None:
        for other in self.fields:
            other.focus(other is field)

    def _toggle(self, prop: str) -> None:
        setattr(props(), prop, not getattr(props(), prop))

    def _back(self) -> None:
        setup_state.state.back()
        self.controller.go(setup_state.state.screen)

    def _activate(self) -> None:
        f = props()
        setup_state.state.activate(f.order_guid, f.email, f.accept_terms, f.newsletter)

    def key(self, event) -> bool:
        if event.type == "TAB":
            focused = next((i for i, f in enumerate(self.fields) if f.focused), -1)
            step = -1 if event.shift else 1
            self._focus(self.fields[(focused + step) % len(self.fields)])
            return True
        if event.type in ("RET", "NUMPAD_ENTER"):
            self._activate()
            return True
        return any(field.key(event) for field in self.fields)


class PacksScreen(Screen):
    name = "packs"
    ROW = 50
    FOOTER = 104

    def __init__(self, controller, textures) -> None:
        super().__init__(controller, textures)
        self.offset = 0.0  # scroll, in pixels
        self._max_offset = 0.0
        self._thumb: Rect = (0, 0, 0, 0)
        self._track: Rect = (0, 0, 0, 0)
        self._drag: Optional[Tuple[float, float]] = None  # mouse y and offset at the press

    def card_size(self, c: Canvas) -> Tuple[float, float]:
        rows = max(len(setup_state.state.packs), 3)
        extra = 70 if setup_state.state.online_blocked else 0
        return c.px(760), c.px(36 + 72 + 58 + self.ROW * rows + self.FOOTER + extra)

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

    def layout(self, c: Canvas) -> None:
        st = setup_state.state
        p = c.palette
        x, y, w, h = self.rect
        pad = c.px(36)
        if st.update_mode:
            title = tr("Update Human Generator")
            subtitle = tr("Newer versions of your content packs are available. Your own content stays as it is.")
        elif st.mode == "trial":
            title = tr("Install Human Generator")
            subtitle = tr("The trial content is included. The rest of the library comes with the full version.")
        else:
            title = tr("Install Human Generator")
            subtitle = tr("Choose what to install. You can add packs later from the preferences.")
        cursor = self.header(c, title, subtitle)

        # Folder row
        row_h = c.px(44)
        cursor -= row_h
        c.rect(x + pad, cursor, w - 2 * pad, row_h, p.panel, c.px(8))
        folder_label = tr("Content folder")
        c.text(folder_label, x + pad + c.px(14), cursor + c.px(16), 12.5, p.muted)
        label_w = c.text_width(folder_label, 12.5)
        button_w = c.px(84)
        path_x = x + pad + c.px(14) + label_w + c.px(14)
        path_w = (x + w - pad) - button_w - c.px(10) - path_x - c.px(14)
        c.text(c.ellipsize(st.folder, 13, path_w), path_x, cursor + c.px(16), 13, p.text)
        self.button(tr("Change"), x + w - pad - button_w - c.px(6), cursor + c.px(7), button_w, row_h - c.px(14), self.controller.change_folder, "ghost")
        cursor -= c.px(14)

        # Pack rows, in a clipped, scrollable area between the folder and the footer
        row_h = c.px(self.ROW)
        list_top = cursor
        list_bottom = y + c.px(self.FOOTER)
        if st.online_blocked:
            list_bottom += self.online_notice(c, x + pad, list_bottom, w - 2 * pad) + c.px(12)
        area_h = list_top - list_bottom
        if not st.packs:
            self._track = self._thumb = (0, 0, 0, 0)
            self._max_offset = 0.0
            mid = list_bottom + area_h / 2
            if st.loading:
                c.text(tr("Loading the pack list…"), x + w / 2, mid, 13.5, p.muted, "CENTER")
            elif st.catalogue_phase == "failed":
                c.paragraph(tr("Could not load the pack list.") + " " + st.catalogue_error, x + w / 2, mid + c.px(30), 13, p.danger, w - 2 * pad - c.px(40), align="CENTER")
                bw2, bh2 = c.px(120), c.px(34)
                self.button(tr("Try again"), x + (w - bw2) / 2, mid - c.px(40), bw2, bh2, st.load_catalogue, "secondary")
            elif not st.online_blocked:
                c.text(tr("Nothing to install."), x + w / 2, mid, 13.5, p.muted, "CENTER")
            self._footer(c, st)
            return
        content_h = row_h * len(st.packs)
        self._max_offset = max(0.0, content_h - area_h)
        self.offset = max(0.0, min(self._max_offset, self.offset))
        cursor = list_top + self.offset
        c.clip(x + pad, list_bottom, w - 2 * pad, area_h)
        for pack in st.packs:
            cursor -= row_h
            if cursor + row_h < list_bottom or cursor > list_top:
                continue
            rect = (x + pad, cursor, w - 2 * pad, row_h - c.px(4))
            visible = (rect[0], max(rect[1], list_bottom), rect[2], min(rect[1] + rect[3], list_top) - max(rect[1], list_bottom))
            toggleable = pack.installable and not pack.required and pack.status != "up_to_date"
            hovered = toggleable and in_rect(visible, *self.mouse)
            c.rect(*rect, p.panel_hover if hovered else p.panel, c.px(8))
            text_x = x + pad + c.px(14)
            if pack.locked:
                self.lock_glyph(c, text_x + c.px(2), cursor + c.px(15), p.muted)
                name_color = p.muted
            elif pack.status == "up_to_date":
                c.text(CHECK_GLYPH, text_x + c.px(9), cursor + c.px(18), 14, p.success, "CENTER")
                name_color = p.muted
            else:
                cx, cy = x + pad + c.px(14), cursor + (row_h - c.px(4)) / 2 - c.px(9)
                self.checkbox(c, cx, cy, pack.selected, self._toggler(pack), enabled=False, soft=pack.required)
                name_color = p.text
                if toggleable:
                    self.rows.append((visible, self._toggler(pack)))
            text_x += c.px(32)
            c.text(tr(pack.name), text_x, cursor + c.px(26), 14, name_color)
            right = x + w - pad - c.px(14)
            tag = tr(pack.tag) if pack.tag else ""
            if pack.status in ("update_available", "update_required") and pack.installed_version:
                detail = tr("Installed {old} · update to {new}").format(old=".".join(str(n) for n in pack.installed_version), new=pack.version)
                if pack.size:
                    detail += " · " + format_bytes(pack.size)
            else:
                detail = tr(pack.blurb)
            if tag:
                tag_w = c.text_width(tag, 12) + c.px(16)
                tag_color = p.danger if pack.status == "update_required" else p.muted
                c.rect(right - tag_w, cursor + c.px(13), tag_w, c.px(22), p.faint, c.px(11))
                c.text(tag, right - tag_w / 2, cursor + c.px(19.5), 12, tag_color, "CENTER")
                detail_w = right - tag_w - c.px(12) - text_x
            else:
                detail_w = right - c.px(90) - text_x
            c.text(c.ellipsize(detail, 12, detail_w), text_x, cursor + c.px(10), 12, p.muted)
            if pack.installable and pack.status != "up_to_date" and not tag:
                c.text(format_bytes(pack.size) if pack.size else "", right, cursor + c.px(26), 13, p.text, "RIGHT")
                if pack.required:
                    c.text(tr("Required"), right, cursor + c.px(10), 11.5, p.muted, "RIGHT")
        c.unclip()
        if self._max_offset > 0:
            bar_w = c.px(8)
            self._track = (x + w - pad + c.px(6), list_bottom, bar_w, area_h)
            thumb_h = max(c.px(28), area_h * area_h / content_h)
            thumb_y = list_top - thumb_h - (area_h - thumb_h) * (self.offset / self._max_offset)
            self._thumb = (self._track[0], thumb_y, bar_w, thumb_h)
            grabbed = self._drag is not None or in_rect(self._thumb, *self.mouse)
            c.rect(*self._track, p.panel, bar_w / 2)
            c.rect(*self._thumb, p.muted if grabbed else p.faint, bar_w / 2)
        else:
            self._track = self._thumb = (0, 0, 0, 0)

        self._footer(c, st)

    def _footer(self, c: Canvas, st) -> None:
        p = c.palette
        x, y, w, h = self.rect
        pad = c.px(36)
        total = st.total_bytes
        free = free_space(st.folder)
        fits = free > total * 1.1
        foot_y = y + pad
        summary = pack_count(len(st.selected), format_bytes(total))
        space = tr("{free} free on this disk").format(free=format_bytes(free)) if fits else tr("Not enough space on this disk")
        bw, bh = c.px(150), c.px(40)
        back_w = c.px(80)
        back_x = x + w - pad - bw - c.px(10) - back_w
        text_w = back_x - c.px(16) - (x + pad)
        c.text(c.ellipsize(summary, 13.5, text_w), x + pad, foot_y + c.px(22), 13.5, p.text)
        c.text(c.ellipsize(space, 12, text_w), x + pad, foot_y + c.px(4), 12, p.muted if fits else p.danger)
        self.button(tr("Back"), back_x, foot_y, back_w, bh, self._back, "ghost")
        label = tr("Update") if st.update_mode else tr("Install")
        self.button(label, x + w - pad - bw, foot_y, bw, bh, self._install, "primary", enabled=fits and bool(st.selected) and not st.loading)

    def _toggler(self, pack):
        def toggle():
            pack.selected = not pack.selected
        return toggle

    def _back(self) -> None:
        setup_state.state.back()
        self.controller.go(setup_state.state.screen)

    def _install(self) -> None:
        setup_state.state.start()
        self.controller.go("slides")


class SlidesScreen(Screen):
    name = "slides"

    def __init__(self, controller, textures) -> None:
        super().__init__(controller, textures)
        self.index = 0
        self.changed_at = time.monotonic()
        self.bar_shown = 0.0

    @property
    def deck(self):
        return DECKS.get(setup_state.state.mode, DECKS["licensed"])

    def enter(self) -> None:
        self.changed_at = time.monotonic()

    def go_to(self, index: int) -> None:
        self.index = index % len(self.deck)
        self.changed_at = time.monotonic()

    def tick(self, now: float) -> None:
        if now - self.changed_at > SLIDE_SECONDS:
            self.go_to(self.index + 1)

    def key(self, event) -> bool:
        if event.type in ("RIGHT_ARROW", "RET", "SPACE"):
            self.go_to(self.index + 1)
            return True
        if event.type == "LEFT_ARROW":
            self.go_to(self.index - 1)
            return True
        return False

    def close_button(self, c: Canvas) -> None:
        """While the download runs the corner says what closing does."""
        if not setup_state.state.active:
            super().close_button(c)
            return
        x, y, w, h = self.rect
        label = tr("Continue in background") + "   " + CLOSE_GLYPH
        bw, bh = c.text_width(label, 13) + c.px(28), c.px(32)
        inset = c.px(12)
        self.button(label, x + w - inset - bw, y + h - inset - bh, bw, bh, self.controller.close, "secondary")

    def layout(self, c: Canvas) -> None:
        st = setup_state.state
        p = c.palette
        x, y, w, h = self.rect
        pad = c.px(32)
        bar_h = c.px(92)
        fade = ease_out((time.monotonic() - self.changed_at) / FADE_SECONDS)

        # Slide: image left, text right
        image_w = w * 0.46
        image_h = h - bar_h - pad
        image_x, image_y = x + pad * 0.5, y + bar_h + pad * 0.5
        image_name, title, body = self.deck[self.index % len(self.deck)]
        title, body = tr(title), tr(body)
        texture = self.textures.get(os.path.join(SLIDE_IMAGE_DIR, image_name))
        c.rect(image_x, image_y, image_w, image_h, p.panel, c.px(14))
        if texture:
            c.image(texture, image_x, image_y, image_w, image_h, c.px(14), alpha=fade)

        text_x = image_x + image_w + pad
        text_w = x + w - pad - text_x
        top = y + h - pad - c.px(56)
        c.alpha = fade
        c.text(f"{self.index + 1} / {len(self.deck)}", text_x, top + c.px(26), 12, p.muted)
        used = c.paragraph(title, text_x, top + c.px(24), 24, p.text, text_w, leading=1.2)
        c.paragraph(body, text_x, top + c.px(24) - used - c.px(16), 15, p.muted, text_w, leading=1.5)
        c.alpha = 1.0

        # Dots and arrows
        dots_y = y + bar_h + pad * 0.5 + c.px(16)
        dot = c.px(7)
        dx = text_x
        for i in range(len(self.deck)):
            c.rect(dx, dots_y, dot, dot, p.accent if i == self.index else p.faint, dot / 2)
            dx += dot * 2.2
        arrow = c.px(34)
        self.button("‹", x + w - pad - arrow * 2 - c.px(8), dots_y - c.px(13), arrow, arrow, lambda: self.go_to(self.index - 1), "ghost", size=16)
        self.button("›", x + w - pad - arrow, dots_y - c.px(13), arrow, arrow, lambda: self.go_to(self.index + 1), "ghost", size=16)

        # Progress strip
        strip_y = y
        radius = c.px(16)
        c.rect(x, strip_y, w, bar_h, p.panel, radius)
        c.rect(x, strip_y + bar_h - radius, w, radius, p.panel, 0)  # square top corners
        inner_x = x + pad
        bw, bh = c.px(150), c.px(38)
        cancel_w = c.px(96)
        inner_w = w - 2 * pad - (cancel_w if st.active else bw) - c.px(20)
        if st.active:
            pack = st.current
            template = tr("Installing {pack}") if st.phase == "installing" else tr("Downloading {pack}")
            label = template.format(pack=tr(pack.name) if pack else "")
            detail = tr("{done} of {total} · pack {index} of {count}").format(done=format_bytes(st.done_bytes), total=format_bytes(st.total_bytes), index=min(st.packs_done + 1, len(st.selected)), count=len(st.selected))
            fraction = st.fraction
            color = None
        elif st.phase == "done":
            label, detail, fraction, color = tr("All packs installed"), tr("Ready to use"), 1.0, p.success
        elif st.phase == "failed":
            label, detail, fraction, color = tr("Download failed"), st.error, st.fraction, p.danger
        else:
            label, detail, fraction, color = tr("Cancelled"), "", st.fraction, p.muted
        self.bar_shown = lerp(self.bar_shown, fraction, 0.15)
        c.text(label, inner_x, strip_y + c.px(56), 13.5, p.text)
        c.text(c.ellipsize(detail, 12, inner_w - c.px(60)), inner_x, strip_y + c.px(38), 12, p.muted)
        c.text(f"{self.bar_shown:.0%}", inner_x + inner_w, strip_y + c.px(56), 13.5, p.text, "RIGHT")
        self.draw_progress_bar(c, inner_x, strip_y + c.px(22), inner_w, self.bar_shown, color)
        if st.active:
            self.button(tr("Cancel"), x + w - pad - cancel_w, strip_y + (bar_h - bh) / 2, cancel_w, bh, self._cancel, "ghost")
        else:
            self.button(tr("Continue"), x + w - pad - bw, strip_y + (bar_h - bh) / 2, bw, bh, lambda: self.controller.go("done"), "primary")

    def _cancel(self) -> None:
        """Stop and forget the download; the pack choice comes back."""
        setup_state.state.abort()
        self.bar_shown = 0.0
        self.controller.go("packs")


class DoneScreen(Screen):
    name = "done"

    def card_size(self, c: Canvas) -> Tuple[float, float]:
        return c.px(560), c.px(400)

    def layout(self, c: Canvas) -> None:
        st = setup_state.state
        p = c.palette
        x, y, w, h = self.rect
        cx = x + w / 2
        failed = st.phase == "failed"
        circle = c.px(64)
        cy = y + h - c.px(60) - circle
        c.rect(cx - circle / 2, cy, circle, circle, p.danger if failed else p.success, circle / 2)
        c.text("!" if failed else CHECK_GLYPH, cx, cy + c.px(20), 30, p.on_accent, "CENTER")
        title = tr("Download failed") if failed else (tr("Content updated") if st.update_mode else tr("Human Generator is ready"))
        c.text(title, cx, cy - c.px(40), 24, p.text, "CENTER")
        if failed:
            body = st.error + "\n" + tr("Your progress is kept. Retry when you are back online.")
        elif st.update_mode:
            body = tr("{packs} updated in").format(packs=pack_count(len(st.selected), format_bytes(st.total_bytes))) + "\n" + st.folder
        else:
            body = tr("{packs}, installed in").format(packs=pack_count(len(st.selected), format_bytes(st.total_bytes))) + "\n" + st.folder
        c.paragraph(body, cx, cy - c.px(60), 13.5, p.muted, w - c.px(100), align="CENTER")
        bw, bh = c.px(220), c.px(42)
        by = y + c.px(40)
        if failed:
            self.button(tr("Retry"), cx - bw / 2, by, bw, bh, self._retry, "primary")
        else:
            self.button(tr("Create your first human"), cx - bw - c.px(6), by, bw, bh, self.controller.create_human, "primary")
            self.button(tr("Show me around"), cx + c.px(6), by, bw, bh, self._tour, "secondary")

    def _retry(self) -> None:
        setup_state.state.start()
        self.controller.go("slides")

    def _tour(self) -> None:
        self.controller.go("slides")


SCREENS = {cls.name: cls for cls in (WelcomeScreen, ChooseScreen, LicenseScreen, PacksScreen, SlidesScreen, DoneScreen)}
