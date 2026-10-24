# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The modal operator that shows the setup overlay, the operators of the
sidebar fallback, and the sidebar panel.

The overlay operator owns a draw handler on the 3D viewport it was started in
and swallows input while it runs. Closing it leaves the download running; the
state's poll reopens it when the download ends. Only one can be open. The
panel offers the same steps as plain Blender widgets, for when the overlay
does not show (no 3D viewport, another modal operator, a GPU problem, a
viewport too small for the card).

The draw handler removes itself when its operator is gone (a file load can
end the operator without a cancel), and a `load_pre` handler, added when the
overlay operator class is registered, closes everything that belongs to it.
"""
import textwrap
import time
from typing import List, Optional

import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, StringProperty

from ...backend.setup import migration, online, repository, update_check, user_settings
from ...backend.setup.catalogue import has_humans, installed_packs, is_trial_install
from ...common.i18n import tr
from . import state as setup_state
from .draw import Canvas, TextureCache, ease_out
from .screens import (
    CARD_H,
    CARD_RADIUS,
    CARD_W,
    SCREENS,
    Controller,
    TooSmallScreen,
    can_open_sidebar_tab,
    download_detail,
    download_label,
    license_copy,
    notice_text,
    pack_count,
    packs_copy,
    props,
    space_text,
    update_label,
)
from .state import error_text

OPEN_SECONDS = 0.28
WHEEL_STEP = 60  # pixels per wheel click
MARGIN = 24  # design units between the card and the viewport edge
# Below this the card is not scaled down further; the sidebar takes over
MIN_FIT = 0.55
MIN_EFFECTIVE_SCALE = 0.72
# Grey hint text in a text field (`UILayout.prop(placeholder=...)`), not in every 4.2 build
PLACEHOLDERS = "placeholder" in bpy.types.UILayout.bl_rna.functions["prop"].parameters

# The running operator, for the sidebar panel and the screenshot harness
active: Optional["HG_OT_setup_overlay"] = None
handlers = 0  # draw handlers alive, for the harness


class HG_SETUP_PROPS(bpy.types.PropertyGroup):
    """The licence form. Lives on the window manager, so the overlay and the
    sidebar panel edit the same values and nothing is saved in the .blend."""

    order_guid: StringProperty(name="License key", description="Your license key. Bought on Superhive? Use the order GUID from your order email, not the order number")  # noqa: F821
    email: StringProperty(name="Email", description="The email you bought with")  # noqa: F821
    accept_terms: BoolProperty(name="I accept the Human Generator Asset License and the Privacy policy", default=False)  # noqa: F821
    newsletter: BoolProperty(name="Let me know about updates and offers", default=False)  # noqa: F821


def window_region(area) -> Optional[bpy.types.Region]:
    return next((r for r in area.regions if r.type == "WINDOW"), None)


def tab_name() -> str:
    try:
        from ...backend.preferences.preference_func import get_prefs

        return get_prefs().tab_name or "HumGen"
    except Exception:  # noqa: BLE001
        return "HumGen"


def open_sidebar_tab(area) -> None:
    """Show the sidebar of a 3D viewport, on the HumGen tab where Blender allows it."""
    try:
        area.spaces.active.show_region_ui = True
    except (AttributeError, ReferenceError):
        return
    if not can_open_sidebar_tab():
        return
    for region in area.regions:
        if region.type == "UI":
            try:
                region.active_panel_category = tab_name()
            except (AttributeError, TypeError, ValueError):
                pass


class _DrawHook:
    """The overlay's draw callback. Holds the operator, and removes itself
    when the operator was freed without closing (a file load, for one)."""

    def __init__(self, op: "HG_OT_setup_overlay") -> None:
        self.op = op
        self.handle = None
        self.callback = lambda: self()  # draw_handler_add wants a function
        self.timer = None
        self.window_manager = None

    def __call__(self) -> None:
        try:
            self.op._draw()
        except ReferenceError:
            self.remove()

    def remove(self) -> None:
        global handlers
        if self.handle is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(self.handle, "WINDOW")
            except (ValueError, RuntimeError):
                pass
            self.handle = None
            handlers = max(0, handlers - 1)
        if self.timer is not None:
            try:
                self.window_manager.event_timer_remove(self.timer)
            except (ReferenceError, ValueError, RuntimeError, AttributeError):
                pass
            self.timer = None
        if self in _hooks:
            _hooks.remove(self)


_hooks: List[_DrawHook] = []


def close_overlay() -> None:
    """Drop whatever the overlay left behind, without needing its operator."""
    global active
    for hook in list(_hooks):
        hook.remove()
    setup_state.state.overlay_open = False
    active = None


@persistent
def on_load_pre(*_args) -> None:
    """A file is about to load: the overlay's operator won't survive it."""
    st = setup_state.state
    if st.overlay_open and st.active:
        st.reopen_when_done = True
    close_overlay()


def shutdown() -> None:
    """The add-on is switched off: overlay, poll timer and download thread stop."""
    close_overlay()
    setup_state.stop_poll()
    setup_state.state.shutdown()


class HG_OT_setup_overlay(bpy.types.Operator, Controller):
    """Show the Human Generator setup"""

    bl_idname = "hg3d.setup_overlay"
    bl_label = "Human Generator setup"
    bl_options = {"INTERNAL"}

    screen: StringProperty(default="")  # noqa: F821  start screen, "" takes the state's

    @classmethod
    def register(cls) -> None:
        if on_load_pre not in bpy.app.handlers.load_pre:
            bpy.app.handlers.load_pre.append(on_load_pre)

    @classmethod
    def unregister(cls) -> None:
        if on_load_pre in bpy.app.handlers.load_pre:
            bpy.app.handlers.load_pre.remove(on_load_pre)
        shutdown()

    def invoke(self, context, event):
        global active, handlers
        area = context.area
        region = window_region(area) if area is not None and area.type == "VIEW_3D" else None
        if region is None:
            self.report({"WARNING"}, "The setup opens in a 3D viewport")
            return {"CANCELLED"}
        if setup_state.state.overlay_open:
            if _hooks:
                return {"CANCELLED"}
            setup_state.state.overlay_open = False  # left open by an operator that is gone
        self._region_ptr = region.as_pointer()
        self._area_ptr = area.as_pointer()
        self._textures = TextureCache()
        self._screens = {name: cls(self, self._textures) for name, cls in SCREENS.items()}
        self._too_small = TooSmallScreen(self, self._textures)
        self._small = False
        if self.screen:
            setup_state.state.screen = self.screen
        self._screen = self._screens[self._screen_for_state()]
        self._screen.enter()
        self._opened_at = time.monotonic()
        self._pressed = False
        self._closing = False
        self._after_close = None
        self.ticks = 0  # timer events seen, for the harness
        self.draws = 0
        hook = _DrawHook(self)
        hook.handle = bpy.types.SpaceView3D.draw_handler_add(hook.callback, (), "WINDOW", "POST_PIXEL")
        hook.window_manager = context.window_manager
        hook.timer = context.window_manager.event_timer_add(1 / 60, window=context.window)
        self._hook = hook
        _hooks.append(hook)
        handlers += 1
        context.window_manager.modal_handler_add(self)
        setup_state.state.overlay_open = True
        setup_state.state.ready_unseen = False
        active = self
        area.tag_redraw()
        return {"RUNNING_MODAL"}

    @staticmethod
    def _screen_for_state() -> str:
        st = setup_state.state
        if st.active:
            st.screen = "slides"
        elif st.phase in ("done", "failed"):
            st.screen = "done"
        elif st.paused and st.screen not in ("packs", "slides"):
            st.screen = "slides"
        if st.screen not in SCREENS:
            st.screen = "welcome"
        return st.screen

    @property
    def _current(self):
        return self._too_small if self._small else self._screen

    # Controller

    def go(self, screen: str) -> None:
        setup_state.state.screen = screen
        self._follow_state()

    def _follow_state(self) -> None:
        st = setup_state.state
        name = st.screen
        if name != self._screen.name and name in self._screens:
            self._screen = self._screens[name]
            self._screen.enter()
        elif name == "license" and st.prefill_due:
            self._screen.enter()

    def close(self) -> None:
        if setup_state.state.active:
            setup_state.state.reopen_when_done = True
        self._closing = True

    def change_folder(self) -> None:
        self._after_close = lambda: bpy.ops.hg3d.setup_folder("INVOKE_DEFAULT", reopen=True)
        self._closing = True

    def create_human(self) -> None:
        area_ptr = self._area_ptr

        def show_tab() -> None:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.as_pointer() == area_ptr:
                        open_sidebar_tab(area)

        self._after_close = show_tab
        self._closing = True

    def open_url(self, url: str) -> None:
        if url:
            bpy.ops.wm.url_open(url=url)

    def use_folder(self, folder: str) -> None:
        if setup_state.state.adopt_folder(folder):
            self.go("done")
        else:
            self.report({"WARNING"}, tr("No Human Generator content in this folder."))

    def select_existing_folder(self) -> None:
        self._after_close = lambda: bpy.ops.hg3d.setup_use_folder("INVOKE_DEFAULT", reopen=True)
        self._closing = True

    def open_upgrade(self) -> None:
        bpy.ops.hg3d.setup_open_upgrade()

    def to_sidebar(self) -> None:
        area_ptr = self._area_ptr
        setup_state.state.fallback_open = True

        def show_panel() -> None:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.as_pointer() == area_ptr:
                        open_sidebar_tab(area)

        self._after_close = show_panel
        self._closing = True

    # Modal

    def modal(self, context, event):
        if self._closing or not self._area_alive(context):
            self._finish(context)
            if self._after_close is not None:
                try:
                    self._after_close()
                except Exception as e:  # noqa: BLE001
                    self.report({"ERROR"}, str(e))
            return {"FINISHED"}
        screen = self._current
        if event.type == "TIMER":
            self.ticks += 1
            self._follow_state()
            self._current.tick(time.monotonic())
            self._redraw(context)
            return {"RUNNING_MODAL"}
        x, y = self._mouse(context, event)
        if event.type == "MOUSEMOVE":
            if self._pressed and screen.drag(x, y):
                self._redraw(context)
            elif screen.hover(x, y):
                self._redraw(context)
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE":
            if event.value == "PRESS":
                self._pressed = True
                screen.hover(x, y)
                screen.press(x, y)
            elif event.value == "RELEASE":
                self._pressed = False
                screen.release(x, y)
            self._redraw(context)
            return {"RUNNING_MODAL"}
        if event.type in ("WHEELUPMOUSE", "WHEELDOWNMOUSE") and event.value == "PRESS":
            if screen.scroll(-WHEEL_STEP if event.type == "WHEELUPMOUSE" else WHEEL_STEP):
                self._redraw(context)
            return {"RUNNING_MODAL"}
        if event.type == "TRACKPADPAN":
            # The pan delta comes as the move since the previous event
            if screen.scroll(event.mouse_prev_y - event.mouse_y):
                self._redraw(context)
            return {"RUNNING_MODAL"}
        if event.type == "ESC" and event.value == "PRESS":
            self.close()
            return {"RUNNING_MODAL"}
        if event.value == "PRESS" and event.type not in ("LEFTMOUSE", "MIDDLEMOUSE", "RIGHTMOUSE") and screen.key(event):
            self._redraw(context)
        return {"RUNNING_MODAL"}

    def cancel(self, context) -> None:
        """Blender ends the operator (a file load, the window closing)."""
        self._finish(context)

    def _mouse(self, context, event):
        """Mouse position relative to the viewport's main region, whatever
        region the operator was started from."""
        for area in context.screen.areas:
            if area.as_pointer() == self._area_ptr:
                for region in area.regions:
                    if region.as_pointer() == self._region_ptr:
                        return event.mouse_x - region.x, event.mouse_y - region.y
        return -1, -1

    def _area_alive(self, context) -> bool:
        return context.screen is not None and any(area.as_pointer() == self._area_ptr for area in context.screen.areas)

    def _redraw(self, context) -> None:
        for area in context.screen.areas:
            if area.as_pointer() == self._area_ptr:
                area.tag_redraw()

    def _finish(self, context) -> None:
        global active
        hook = getattr(self, "_hook", None)
        if hook is not None:
            hook.remove()
        try:
            self._textures.release()
        except Exception:  # noqa: BLE001
            pass
        setup_state.state.overlay_open = False
        active = None
        try:
            setup_state.redraw_viewports()
        except Exception:  # noqa: BLE001
            pass

    # Drawing

    @staticmethod
    def _insets(context) -> tuple:
        """Pixels at the left, right, top and bottom of the viewport that
        regions drawn over it (region overlap: toolbar, sidebar, tool
        header) cover, so the card stays clear of them."""
        win = context.region
        left = right = top = bottom = 0
        for region in context.area.regions if context.area is not None else ():
            if region.type == "WINDOW" or region.width <= 1 or region.height <= 1:
                continue
            inside_x = region.x >= win.x and region.x + region.width <= win.x + win.width
            inside_y = region.y >= win.y and region.y + region.height <= win.y + win.height
            if not (inside_x and inside_y):
                continue  # beside the viewport, not over it
            if region.type in ("TOOLS", "UI", "HUD", "TOOL_PROPS"):
                if region.x + region.width / 2 < win.x + win.width / 2:
                    left = max(left, region.x + region.width - win.x)
                else:
                    right = max(right, win.x + win.width - region.x)
            elif region.y + region.height / 2 > win.y + win.height / 2:
                top = max(top, win.y + win.height - region.y)
            else:
                bottom = max(bottom, region.y + region.height - win.y)
        return left, right, top, bottom

    def _draw(self) -> None:
        context = bpy.context
        if context.region is None or context.region.as_pointer() != self._region_ptr:
            return
        import gpu

        self.draws += 1
        # The viewport leaves its depth test on: without this the scene shows
        # through the card wherever geometry is in front of the far plane
        gpu.state.depth_test_set("NONE")
        gpu.state.depth_mask_set(False)
        gpu.state.face_culling_set("NONE")
        gpu.state.blend_set("ALPHA")
        opening = ease_out((time.monotonic() - self._opened_at) / OPEN_SECONDS)
        ui_scale = context.preferences.system.ui_scale
        left, right, top, bottom = self._insets(context)
        width = context.region.width - left - right
        height = context.region.height - top - bottom
        # Scale the card down to fit the viewport; below a readable size the
        # sidebar takes over
        fit = min(1.0, width / ((CARD_W + 2 * MARGIN) * ui_scale), height / ((CARD_H + 2 * MARGIN) * ui_scale))
        self._small = fit < MIN_FIT or fit * ui_scale < MIN_EFFECTIVE_SCALE
        screen = self._current
        if self._small:
            # The short notice that sends the user to the sidebar fits any viewport
            small = self._too_small
            fit = min(1.0, width / ((small.W + 2 * MARGIN) * ui_scale), height / ((small.H + 2 * MARGIN) * ui_scale))
        c = Canvas(context, alpha=opening, fit=fit)
        p = c.palette
        c.rect(0, 0, c.width, c.height, p.backdrop)
        w, h = screen.card_size(c)
        margin = c.px(MARGIN)
        w = min(w, width - 2 * margin)
        h = min(h, height - 2 * margin)
        x = left + (width - w) / 2
        y = bottom + (height - h) / 2 - c.px(10) * (1 - opening)
        x, y = round(x), round(y)
        radius = c.px(CARD_RADIUS)
        c.shadow(x, y, w, h, radius, c.px(24), p.shadow, offset_y=-c.px(8))
        c.outline(x, y, w, h, p.line, radius, max(1.0, round(c.scale)), p.card)
        screen.draw(c, (x, y, w, h))
        gpu.state.blend_set("NONE")
        gpu.state.depth_mask_set(True)
        gpu.state.depth_test_set("LESS_EQUAL")


def open_overlay_or_fallback(context) -> None:
    st = setup_state.state
    if context.area is not None and context.area.type == "VIEW_3D" and not st.overlay_open:
        region = window_region(context.area)
        with context.temp_override(area=context.area, region=region):
            result = bpy.ops.hg3d.setup_overlay("INVOKE_DEFAULT")
        if "RUNNING_MODAL" not in result:
            st.fallback_open = True
    elif not st.overlay_open:
        setup_state.reopen_overlay_soon()


def current_folder() -> str:
    """The folder a setup starts in: the add-on's, unless its drive is gone,
    in which case a new download goes to the default folder."""
    folder = update_check.content_folder() or user_settings.content_folder() or ""
    if folder and migration.content_state(folder) != "unreachable":
        return folder
    return migration.default_folder()


def prefill(context) -> None:
    """Fill the licence form after a step that shows it. Operators only, never a draw."""
    st = setup_state.state
    if st.screen == "license":
        st.prefill_form(context.window_manager.hg_setup)


def _prefill_from_timer() -> None:
    try:
        prefill(bpy.context)
        setup_state.redraw_viewports()
    except Exception:  # noqa: BLE001
        pass
    return None


def maybe_auto_open() -> None:
    """Open the setup once on a fresh install: not in background mode, not
    when content is installed or the content folder's drive is missing, and
    never again after it was shown. Safe to call from a timer."""
    _auto_open(attempt=0)


def _auto_open(attempt: int) -> Optional[float]:
    try:
        if bpy.app.background or user_settings.setup_shown():
            return None
        folder = update_check.content_folder() or user_settings.content_folder() or ""
        if folder and migration.content_state(folder) == "unreachable":
            return None
        if folder and has_humans(installed_packs(folder)):
            return None
        st = setup_state.state
        if st.overlay_open or st.in_progress:
            return None
        st.begin_setup(current_folder())
        if setup_state.reopen_overlay():
            user_settings.mark_setup_shown()
            return None
    except Exception as e:  # noqa: BLE001
        print("HumGen: could not open the setup:", repr(e))
        return None
    # No 3D viewport yet (the window is still being set up): try again shortly
    if attempt < 5:
        bpy.app.timers.register(lambda: _auto_open(attempt + 1), first_interval=1.0)
    return None


# Operators of the sidebar fallback and the ways in. They change the shared
# state; an open overlay follows it on its next tick.


class HG_OT_setup_start(bpy.types.Operator):
    """Set up Human Generator: install the content, or add packs to an existing install"""

    bl_idname = "hg3d.setup_start"
    bl_label = "Set up Human Generator"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        setup_state.state.begin_setup(current_folder())
        prefill(context)
        open_overlay_or_fallback(context)
        return {"FINISHED"}


class HG_OT_setup_update(bpy.types.Operator):
    """Download the newer versions of your content packs"""

    bl_idname = "hg3d.setup_update"
    bl_label = "Update content"
    bl_options = {"INTERNAL"}

    keys: StringProperty(default="", options={"SKIP_SAVE"})  # noqa: F821  comma-separated pack keys to tick instead of the updates

    def execute(self, context):
        st = setup_state.state
        if st.active:
            return {"CANCELLED"}
        st.begin_update(current_folder(), keys=[k.strip() for k in self.keys.split(",") if k.strip()])
        open_overlay_or_fallback(context)
        return {"FINISHED"}


class HG_OT_setup_add_packs(bpy.types.Operator):
    """Add content packs to this install"""

    bl_idname = "hg3d.setup_add_packs"
    bl_label = "Add content packs"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        st = setup_state.state
        if st.active:
            return {"CANCELLED"}
        st.begin_add_packs(current_folder())
        open_overlay_or_fallback(context)
        return {"FINISHED"}


class HG_OT_setup_upgrade(bpy.types.Operator):
    """Activate the license you bought and install the full library"""

    bl_idname = "hg3d.setup_upgrade"
    bl_label = "I have a license"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        st = setup_state.state
        if st.active:
            return {"CANCELLED"}
        st.folder = current_folder()
        st.begin_upgrade()
        prefill(context)
        open_overlay_or_fallback(context)
        return {"FINISHED"}


class HG_OT_setup_change_licence(bpy.types.Operator):
    """Enter another license key on this computer"""

    bl_idname = "hg3d.setup_change_licence"
    bl_label = "Change…"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        st = setup_state.state
        if st.active:
            return {"CANCELLED"}
        st.folder = current_folder()
        st.begin_change_credential()
        prefill(context)
        open_overlay_or_fallback(context)
        return {"FINISHED"}


class HG_OT_setup_forget_licence(bpy.types.Operator):
    """Remove the license key from this computer. Installed content keeps working"""

    bl_idname = "hg3d.setup_forget_licence"
    bl_label = "Forget"
    bl_options = {"INTERNAL"}

    confirmed: BoolProperty(default=False, options={"SKIP_SAVE"})  # noqa: F821
    keep: BoolProperty(default=False, options={"SKIP_SAVE"})  # noqa: F821

    def execute(self, context):
        st = setup_state.state
        if self.keep:
            st.forget_pending = False
        elif not self.confirmed:
            st.forget_pending = True
        else:
            st.forget_credential()
            self.report({"INFO"}, tr("The license key is no longer stored on this computer. Installed content stays."))
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
        return {"FINISHED"}


def draw_forget_button(layout) -> None:
    """The "Forget" button with its in-panel confirmation, for the preferences."""
    if not setup_state.state.forget_pending:
        layout.operator("hg3d.setup_forget_licence", text=tr("Forget"))
        return
    col = layout.column(align=True)
    col.label(text=tr("Forget only removes it from this computer. Installed content stays."), icon="INFO")
    row = col.row(align=True)
    row.operator("hg3d.setup_forget_licence", text=tr("Forget")).confirmed = True
    row.operator("hg3d.setup_forget_licence", text=tr("Keep")).keep = True


def upgrade_url() -> str:
    cred = user_settings.credential()
    if cred is not None and cred.upgrade_url:
        return cred.upgrade_url
    for catalogue in (setup_state.state.catalogue, update_check.status.catalogue):
        if catalogue is not None and catalogue.upgrade_url:
            return catalogue.upgrade_url
    return setup_state.UPGRADE_URL


class HG_OT_setup_open_upgrade(bpy.types.Operator):
    """Upgrade your Personal license to a Commercial one"""

    bl_idname = "hg3d.setup_open_upgrade"
    bl_label = "Upgrade to Commercial"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        bpy.ops.wm.url_open(url=upgrade_url())
        return {"FINISHED"}


class HG_OT_setup_use_folder(bpy.types.Operator):
    """Use Human Generator content that is already on this computer, without downloading"""

    bl_idname = "hg3d.setup_use_folder"
    bl_label = "Use this folder"
    bl_options = {"INTERNAL"}

    directory: StringProperty(subtype="DIR_PATH")  # noqa: F821
    reopen: BoolProperty(default=False, options={"SKIP_SAVE"})  # noqa: F821  reopen the overlay afterwards

    def invoke(self, context, event):
        if self.directory:
            return self.execute(context)
        self.directory = setup_state.state.found_folder or setup_state.state.folder
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        st = setup_state.state
        ok = st.adopt_folder(self.directory)
        if not ok:
            self.report({"WARNING"}, tr("No Human Generator content in this folder."))
        if self.reopen:
            setup_state.reopen_overlay_soon()
        setup_state.redraw_viewports()
        return {"FINISHED"} if ok else {"CANCELLED"}

    def cancel(self, context):
        if self.reopen:
            setup_state.reopen_overlay_soon()


class HG_OT_setup_hide_updates(bpy.types.Operator):
    """Hide this content update until a newer one comes out. The preferences still list it"""

    bl_idname = "hg3d.setup_hide_updates"
    bl_label = "Hide"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        us = update_check.status
        us.skip(us.shown_updates + [s for s in us.required if not us.is_skipped(s)])
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
        return {"FINISHED"}


class HG_OT_setup_check_updates(bpy.types.Operator):
    """Ask humgen3d.com for the latest versions of the add-on and the content packs"""

    bl_idname = "hg3d.setup_check_updates"
    bl_label = "Check for updates"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        if not online.allowed():
            self.report({"WARNING"}, tr("Blender's online access is turned off."))
            return {"CANCELLED"}
        if not update_check.check_now():
            return {"CANCELLED"}
        return {"FINISHED"}


class HG_OT_setup_allow_online(bpy.types.Operator):
    """Turn on Blender's online access, which downloading needs"""

    bl_idname = "hg3d.setup_allow_online"
    bl_label = "Allow online access"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        if not online.allow():
            self.report({"WARNING"}, tr("Blender was started in offline mode. Start it normally to download content."))
            return {"CANCELLED"}
        setup_state.state.allow_online()
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_setup_reload_packs(bpy.types.Operator):
    """Load the pack list again"""

    bl_idname = "hg3d.setup_reload_packs"
    bl_label = "Try again"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        setup_state.state.load_catalogue()
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_add_extension_repo(bpy.types.Operator):
    """Add the Human Generator repository to Blender, so Blender's extension list delivers add-on updates"""

    bl_idname = "hg3d.add_extension_repo"
    bl_label = "Enable add-on updates"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        repo = repository.add_repo()
        if repo is None:
            self.report({"WARNING"}, tr("Could not add the repository. Add it in the preferences, under Get Extensions > Repositories."))
            return {"CANCELLED"}
        try:
            bpy.ops.wm.save_userpref()
        except Exception:  # noqa: BLE001
            pass
        self.report({"INFO"}, tr("Repository added. Install Human Generator from it to get updates through Blender."))
        return {"FINISHED"}


