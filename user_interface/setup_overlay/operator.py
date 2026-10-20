# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
"""The modal operator that shows the setup overlay, the operators of the
sidebar fallback, and the sidebar panel.

The overlay operator owns a draw handler on the 3D viewport it was started in
and swallows input while it runs. Closing it leaves the download running; the
state's poll reopens it when the download ends. Only one can be open. The
panel offers the same steps as plain Blender widgets, for when the overlay
does not show (no 3D viewport, another modal operator, a GPU problem).
"""
import time
from typing import Optional

import bpy
from bpy.props import BoolProperty, StringProperty

from ...backend.setup import online, repository, update_check
from ...backend.setup.catalogue import has_humans, installed_packs
from ...common.i18n import tr
from . import state as setup_state
from .draw import Canvas, TextureCache, ease_out
from .screens import CARD_RADIUS, SCREENS, Controller, pack_count, props

OPEN_SECONDS = 0.28
WHEEL_STEP = 60  # pixels per wheel click

# The running operator, for the sidebar panel and the screenshot harness
active: Optional["HG_OT_setup_overlay"] = None
handlers = 0  # draw handlers alive, for the harness


class HG_SETUP_PROPS(bpy.types.PropertyGroup):
    """The licence form. Lives on the window manager, so the overlay and the
    sidebar panel edit the same values and nothing is saved in the .blend."""

    order_guid: StringProperty(name="Order GUID", description="The GUID of your Superhive order, from the order email")  # noqa: F821
    email: StringProperty(name="Email", description="The email address of your Superhive account")  # noqa: F821
    accept_terms: BoolProperty(name="I accept the Human Generator Asset License and the Privacy policy", default=False)  # noqa: F821
    newsletter: BoolProperty(name="Let me know about updates and offers", default=False)  # noqa: F821


def window_region(area) -> Optional[bpy.types.Region]:
    return next((r for r in area.regions if r.type == "WINDOW"), None)


class HG_OT_setup_overlay(bpy.types.Operator, Controller):
    """Show the Human Generator setup"""

    bl_idname = "hg3d.setup_overlay"
    bl_label = "Human Generator setup"
    bl_options = {"INTERNAL"}

    screen: StringProperty(default="")  # noqa: F821  start screen, "" takes the state's

    def invoke(self, context, event):
        global active, handlers
        area = context.area
        region = window_region(area) if area is not None and area.type == "VIEW_3D" else None
        if region is None:
            self.report({"WARNING"}, "The setup opens in a 3D viewport")
            return {"CANCELLED"}
        if setup_state.state.overlay_open:
            return {"CANCELLED"}
        self._region_ptr = region.as_pointer()
        self._area_ptr = area.as_pointer()
        self._textures = TextureCache()
        self._screens = {name: cls(self, self._textures) for name, cls in SCREENS.items()}
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
        self._handle = bpy.types.SpaceView3D.draw_handler_add(self._draw, (), "WINDOW", "POST_PIXEL")
        handlers += 1
        self._timer = context.window_manager.event_timer_add(1 / 60, window=context.window)
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
        return st.screen

    # Controller

    def go(self, screen: str) -> None:
        setup_state.state.screen = screen
        self._follow_state()

    def _follow_state(self) -> None:
        name = setup_state.state.screen
        if name != self._screen.name and name in self._screens:
            self._screen = self._screens[name]
            self._screen.enter()

    def close(self) -> None:
        if setup_state.state.active:
            setup_state.state.reopen_when_done = True
        self._closing = True

    def change_folder(self) -> None:
        self._after_close = lambda: bpy.ops.hg3d.setup_folder("INVOKE_DEFAULT", reopen=True)
        self._closing = True

    def create_human(self) -> None:
        self._closing = True

    def open_url(self, url: str) -> None:
        bpy.ops.wm.url_open(url=url)

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
        if event.type == "TIMER":
            self.ticks += 1
            self._follow_state()
            self._screen.tick(time.monotonic())
            self._redraw(context)
            return {"RUNNING_MODAL"}
        x, y = self._mouse(context, event)
        if event.type == "MOUSEMOVE":
            if self._pressed and self._screen.drag(x, y):
                self._redraw(context)
            elif self._screen.hover(x, y):
                self._redraw(context)
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE":
            if event.value == "PRESS":
                self._pressed = True
                self._screen.hover(x, y)
                self._screen.press(x, y)
            elif event.value == "RELEASE":
                self._pressed = False
                self._screen.release(x, y)
            self._redraw(context)
            return {"RUNNING_MODAL"}
        if event.type in ("WHEELUPMOUSE", "WHEELDOWNMOUSE") and event.value == "PRESS":
            if self._screen.scroll(-WHEEL_STEP if event.type == "WHEELUPMOUSE" else WHEEL_STEP):
                self._redraw(context)
            return {"RUNNING_MODAL"}
        if event.type == "TRACKPADPAN":
            # The pan delta comes as the move since the previous event
            if self._screen.scroll(event.mouse_prev_y - event.mouse_y):
                self._redraw(context)
            return {"RUNNING_MODAL"}
        if event.type == "ESC" and event.value == "PRESS":
            self.close()
            return {"RUNNING_MODAL"}
        if event.value == "PRESS" and event.type not in ("LEFTMOUSE", "MIDDLEMOUSE", "RIGHTMOUSE") and self._screen.key(event):
            self._redraw(context)
        return {"RUNNING_MODAL"}

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
        return any(area.as_pointer() == self._area_ptr for area in context.screen.areas)

    def _redraw(self, context) -> None:
        for area in context.screen.areas:
            if area.as_pointer() == self._area_ptr:
                area.tag_redraw()

    def _finish(self, context) -> None:
        global active, handlers
        bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
        handlers -= 1
        context.window_manager.event_timer_remove(self._timer)
        self._textures.release()
        setup_state.state.overlay_open = False
        active = None
        setup_state.redraw_viewports()

    # Drawing

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
        c = Canvas(context, alpha=opening)
        p = c.palette
        c.rect(0, 0, c.width, c.height, p.backdrop)
        w, h = self._screen.card_size(c)
        margin = c.px(24)
        w = min(w, c.width - 2 * margin)
        h = min(h, c.height - 2 * margin)
        x = (c.width - w) / 2
        y = (c.height - h) / 2 - c.px(10) * (1 - opening)
        x, y = round(x), round(y)
        radius = c.px(CARD_RADIUS)
        c.shadow(x, y, w, h, radius, c.px(24), p.shadow, offset_y=-c.px(8))
        c.outline(x, y, w, h, p.line, radius, max(1.0, round(c.scale)), p.card)
        self._screen.draw(c, (x, y, w, h))
        gpu.state.blend_set("NONE")
        gpu.state.depth_mask_set(True)
        gpu.state.depth_test_set("LESS_EQUAL")


