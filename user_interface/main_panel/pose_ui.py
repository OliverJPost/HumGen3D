# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import os

import addon_utils
import bpy

from HumGen3D.backend import get_prefs
from ..panel_functions import draw_paragraph

from ..ui_baseclasses import MainPanelPart, subpanel_draw


class HG_PT_POSE(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_POSE"
    phase_name = "pose"

    @subpanel_draw
    def draw(self, context):
        sett = self.sett
        col = self.layout.column()

        row_h = col.row(align=True)
        row_h.scale_y = 1.5
        row_h.prop(sett.ui, "pose_tab_switch", expand=True)

        if sett.ui.pose_tab_switch == "library":
            self._draw_pose_library(sett, col)
        elif sett.ui.pose_tab_switch == "animation":
            self._draw_animation_library(col)
        elif sett.ui.pose_tab_switch == "rigify":
            self._draw_rigify_subsection(col)

    def _draw_animation_library(self, layout):
        """Draws the animation library, the active animation and the NLA strips.

        Args:
            layout (UILayout): layout of pose section
        """
        if self.human.pose.rigify.is_rigify:
            row = layout.row(align=True)
            row.label(text="Rigify not supported", icon="ERROR")
            row.operator(
                "hg3d.showinfo", text="", icon="QUESTION"
            ).info = "rigify_library"
            return

        self.draw_content_selector(layout, pcoll_name="animation")
        layout.operator(
            "hg3d.import_mixamo", text="Import Mixamo Animation", icon="IMPORT"
        )

        animation = self.human.animation
        if animation.action:
            self._draw_active_animation(layout, animation)
        self._draw_nla_strips(layout, animation)

    def _draw_active_animation(self, layout, animation):
        """Draws the box with the active animation and its settings."""
        box = layout.box()
        col = box.column(align=True)
        col.label(text=_animation_label(animation.action), icon="ACTION")
        col.label(
            text=f"{animation.frame_count} frames"
            + (", looping" if animation.loop else "")
        )
        col.prop(self.sett, "animation_finger_curl", slider=True)
        row = col.row(align=True)
        row.operator("hg3d.animation_frame_range", icon="PREVIEW_RANGE")
        row.operator("hg3d.remove_animation", text="Remove", icon="X")

    def _draw_nla_strips(self, layout, animation):
        """Draws the collapsed subsection for chaining animations as NLA strips."""
        strips = animation.strips
        label = f"NLA Strips ({len(strips)})" if strips else "NLA Strips"
        is_open, box = self.draw_sub_spoiler(
            layout, self.sett.ui, "animation_nla", label
        )
        if not is_open:
            return

        row = box.row(align=True)
        row.label(text="Chain or layer animations")
        row.operator("hg3d.showinfo", text="", icon="QUESTION").info = "animation_nla"

        col = box.column(align=True)
        row = col.row(align=True)
        row.enabled = bool(animation.action)
        row.operator(
            "hg3d.animation_push_down", text="Push Down Active", icon="NLA_PUSHDOWN"
        )
        selected = self.sett.pcoll.animation
        has_selection = bool(selected) and selected != "none"
        row = col.row(align=True)
        row.enabled = has_selection
        text = (
            f"Add '{_preset_label(selected)}' as Strip"
            if has_selection
            else "Add Selected as Strip"
        )
        row.operator("hg3d.add_animation_strip", text=text, icon="NLA")

        if not strips:
            return
        col = box.column(align=True)
        for strip in strips:
            split = col.split(factor=0.7, align=True)
            split.label(text=_animation_label(strip.action), icon="NLA")
            split.label(text=f"{round(strip.frame_start)} - {round(strip.frame_end)}")
        row = box.row(align=True)
        if not animation.action:
            row.operator("hg3d.animation_frame_range", icon="PREVIEW_RANGE")
        op = row.operator("hg3d.remove_animation", text="Remove Strips", icon="X")
        op.active = False
        op.strips = True

    def _draw_rigify_subsection(self, box):
        """Draws ui for adding rigify, context info if added.

        Args:
            box (UILayout): layout.box of pose section
        """
        if "hg_rigify" in self.human.objects.rig.data:
            box.label(text="Rigify rig active")
            box.label(text="Use Rigify add-on to adjust", icon="INFO")
        elif addon_utils.check("rigify"):
            box.label(text="Load facial rig first", icon="INFO")
            is_trial = get_prefs().is_trial
            if is_trial:
                tbox = box.box()
                row = tbox.row(align=True)
                row.alert = True
                row.label(text="Disabled in Trial Version")
                tbox.operator("wm.url_open", text="Buy Human Generator", depress=True).url = (
                    "https://humgen3d.com/pricing"
                    "?utm_source=addon"
                    "&utm_medium=ui_link"
                    "&utm_campaign=trial_click"
                )
            col = box.column()
            col.enabled = not is_trial
            col.scale_y = 1.5
            col.operator("hg3d.rigify", depress=True)
        else:
            box.label(text="Rigify is not enabled")

    def _draw_pose_library(self, sett, layout):
        """Draws template_icon_view for selecting poses from the library.

        Args:
            sett (PropertyGroup): HumGen properties
            box (UILayout): layout.box of pose section
        """
        if "hg_rigify" in self.human.objects.rig.data:
            col = layout.column(align=True)

            row = col.row(align=True)
            row.label(text="Rigify not supported", icon="ERROR")
            row.operator(
                "hg3d.showinfo", text="", icon="QUESTION"
            ).info = "rigify_library"
            return

        self.draw_content_selector(layout)


def _preset_label(preset):
    """Readable name of an animation preset path, like the library shows it."""
    name = os.path.splitext(os.path.basename(preset))[0]
    return name.replace("HG_", "", 1).replace("_", " ")


def _animation_label(action):
    """Readable name of an action created by Human Generator."""
    preset = action.get("hg_animation")
    return _preset_label(preset) if preset else action.name