class HG_OT_setup_fallback(bpy.types.Operator):
    """Show the setup steps here in the panel"""

    bl_idname = "hg3d.setup_fallback"
    bl_label = "Set up in this panel"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        st = setup_state.state
        st.fallback_open = not st.fallback_open
        prefill(context)
        return {"FINISHED"}


class HG_OT_setup_choose(bpy.types.Operator):
    """Start with the free trial or activate a license"""

    bl_idname = "hg3d.setup_choose"
    bl_label = "Choose"
    bl_options = {"INTERNAL"}

    mode: StringProperty()  # noqa: F821

    def execute(self, context):
        setup_state.state.choose(self.mode)
        prefill(context)
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_setup_go(bpy.types.Operator):
    """Go to this step of the setup"""

    bl_idname = "hg3d.setup_go"
    bl_label = "Go"
    bl_options = {"INTERNAL"}

    screen: StringProperty()  # noqa: F821

    def execute(self, context):
        setup_state.state.go(self.screen)
        prefill(context)
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_setup_enter_order(bpy.types.Operator):
    """Correct the license key, or enter another one"""

    bl_idname = "hg3d.setup_enter_order"
    bl_label = "Enter license key"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        st = setup_state.state
        st.license_reason = "rejected"
        st.go("license")
        prefill(context)
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_setup_back(bpy.types.Operator):
    """Back to the previous step"""

    bl_idname = "hg3d.setup_back"
    bl_label = "Back"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        setup_state.state.back()
        prefill(context)
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_setup_activate(bpy.types.Operator):
    """Check the license key and unlock the full library"""

    bl_idname = "hg3d.setup_activate"
    bl_label = "Activate"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        f = props()
        if not setup_state.state.activate(f.order_guid, f.email, f.accept_terms, f.newsletter):
            self.report({"WARNING"}, tr(setup_state.state.license_error))
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_setup_toggle_pack(bpy.types.Operator):
    """Include or leave out this pack"""

    bl_idname = "hg3d.setup_toggle_pack"
    bl_label = "Toggle pack"
    bl_options = {"INTERNAL"}

    key: StringProperty()  # noqa: F821

    @classmethod
    def description(cls, context, properties):
        pack = next((p for p in setup_state.state.packs if p.key == properties.key), None)
        return tr(pack.blurb) if pack is not None and pack.blurb else tr("Include or leave out this pack")

    def execute(self, context):
        st = setup_state.state
        for pack in st.packs:
            if pack.key == self.key and not pack.required and pack.installable and pack.status != "up_to_date" and not st.in_progress:
                pack.selected = not pack.selected
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_setup_toggle_locked(bpy.types.Operator):
    """Show or hide the packs of the full version"""

    bl_idname = "hg3d.setup_toggle_locked"
    bl_label = "Full version packs"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        st = setup_state.state
        st.locked_open = not st.locked_open
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_setup_install(bpy.types.Operator):
    """Download and install the selected packs, or resume the download"""

    bl_idname = "hg3d.setup_install"
    bl_label = "Install"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        setup_state.state.start()
        prefill(context)
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_setup_pause(bpy.types.Operator):
    """Pause the download. What was fetched is kept, and Resume continues from there"""

    bl_idname = "hg3d.setup_pause"
    bl_label = "Pause"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        setup_state.state.pause()
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_setup_folder(bpy.types.Operator):
    """Choose the folder the content is installed in"""

    bl_idname = "hg3d.setup_folder"
    bl_label = "Choose content folder"
    bl_options = {"INTERNAL"}

    directory: StringProperty(subtype="DIR_PATH")  # noqa: F821
    reopen: BoolProperty(default=False)  # noqa: F821  reopen the overlay afterwards

    def invoke(self, context, event):
        self.directory = setup_state.state.folder
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        st = setup_state.state
        st.folder = self.directory
        st.build_packs()  # packs already in that folder count as installed
        if self.reopen:
            setup_state.reopen_overlay_soon()
        setup_state.redraw_viewports()
        return {"FINISHED"}

    def cancel(self, context):
        if self.reopen:
            setup_state.reopen_overlay_soon()