# Operators of the sidebar fallback. They change the shared state; an open
# overlay follows it on its next tick.


class HG_OT_setup_start(bpy.types.Operator):
    """Set up Human Generator: choose the trial or activate a licence, then download the content"""

    bl_idname = "hg3d.setup_start"
    bl_label = "Set up Human Generator"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        st = setup_state.state
        if not st.prompted:
            st.screen = "welcome"
            st.update_mode = False
        st.prompted = True
        open_overlay_or_fallback(context)
        return {"FINISHED"}


def open_overlay_or_fallback(context) -> None:
    st = setup_state.state
    if context.area is not None and context.area.type == "VIEW_3D" and not st.overlay_open:
        region = window_region(context.area)
        with context.temp_override(area=context.area, region=region):
            result = bpy.ops.hg3d.setup_overlay("INVOKE_DEFAULT")
        if "RUNNING_MODAL" not in result:
            st.fallback_open = True
    else:
        setup_state.reopen_overlay_soon()


class HG_OT_setup_update(bpy.types.Operator):
    """Download the newer versions of your content packs"""

    bl_idname = "hg3d.setup_update"
    bl_label = "Update content"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        st = setup_state.state
        if st.active:
            return {"CANCELLED"}
        st.folder = update_check.content_folder() or st.folder
        st.begin_update()
        open_overlay_or_fallback(context)
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
        setup_state.state.fallback_open = not setup_state.state.fallback_open
        return {"FINISHED"}


class HG_OT_setup_choose(bpy.types.Operator):
    """Start with the free trial or activate a licence"""

    bl_idname = "hg3d.setup_choose"
    bl_label = "Choose"
    bl_options = {"INTERNAL"}

    mode: StringProperty()  # noqa: F821

    def execute(self, context):
        setup_state.state.choose(self.mode)
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
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_setup_back(bpy.types.Operator):
    """Back to the previous step"""

    bl_idname = "hg3d.setup_back"
    bl_label = "Back"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        setup_state.state.back()
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_setup_activate(bpy.types.Operator):
    """Check the order and unlock the full library"""

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

    def execute(self, context):
        for pack in setup_state.state.packs:
            if pack.key == self.key and not pack.required and pack.installable and pack.status != "up_to_date":
                pack.selected = not pack.selected
        setup_state.redraw_viewports()
        return {"FINISHED"}