class HG_OT_setup_cancel(bpy.types.Operator):
    """Stop the download, throw away what was fetched and choose again"""

    bl_idname = "hg3d.setup_cancel"
    bl_label = "Discard download"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        setup_state.state.abort()
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_setup_dismiss(bpy.types.Operator):
    """Close the setup card in the sidebar"""

    bl_idname = "hg3d.setup_dismiss"
    bl_label = "Done"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        setup_state.state.dismiss()
        if context.area is not None:
            open_sidebar_tab(context.area)
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_setup_reset(bpy.types.Operator):
    """Back to the start of the setup"""

    bl_idname = "hg3d.setup_reset"
    bl_label = "Reset"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        setup_state.state.reset()
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_setup_fail(bpy.types.Operator):
    """Prototype: make the running fake download fail"""

    bl_idname = "hg3d.setup_fail"
    bl_label = "Simulate failure"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        setup_state.state.fail()
        return {"FINISHED"}


_installed_cache = {"key": ("", 0.0), "value": {}}


def _installed() -> dict:
    """The packs of the add-on's content folder, read at most every two seconds."""
    folder = update_check.content_folder()
    now = time.monotonic()
    key_folder, at = _installed_cache["key"]
    if key_folder != folder or now - at > 2.0:
        _installed_cache["value"] = installed_packs(folder)
        _installed_cache["key"] = (folder, now)
    return _installed_cache["value"]