class HG_OT_setup_install(bpy.types.Operator):
    """Download and install the selected packs"""

    bl_idname = "hg3d.setup_install"
    bl_label = "Install"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        setup_state.state.start()
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
    bl_label = "Cancel download"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        setup_state.state.abort()
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


def content_installed() -> bool:
    return has_humans(installed_packs(update_check.content_folder()))


def dev_tools() -> bool:
    try:
        from ...backend.preferences.preference_func import get_prefs

        return bool(get_prefs().dev_tools)
    except Exception:  # noqa: BLE001
        return False


class HG_PT_SETUP(bpy.types.Panel):
    """Sidebar card: the setup at a glance, the way back to the overlay, the
    update notice, and every step as plain widgets for when the overlay does
    not show."""

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
        if not content_installed():
            return True
        return bool(update_check.status.notice())

    def draw(self, context):
        st = setup_state.state
        layout = self.layout
        col = layout.column(align=True)
        if st.active:
            self.draw_download(col, st)
        elif st.phase in ("done", "failed"):
            self.draw_finished(col, st)
        elif not st.prompted:
            if content_installed():
                self.draw_notice(col)
            else:
                col.label(text=tr("Not installed yet"))
                row = col.row(align=True)
                row.scale_y = 1.4
                row.operator("hg3d.setup_start", text=tr("Set up Human Generator"), icon="IMPORT")
        else:
            col.label(text=tr("Pop-up not showing?"))
            row = col.row(align=True)
            row.operator("hg3d.setup_fallback", text=tr("Set up in this panel"), icon="TRIA_DOWN" if st.fallback_open else "TRIA_RIGHT", depress=st.fallback_open)
            row.operator("hg3d.setup_start", text="", icon="WINDOW")
            if st.fallback_open:
                box = layout.box()
                draw = getattr(self, "draw_" + st.screen, None)
                if draw is not None:
                    draw(box, st)
        if dev_tools() and (st.phase != "idle" or st.prompted):
            layout.separator()
            layout.operator("hg3d.setup_reset", text=tr("Reset setup"), icon="LOOP_BACK")

    # The update notice, for installs that are up and running

    def draw_notice(self, col) -> None:
        us = update_check.status
        notice = us.notice()
        if notice == "required":
            alert = col.column(align=True)
            alert.alert = True
            if us.blocked_by_addon:
                alert.label(text=tr("Update the add-on first"), icon="ERROR")
            else:
                alert.label(text=tr("Content update needed"), icon="ERROR")
        elif notice == "addon":
            col.label(text=tr("Add-on update available"), icon="INFO")
        elif notice == "available":
            col.label(text=tr("Content update available"), icon="INFO")
        if us.updates and not us.blocked_by_addon:
            row = col.row(align=True)
            row.scale_y = 1.3
            row.operator("hg3d.setup_update", text=tr("Update ({count})").format(count=len(us.updates)), icon="IMPORT")
        if notice == "addon" or us.blocked_by_addon:
            col.operator("hg3d.openpref", text=tr("How to update the add-on"), icon="PREFERENCES")

    # The steps, as the overlay shows them

    def draw_welcome(self, layout, st) -> None:
        col = layout.column(align=True)
        col.label(text=tr("Welcome to Human Generator"))
        col.operator("hg3d.setup_go", text=tr("Get started"), icon="PLAY").screen = "choose"

    def draw_choose(self, layout, st) -> None:
        col = layout.column(align=True)
        col.label(text=tr("How do you want to start?"))
        col.operator("hg3d.setup_choose", text=tr("Free trial"), icon="PLAY").mode = "trial"
        col.operator("hg3d.setup_choose", text=tr("Activate licence"), icon="KEYINGSET").mode = "licensed"

    def draw_online_notice(self, layout, st) -> None:
        if not st.online_blocked:
            return
        box = layout.box()
        if online.locked():
            box.label(text=tr("Blender was started in offline mode."), icon="ERROR")
            return
        box.label(text=tr("Downloading needs online access."), icon="INFO")
        box.operator("hg3d.setup_allow_online", text=tr("Allow online access"), icon="URL")

    def draw_license(self, layout, st) -> None:
        f = props()
        st.prefill_form(f)
        col = layout.column()
        col.enabled = not st.checking
        col.prop(f, "order_guid")
        col.prop(f, "email")
        col.prop(f, "accept_terms")
        row = col.row(align=True)
        row.operator("wm.url_open", text=tr("Asset License"), icon="URL").url = setup_state.LICENSE_URL
        row.operator("wm.url_open", text=tr("Privacy policy"), icon="URL").url = setup_state.PRIVACY_URL
        col.prop(f, "newsletter")
        self.draw_online_notice(layout, st)
        if st.license_error:
            alert = layout.column()
            alert.alert = True
            alert.label(text=tr(st.license_error), icon="ERROR")
        row = layout.row(align=True)
        row.operator("hg3d.setup_back", text="", icon="BACK")
        if st.checking:
            row.label(text=tr("Checking your order…"))
        else:
            row.operator("hg3d.setup_activate", text=tr("Activate"), icon="CHECKMARK")

    def draw_packs(self, layout, st) -> None:
        col = layout.column(align=True)
        col.label(text=tr("Content folder"))
        row = col.row(align=True)
        row.label(text=st.folder)
        row.operator("hg3d.setup_folder", text="", icon="FILE_FOLDER").reopen = False
        layout.separator(factor=0.5)
        self.draw_online_notice(layout, st)
        if st.loading:
            layout.label(text=tr("Loading the pack list…"), icon="TIME")
        elif st.catalogue_phase == "failed":
            alert = layout.column()
            alert.alert = True
            alert.label(text=tr("Could not load the pack list."), icon="ERROR")
            layout.label(text=st.catalogue_error)
            layout.operator("hg3d.setup_reload_packs", text=tr("Try again"), icon="FILE_REFRESH")
        col = layout.column(align=True)
        for pack in st.packs:
            row = col.row(align=True)
            if pack.locked:
                row.enabled = False
                row.label(text=tr(pack.name), icon="LOCKED")
                row.label(text=tr(pack.tag))
                continue
            if pack.status == "up_to_date":
                row.enabled = False
                row.label(text=tr(pack.name), icon="CHECKMARK")
                row.label(text=tr(pack.tag))
                continue
            sub = row.row(align=True)
            sub.enabled = not pack.required
            op = sub.operator("hg3d.setup_toggle_pack", text=tr(pack.name), icon="CHECKBOX_HLT" if pack.selected else "CHECKBOX_DEHLT", emboss=False)
            op.key = pack.key
            row.label(text=tr(pack.tag) if pack.tag else setup_state.format_bytes(pack.size))
        layout.label(text=pack_count(len(st.selected), setup_state.format_bytes(st.total_bytes)))
        row = layout.row(align=True)
        row.operator("hg3d.setup_back", text="", icon="BACK")
        sub = row.row(align=True)
        sub.enabled = bool(st.selected) and not st.loading
        sub.operator("hg3d.setup_install", text=tr("Update") if st.update_mode else tr("Install"), icon="IMPORT")

    def draw_download(self, col, st) -> None:
        pack = tr(st.current.name) if st.current else ""
        template = tr("Installing {pack}") if st.phase == "installing" else tr("Downloading {pack}")
        col.progress(text=template.format(pack=pack), factor=st.fraction, type="BAR")
        col.label(text=tr("{done} of {total}").format(done=setup_state.format_bytes(st.done_bytes), total=setup_state.format_bytes(st.total_bytes)), icon="BLANK1")
        row = col.row(align=True)
        row.operator("hg3d.setup_overlay", text=tr("Show details"), icon="WINDOW")
        row.operator("hg3d.setup_cancel", text="", icon="X")
        if isinstance(st.services, setup_state.FakeServices):
            col.operator("hg3d.setup_fail", text=tr("Simulate failure"), icon="ERROR")

    def draw_finished(self, col, st) -> None:
        if st.phase == "done":
            col.label(text=tr("Ready"), icon="CHECKMARK")
            col.operator("hg3d.setup_overlay", text=tr("Open"), icon="WINDOW")
        else:
            alert = col.column()
            alert.alert = True
            alert.label(text=tr("Download failed"), icon="ERROR")
            row = col.row(align=True)
            row.operator("hg3d.setup_install", text=tr("Retry"), icon="FILE_REFRESH")
            row.operator("hg3d.setup_overlay", text="", icon="WINDOW")