def content_installed() -> bool:
    return has_humans(_installed())


def trial_installed() -> bool:
    return is_trial_install(_installed())


def dev_tools() -> bool:
    try:
        from ...backend.preferences.preference_func import get_prefs

        return bool(get_prefs().dev_tools)
    except Exception:  # noqa: BLE001
        return False


def wrapped(layout, context, text: str, icon: str = "NONE", alert: bool = False) -> None:
    """A paragraph as labels, wrapped to the panel width."""
    width = context.region.width if context.region is not None else 300
    chars = max(18, int(width / (6.2 * context.preferences.system.ui_scale)) - (4 if icon != "NONE" else 0))
    col = layout.column(align=True)
    col.alert = alert
    col.scale_y = 0.85
    for i, line in enumerate(textwrap.wrap(text, chars) or [""]):
        col.label(text=line, icon=icon if i == 0 else ("BLANK1" if icon != "NONE" else "NONE"))


class HG_PT_SETUP(bpy.types.Panel):
    """Sidebar card: the setup at a glance, the way back to the overlay, the
    update notice, the trial's way to the full version, and every step as
    plain widgets for when the overlay does not show."""

    bl_label = "Setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"
    bl_order = 0

    @classmethod
    def poll(cls, context):
        st = setup_state.state
        if st.prompted or st.phase != "idle":
            return True
        if not content_installed() or trial_installed():
            return True
        return bool(update_check.status.notice())

    def draw(self, context):
        st = setup_state.state
        layout = self.layout
        col = layout.column(align=True)
        if st.active:
            self.draw_download(col, st)
        elif st.paused:
            self.draw_paused(col, st)
        elif st.phase in ("done", "failed"):
            self.draw_finished(layout, context, st)
        elif not st.prompted:
            if content_installed():
                self.draw_notice(col, context)
                if trial_installed():
                    self.draw_trial_card(layout, st)
            else:
                col.label(text=tr("Not installed yet"))
                row = col.row(align=True)
                row.scale_y = 1.4
                row.operator("hg3d.setup_start", text=tr("Set up Human Generator"), icon="IMPORT")
        else:
            row = col.row(align=True)
            row.scale_y = 1.4
            row.operator("hg3d.setup_overlay", text=tr("Continue setup"), icon="WINDOW")
            col.operator("hg3d.setup_fallback", text=tr("Pop-up not showing? Set up in this panel"), icon="TRIA_DOWN" if st.fallback_open else "TRIA_RIGHT", emboss=False)
            if st.fallback_open:
                box = layout.box()
                draw = getattr(self, "draw_" + st.screen, None)
                if draw is not None:
                    draw(box, context, st)
        if dev_tools() and (st.phase != "idle" or st.prompted):
            layout.separator()
            layout.operator("hg3d.setup_reset", text=tr("Reset setup"), icon="LOOP_BACK")

    # The update notice, for installs that are up and running

    def draw_notice(self, col, context) -> None:
        us = update_check.status
        notice = us.notice()
        if notice == "required":
            if us.blocked_by_addon:
                wrapped(col, context, tr("A newer Human Generator is needed for the latest content."), icon="INFO")
            else:
                col.label(text=tr("Content update needed"), icon="INFO")
        elif notice == "addon":
            col.label(text=tr("Add-on update available"), icon="INFO")
        elif notice == "available":
            col.label(text=tr("Content update available"), icon="INFO")
        if notice and getattr(us, "message", ""):
            wrapped(col, context, tr(us.message))
        shown = us.shown_updates
        if shown and not us.blocked_by_addon:
            row = col.row(align=True)
            row.scale_y = 1.3
            row.operator("hg3d.setup_update", text=update_label(len(shown)), icon="IMPORT")
            row.operator("hg3d.setup_hide_updates", text=tr("Hide"))
        if notice == "addon" or us.blocked_by_addon:
            col.operator("hg3d.openpref", text=tr("How to update the add-on"), icon="PREFERENCES")

    def draw_trial_card(self, layout, st) -> None:
        box = layout.box()
        col = box.column(align=True)
        col.label(text=tr("Trial version"), icon="INFO")
        row = col.row(align=True)
        row.operator("wm.url_open", text=tr("Get the full version"), icon="URL").url = setup_state.buy_url(setup_state.trial_rid())
        row.operator("hg3d.setup_upgrade", text=tr("I have a license"))

    # The steps, as the overlay shows them

    def draw_online_notice(self, layout, st) -> None:
        if not st.online_blocked:
            return
        box = layout.box()
        if online.locked():
            box.label(text=tr("Blender was started in offline mode."), icon="INFO")
            return
        box.label(text=tr("Downloading needs online access."), icon="INFO")
        box.operator("hg3d.setup_allow_online", text=tr("Allow online access"), icon="URL")

    def draw_welcome(self, layout, context, st) -> None:
        col = layout.column(align=True)
        col.label(text=tr("Welcome to Human Generator"))
        wrapped(col, context, tr("Downloads 2–4 GB. You can keep working meanwhile."))
        col.separator()
        if st.rid:
            col.operator("hg3d.setup_choose", text=tr("Install the free trial"), icon="PLAY").mode = "trial"
            col.operator("hg3d.setup_choose", text=tr("I have a license"), icon="KEYINGSET").mode = "licensed"
        else:
            col.operator("hg3d.setup_go", text=tr("Get started"), icon="PLAY").screen = "choose"
        col.separator()
        if st.found_folder:
            col.label(text=tr("Found Human Generator content in"))
            col.label(text=st.found_folder)
            col.operator("hg3d.setup_use_folder", text=tr("Use this folder"), icon="CHECKMARK").directory = st.found_folder
        else:
            col.operator("hg3d.setup_use_folder", text=tr("I already have the content packs"), icon="FILE_FOLDER")

    def draw_choose(self, layout, context, st) -> None:
        col = layout.column(align=True)
        col.label(text=tr("How do you want to start?"))
        col.operator("hg3d.setup_choose", text=tr("Free trial"), icon="PLAY").mode = "trial"
        col.operator("hg3d.setup_choose", text=tr("Activate license"), icon="KEYINGSET").mode = "licensed"
        if st.can_go_back:
            layout.operator("hg3d.setup_back", text=tr("Back"), icon="BACK")

    def draw_license(self, layout, context, st) -> None:
        f = props()
        if st.prefill_due and not bpy.app.timers.is_registered(_prefill_from_timer):
            # Writing the form is not allowed while a panel draws
            bpy.app.timers.register(_prefill_from_timer, first_interval=0.0)
        title, subtitle = license_copy(st)
        layout.label(text=title)
        wrapped(layout, context, subtitle)
        col = layout.column()
        col.enabled = not st.checking
        col.label(text=tr("License key"))
        if PLACEHOLDERS:
            col.prop(f, "order_guid", text="", placeholder=tr("Bought on Superhive? Use the order GUID, not the order number"))
        else:
            col.prop(f, "order_guid", text="")
        col.label(text=tr("The email you bought with"))
        col.prop(f, "email", text="")
        row = col.row(align=True)
        row.operator("wm.url_open", text=tr("Where do I find this?"), icon="QUESTION").url = setup_state.ORDER_HELP_URL
        row.operator("wm.url_open", text=tr("Why is this needed?"), icon="QUESTION").url = setup_state.EMAIL_HELP_URL
        col.prop(f, "accept_terms")
        row = col.row(align=True)
        row.operator("wm.url_open", text=tr("Asset License"), icon="URL").url = setup_state.LICENSE_URL
        row.operator("wm.url_open", text=tr("Privacy policy"), icon="URL").url = setup_state.PRIVACY_URL
        col.prop(f, "newsletter")
        self.draw_online_notice(layout, st)
        if st.license_error:
            wrapped(layout, context, error_text(st.license_error, tr), icon="ERROR", alert=True)
            if st.license_phase == "failed" or st.license_reason == "rejected":
                layout.operator("wm.url_open", text=tr("Contact support"), icon="URL").url = setup_state.SUPPORT_URL
        row = layout.row(align=True)
        if st.can_go_back:
            row.operator("hg3d.setup_back", text=tr("Not now") if st.license_reason == "update" else "", icon="BACK")
        if st.checking:
            row.label(text=tr("Checking your license…"))
        else:
            row.operator("hg3d.setup_activate", text=tr("Activate"), icon="CHECKMARK")

    def draw_packs(self, layout, context, st) -> None:
        title, _ = packs_copy(st)
        layout.label(text=title)
        col = layout.column(align=True)
        col.label(text=tr("Content folder"))
        row = col.row(align=True)
        row.label(text=st.folder)
        sub = row.row(align=True)
        sub.enabled = not st.in_progress
        sub.operator("hg3d.setup_folder", text="", icon="FILE_FOLDER").reopen = False
        layout.separator(factor=0.5)
        self.draw_online_notice(layout, st)
        text, url = notice_text(st)
        if text and not st.online_blocked:
            box = layout.box()
            wrapped(box, context, text, icon="INFO")
            if url:
                box.operator("wm.url_open", text=tr("Learn more"), icon="URL").url = url
        if st.loading:
            layout.label(text=tr("Loading the pack list…"), icon="TIME")
        elif st.catalogue_phase == "failed":
            wrapped(layout, context, tr("Could not load the pack list.") + " " + tr(st.catalogue_error), icon="ERROR", alert=True)
            layout.operator("hg3d.setup_reload_packs", text=tr("Try again"), icon="FILE_REFRESH")
        col = layout.column(align=True)
        trial = st.mode == "trial"
        locked = [p for p in st.packs if p.locked] if trial else []
        for pack in st.packs:
            if trial and pack.locked:
                continue
            self.draw_pack_row(col, st, pack)
        if locked:
            row = col.row(align=True)
            row.operator("hg3d.setup_toggle_locked", text=tr("In the full version: {count} more packs").format(count=len(locked)), icon="DOWNARROW_HLT" if st.locked_open else "RIGHTARROW", emboss=False)
            if st.locked_open:
                for pack in locked:
                    self.draw_pack_row(col, st, pack)
        if st.trial_installed_here and not st.in_progress:
            layout.label(text=tr("Trial installed"), icon="CHECKMARK")
            row = layout.row(align=True)
            row.operator("wm.url_open", text=tr("Get the full version"), icon="URL").url = setup_state.buy_url(st.rid)
            row.operator("hg3d.setup_upgrade", text=tr("I have a license"))
            return
        if st.paused:
            layout.label(text=tr("Download paused"))
            row = layout.row(align=True)
            row.operator("hg3d.setup_cancel", text=tr("Discard download"), icon="TRASH")
            row.operator("hg3d.setup_install", text=tr("Resume"), icon="PLAY")
            return
        layout.label(text=pack_count(len(st.selected), setup_state.format_bytes(st.total_bytes)))
        space, warn = space_text(st)
        wrapped(layout, context, space, alert=warn)
        row = layout.row(align=True)
        if st.can_go_back:
            row.operator("hg3d.setup_back", text="", icon="BACK")
        sub = row.row(align=True)
        sub.enabled = st.can_install
        label = update_label(len(st.selected)) if st.update_mode else tr("Install")
        sub.operator("hg3d.setup_install", text=label, icon="IMPORT")

    @staticmethod
    def draw_pack_row(col, st, pack) -> None:
        row = col.row(align=True)
        if pack.locked:
            row.enabled = False
            row.label(text=tr(pack.name), icon="LOCKED")
            row.label(text=tr(pack.tag))
            return
        if pack.status == "up_to_date" or pack.state == "done":
            row.enabled = False
            row.label(text=tr(pack.name), icon="CHECKMARK")
            row.label(text=tr("Installed"))
            return
        sub = row.row(align=True)
        sub.enabled = not pack.required and not st.in_progress
        op = sub.operator("hg3d.setup_toggle_pack", text=tr(pack.name), icon="CHECKBOX_HLT" if pack.selected else "CHECKBOX_DEHLT", emboss=False)
        op.key = pack.key
        size = setup_state.format_bytes(pack.size)
        if pack.tag:
            row.label(text=tr(pack.tag))
        elif pack.required:
            row.label(text=tr("Required · {size}").format(size=size))
        else:
            row.label(text=size)

    def draw_slides(self, layout, context, st) -> None:
        layout.operator("hg3d.setup_go", text=tr("Back to the pack list"), icon="BACK").screen = "packs"

    def draw_download(self, col, st) -> None:
        col.progress(text=download_label(st), factor=st.fraction, type="BAR")
        col.label(text=download_detail(st), icon="BLANK1")
        row = col.row(align=True)
        row.operator("hg3d.setup_overlay", text=tr("Show details"), icon="WINDOW")
        if st.phase == "downloading":
            row.operator("hg3d.setup_pause", text="", icon="PAUSE")
        if isinstance(st.services, setup_state.FakeServices):
            col.operator("hg3d.setup_fail", text=tr("Simulate failure"), icon="ERROR")

    def draw_paused(self, col, st) -> None:
        col.progress(text=tr("Download paused"), factor=st.fraction, type="BAR")
        col.label(text=tr("{done} of {total}").format(done=setup_state.format_bytes(st.done_bytes), total=setup_state.format_bytes(st.total_bytes)), icon="BLANK1")
        row = col.row(align=True)
        row.scale_y = 1.2
        row.operator("hg3d.setup_install", text=tr("Resume"), icon="PLAY")
        row.operator("hg3d.setup_overlay", text="", icon="WINDOW")

    def draw_finished(self, layout, context, st) -> None:
        col = layout.column(align=True)
        if st.phase == "done":
            col.label(text=tr("Human Generator is ready"), icon="CHECKMARK")
            cred = st.credential
            if cred is not None and cred.status == "ok" and cred.is_personal:
                row = col.row(align=True)
                row.label(text=tr("Personal license"))
                row.operator("hg3d.setup_open_upgrade", text=tr("Upgrade to Commercial"), emboss=False)
            row = col.row(align=True)
            row.operator("hg3d.setup_dismiss", text=tr("Done"), icon="CHECKMARK")
            row.operator("hg3d.setup_overlay", text="", icon="WINDOW")
            return
        if st.credential_failed:
            col.label(text=tr("We couldn't confirm your license"), icon="ERROR")
            wrapped(col, context, error_text(st.error, tr), alert=True)
            col.separator()
            col.operator("hg3d.setup_enter_order", text=tr("Enter license key"), icon="KEYINGSET")
            row = col.row(align=True)
            row.operator("wm.url_open", text=tr("Contact support"), icon="URL").url = setup_state.SUPPORT_URL
            row.operator("hg3d.setup_install", text=tr("Retry"), icon="FILE_REFRESH")
            return
        col.label(text=tr("Download failed"), icon="ERROR")
        wrapped(col, context, error_text(st.error, tr), alert=True)
        row = col.row(align=True)
        row.operator("hg3d.setup_install", text=tr("Retry"), icon="FILE_REFRESH")
        row.operator("hg3d.setup_overlay", text="", icon="WINDOW")

