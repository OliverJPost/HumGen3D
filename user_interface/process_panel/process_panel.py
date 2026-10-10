# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

"""The Process tab: one recipe, one output, and the sections that refine it.

Nothing here is needed for a correct file, the recipe holds the knowledge
about the engine. The sections show and change what it decided.
"""

import os
from typing import Optional

import bpy
from HumGen3D.backend import get_prefs
from HumGen3D.backend.properties.process_props import (
    _resolution_from_props,
    is_modified,
    props_to_settings,
    quality_from_props,
)
from HumGen3D.common import find_multiple_in_list
from HumGen3D.common.documentation import draw_docs_button
from HumGen3D.human.human import Human
from HumGen3D.human.process.pipeline import output_folder, preflight
from HumGen3D.human.process.quality import (
    CUSTOM_TIER,
    TEXTURE_TIERS,
    estimate_triangles,
    quality_of_tier,
    texture_tier_of,
)
from HumGen3D.human.process.settings import (
    OUTPUT_FORMATS,
    TEXTURE_PASSES,
    TEXTURE_SETS,
)
from HumGen3D.human.process.shape_keys import KEY_GROUPS, driven_groups_kept
from HumGen3D.user_interface.icons.icons import get_hg_icon
from HumGen3D.user_interface.panel_functions import (
    draw_panel_switch_header,
    draw_paragraph,
)

from ..ui_baseclasses import HGPanel, draw_icon_title

LABELS = {ident: label for ident, label, *_ in OUTPUT_FORMATS}
PASS_LABELS = {
    "base_color": "Color",
    "normal": "Normal",
    "roughness": "Rough",
    "metallic": "Metal",
    "alpha": "Alpha",
}
SKELETON_LABELS = {
    "humanoid": "Humanoid",
    "unreal": "Unreal",
    "mixamo": "Mixamo",
    "humgen": "HG names",
    "custom": "Custom",
}
TIER_LABELS = {ident: label for ident, label, _ in TEXTURE_TIERS}
TIER_LABELS[CUSTOM_TIER[0]] = CUSTOM_TIER[1]


def _props(context):
    return context.scene.HG3D.process


def _human(context) -> Optional[Human]:
    return Human.from_existing(context.object, strict_check=False)


def _rounded(tris: int) -> str:
    rounded = round(tris, -3 if tris >= 10_000 else -2)
    return f"~{rounded:,} tris"


def _short(tris: int) -> str:
    """Triangles as a short figure for a narrow column, "4.1k", "70k" or "320"."""
    if tris < 1000:
        return str(tris)
    return f"{tris / 1000:g}k" if tris % 1000 == 0 else f"{tris / 1000:.1f}k"


def _flow(layout):
    col = layout.column(align=True)
    col.use_property_split = True
    col.use_property_decorate = False
    return col


class ProcessPanel(HGPanel):
    bl_parent_id = "HG_PT_PROCESS"
    bl_options = {"DEFAULT_CLOSED"}
    icon_name: str = "NONE"
    # Property group with an "enabled" toggle, drawn in the header
    toggle_group: Optional[str] = None
    # Page of the documentation about the section, see common.documentation
    help_url: Optional[str] = None

    @classmethod
    def poll(cls, context):
        if not _props(context).lods:
            return False
        return bool(find_multiple_in_list(context.selected_objects))

    def draw_header(self, context):
        layout = self.layout
        layout.enabled = not get_prefs().is_trial
        if self.toggle_group:
            group = getattr(_props(context), self.toggle_group)
            row = layout.row()
            row.enabled = self.toggle_enabled(context)
            row.prop(group, "enabled", text="")
        try:
            layout.label(text="", icon_value=get_hg_icon(self.icon_name))
        except KeyError:
            layout.label(text="", icon=self.icon_name)

    def draw_header_preset(self, context):
        """A word on what the section does, at the right end of the header."""
        summary = self.summary(context)
        if summary:
            row = self.layout.row()
            row.enabled = False
            row.label(text=summary)

    def toggle_enabled(self, context) -> bool:
        """Whether the toggle can be changed, some formats force it."""
        return True

    def summary(self, context) -> str:
        return ""

    def check_enabled(self, context):
        if self.toggle_group:
            self.layout.enabled = getattr(_props(context), self.toggle_group).enabled

    def _draw_documentation_button(self):
        if not self.help_url:
            return
        draw_docs_button(self.layout, self.help_url)

    def _draw_advanced(self, layout, group):
        """The collapsible advanced drawer of a section, returns its box or None.

        The title sits inside the box, so the box is the drawer.
        """
        box = layout.box()
        row = box.row(align=True)
        row.alignment = "LEFT"
        row.prop(
            group,
            "show_advanced",
            text="Advanced",
            icon="TRIA_DOWN" if group.show_advanced else "TRIA_RIGHT",
            emboss=False,
        )
        return box.column() if group.show_advanced else None

    @staticmethod
    def _draw_selection_box(layout, group, open_prop, items, list_id, noun):
        """A collapsible list with a checkbox per entry and All / None buttons.

        Args:
            layout: Where the box goes.
            group: Property group holding `open_prop`.
            open_prop (str): Name of the bool that opens the list.
            items: Collection with `enabled` and `name` per entry.
            list_id (str): Identifier for `hg3d.select_process_list`.
            noun (str): What the entries are, "keys" or "clips".

        Returns:
            The box, with the list drawn when it is open.
        """
        is_open = getattr(group, open_prop)
        selected = sum(1 for item in items if item.enabled)
        box = layout.box()
        row = box.row(align=True)
        row.prop(
            group,
            open_prop,
            text=f"{selected} of {len(items)} {noun}",
            icon="TRIA_DOWN" if is_open else "TRIA_RIGHT",
            emboss=False,
        )
        if not is_open:
            return None
        buttons = row.row(align=True)
        buttons.alignment = "RIGHT"
        for text, select in (("All", True), ("None", False)):
            op = buttons.operator("hg3d.select_process_list", text=text)
            op.list, op.select = list_id, select
        return box

    @staticmethod
    def _draw_tris_count(row, tris: int):
        sub = row.row()
        sub.alignment = "RIGHT"
        sub.enabled = False
        sub.label(text=_rounded(tris))

    def _draw_thumbnail_picker(
        self, context, layout, levels, prop_name, icon_prefix, tris=None
    ):
        """An enum as a wireframe thumbnail per option.

        With one LOD level the toggle of each option sits below its thumbnail.
        With more levels the thumbnails are followed by one segmented row per
        level, numbered like the exported meshes (LOD0, LOD1, ...), with the
        triangles of that level at the end when `tris` gives them per level.
        """
        items = levels[0].bl_rna.properties[prop_name].enum_items
        ui_scale = context.preferences.system.ui_scale
        available_width = context.region.width / ui_scale - 30
        scale = min(4.5, available_width / len(items) / 20)

        row = layout.row(align=True)
        for item in items:
            col = row.column(align=True)
            icon = get_hg_icon(f"{icon_prefix}_{item.identifier}")
            col.template_icon(icon, scale=scale)
            if len(levels) == 1:
                col.prop_enum(levels[0], prop_name, item.identifier)
        if len(levels) == 1:
            return
        col = layout.column(align=True)
        for index, level in enumerate(levels):
            row = col.row(align=True)
            sub = row.row(align=True)
            sub.scale_x = 0.5
            sub.label(text=str(index))
            row.prop(level, prop_name, expand=True)
            if tris is not None:
                self._draw_short_tris(row, tris[index])

    @staticmethod
    def _draw_short_tris(row, tris: int):
        # A fixed width, so the figure is readable without squeezing the control
        sub = row.row(align=True)
        sub.ui_units_x = 2.3
        sub.alignment = "RIGHT"
        sub.enabled = False
        sub.label(text=_short(tris))

    def _draw_level_rows(self, layout, levels, prop_name, tris=None):
        """One dropdown per LOD level, numbered, with the triangles of the level."""
        col = layout.column(align=True)
        for index, level in enumerate(levels):
            row = col.row(align=True)
            sub = row.row(align=True)
            sub.scale_x = 0.5
            sub.label(text=str(index))
            row.prop(level, prop_name, text="")
            if tris is not None:
                self._draw_short_tris(row, tris[index])


class HG_PT_PROCESS(HGPanel, bpy.types.Panel):
    _register_priority = 4
    bl_idname = "HG_PT_PROCESS"
    bl_label = "Process"

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        return context.scene.HG3D.ui.active_tab == "PROCESS"

    def draw_header(self, context) -> None:
        draw_panel_switch_header(self.layout, context.scene.HG3D)

    def draw(self, context):
        props = _props(context)
        is_trial = get_prefs().is_trial

        col = self.layout.column()
        col.enabled = not is_trial

        row = col.row(align=True)
        row.scale_x = 0.7
        row.alignment = "CENTER"
        draw_icon_title("Processing", row, True)
        col.separator(factor=0.3)
        draw_paragraph(
            col,
            "Export for a game engine or make a frozen copy in this file.",
            alignment="CENTER",
            enabled=False,
        )
        col.separator()

        if not props.lods:
            col.operator("hg3d.init_process", text="Load recipes", icon="IMPORT")
            return

        flow = _flow(col)
        row = flow.row(align=True)
        row.prop(props, "recipe", text="Recipe")
        if is_modified(props):
            row.operator("hg3d.reset_recipe", text="", icon="LOOP_BACK")
            row.operator("hg3d.save_process_template", text="", icon="FILE_TICK")
        flow.prop(props.output, "format", text="Output")
        flow.prop(props, "lod_count", text="LOD levels")

        if not find_multiple_in_list(context.selected_objects):
            col.separator()
            box = col.box()
            row = box.row()
            row.alignment = "CENTER"
            row.alert = True
            row.label(text="No humans selected!")
            return

        if is_trial:
            box = self.layout.box()
            row = box.row(align=True)
            row.alert = True
            row.label(text="Disabled in Trial Version")
            box.operator("wm.url_open", text="Buy Human Generator", depress=True).url = (
                "https://humgen3d.com/pricing"
                "?utm_source=addon"
                "&utm_medium=ui_link"
                "&utm_campaign=trial_click"
            )


class HG_PT_MESHES(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_MESHES"
    bl_label = "Optimize Meshes"
    bl_order = 1
    icon_name = "MOD_DECIM"
    toggle_group = "meshes"
    help_url = "process/optimize-meshes"

    def summary(self, context) -> str:
        """The triangles of the first level, hair not included."""
        human = _human(context)
        if not human:
            return ""
        estimates = self._estimates(context, human)
        tris = sum(count for part, count in estimates[0].items() if part != "hair")
        return f"{_short(round(tris, -3))} tris" if tris >= 10_000 else f"{tris} tris"

    @staticmethod
    def _estimates(context, human):
        """Triangles per part and level, every mesh original when turned off."""
        props = _props(context)
        meshes = props.meshes
        if meshes.enabled:
            return [
                estimate_triangles(
                    human,
                    quality_from_props(level),
                    props.haircards.enabled,
                    meshes.remove_clothing_subdiv,
                    meshes.remove_clothing_solidify,
                )
                for level in props.lods
            ]
        original = quality_of_tier("original")
        return [
            estimate_triangles(human, original, props.haircards.enabled, False, False)
            for _ in props.lods
        ]

    def draw(self, context):
        self.check_enabled(context)
        self._draw_documentation_button()
        props = _props(context)
        human = _human(context)
        levels = list(props.lods)
        col = self.layout.column()
        if human and human.is_trial:
            col.label(text="Body reduction is not available in the trial version.")

        estimates = self._estimates(context, human) if human else []

        parts = (
            ("body", "Body", "body", "lod_body"),
            ("clothing", "Clothing", "outfit", "lod_clothing"),
            ("eyes", "Eyes", "eyes", "lod_eyes"),
            ("teeth", "Teeth", "face", "lod_teeth"),
        )
        for prop_name, label, icon, icon_prefix in parts:
            row = col.row()
            row.label(text=label, icon_value=get_hg_icon(icon))
            if estimates and len(levels) == 1:
                self._draw_tris_count(row, estimates[0][prop_name])
            self._draw_thumbnail_picker(
                context,
                col,
                levels,
                prop_name,
                icon_prefix,
                [tris[prop_name] for tris in estimates] if estimates else None,
            )
            if prop_name == "eyes" and any(level.eyes == "original" for level in levels):
                col.label(text="Not game ready", icon="ERROR")
                draw_paragraph(
                    col,
                    "The layered eyes with a transparent cornea only render in Blender.",
                    enabled=False,
                )
            col.separator()

        col.prop(props.meshes, "remove_hidden_skin")
        box = self._draw_advanced(col, props.meshes)
        if box:
            box.prop(props.meshes, "remove_clothing_subdiv")
            box.prop(props.meshes, "remove_clothing_solidify")

        if estimates:
            col.separator()
            sub = col.column(align=True)
            for index, tris in enumerate(estimates):
                row = sub.row()
                row.label(text=f"LOD{index}" if len(levels) > 1 else "Total")
                self._draw_tris_count(
                    row, sum(count for part, count in tris.items() if part != "hair")
                )


class HG_PT_HAIRCARDS(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_HAIRCARDS"
    bl_label = "Haircards"
    bl_order = 2
    icon_name = "hair"
    toggle_group = "haircards"
    help_url = "process/haircards"

    def summary(self, context) -> str:
        props = _props(context)
        if not props.haircards.enabled:
            return ""
        return props.lods[0].haircards.replace("_only", "").capitalize()

    def draw(self, context):
        self.check_enabled(context)
        self._draw_documentation_button()
        props = _props(context)
        human = _human(context)
        levels = list(props.lods)
        col = self.layout.column()
        if len(levels) == 1:
            level = levels[0]
            if human:
                row = col.row()
                row.label(text="Hair", icon_value=get_hg_icon("hair"))
                self._draw_tris_count(row, human.hair.estimate_haircards_triangles(level.haircards))
            # A large thumbnail of the chosen quality, clicking it shows all of them
            col.template_icon_view(level, "haircards", show_labels=True, scale=8, scale_popup=6)
            col.prop(level, "haircards", text="")
        else:
            tris = (
                [human.hair.estimate_haircards_triangles(level.haircards) for level in levels]
                if human
                else None
            )
            self._draw_level_rows(col, levels, "haircards", tris)
        draw_paragraph(
            self.layout,
            "The particle hair is not carried by any file format. The cards"
            " replace it, with their own baked textures.",
            enabled=False,
        )


class HG_PT_SKELETON(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_SKELETON"
    bl_label = "Skeleton"
    bl_order = 3
    icon_name = "ARMATURE_DATA"
    toggle_group = "skeleton"
    help_url = "process/skeleton"

    def summary(self, context) -> str:
        skeleton = _props(context).skeleton
        return SKELETON_LABELS[skeleton.names] if skeleton.enabled else ""

    def draw(self, context):
        self.check_enabled(context)
        self._draw_documentation_button()
        props = _props(context)
        skeleton = props.skeleton
        human = _human(context)
        levels = list(props.lods)
        col = self.layout.column()

        if human and human.pose.rigify.is_rigify:
            col.alert = True
            col.label(text="Not available for Rigify humans", icon="ERROR")
            col.alert = False
            draw_paragraph(
                col,
                "The skeleton is made from the Human Generator rig, which Rigify"
                " replaced. The Rigify rig is exported as it is.",
                enabled=False,
            )
            return

        draw_paragraph(
            col,
            "Removes the control bones, constraints and drivers, adds a root bone"
            " and names the bones for the engine. Face and corrective shape keys"
            " stay as blend shapes.",
            enabled=False,
        )
        col.separator()
        flow = _flow(col)
        flow.prop(skeleton, "names")
        if skeleton.names == "custom":
            flow.prop(skeleton, "names_file", text="File")
        flow.prop(skeleton, "rest_pose")

        box = self._draw_advanced(col, skeleton)
        if not box:
            return
        row = box.row(align=True)
        row.prop(skeleton, "root_bone", text="Root bone", toggle=True)
        sub = row.row(align=True)
        sub.enabled = skeleton.root_bone
        sub.prop(skeleton, "root_bone_name", text="")

        box.separator()
        self.draw_subtitle("Keep bones", box, alignment="LEFT")
        grid = box.grid_flow(columns=2, align=True)
        for prop_name in ("keep_eyes", "keep_jaw", "keep_breasts", "keep_metacarpals"):
            grid.prop(skeleton, prop_name, toggle=True)

        box.separator()
        self.draw_subtitle("Bones per vertex", box, alignment="LEFT")
        if len(levels) == 1:
            row = box.row(align=True)
            row.prop(levels[0], "bones_per_vertex", expand=True)
        else:
            sub = box.column(align=True)
            for index, level in enumerate(levels):
                row = sub.row(align=True)
                label = row.row(align=True)
                label.scale_x = 0.5
                label.label(text=str(index))
                row.prop(level, "bones_per_vertex", expand=True)

        if props.output.format == "fbx":
            box.separator()
            self.draw_subtitle("Units", box, alignment="LEFT")
            row = box.row(align=True)
            row.prop(skeleton, "units", expand=True)


class HG_PT_SHAPEKEYS(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_SHAPEKEYS"
    bl_label = "Shape Keys"
    bl_order = 4
    icon_name = "SHAPEKEY_DATA"
    toggle_group = "shape_keys"
    help_url = "process/shape-keys"

    def summary(self, context) -> str:
        props = _props(context)
        keys = props.shape_keys
        if not keys.enabled:
            return ""
        total = 0
        for group, *_ in KEY_GROUPS:
            if getattr(keys, group) == "keep":
                total += sum(1 for item in getattr(keys, f"items_{group}") if item.enabled)
        return f"{total} keys" if total else ""

    def draw(self, context):
        self.check_enabled(context)
        self._draw_documentation_button()
        props = _props(context)
        keys = props.shape_keys

        col = self.layout.column()
        draw_paragraph(
            col,
            "Keep a group as shape keys, bake it into the mesh or remove it. Kept"
            " sliders become shape keys. The face rig and the 1-click expressions"
            " are loaded from the library. Turned off, no shape keys are kept.",
            enabled=False,
        )
        row = col.row()
        row.alignment = "RIGHT"
        row.operator("hg3d.refresh_key_lists", text="", icon="FILE_REFRESH", emboss=False)
        for group, label, _ in KEY_GROUPS:
            items = getattr(keys, f"items_{group}")
            col.separator(factor=0.5)
            row = col.row()
            row.label(text=label)
            sub = row.row()
            sub.alignment = "RIGHT"
            sub.enabled = False
            sub.label(text=f"{len(items)} keys")
            row = col.row(align=True)
            row.prop(keys, group, expand=True)
            if getattr(keys, group) == "keep":
                self._draw_keep_selection(col, keys, group, items)

        if len(props.lods) > 1:
            col.separator()
            col.prop(keys, "lod0_only")

        kept = driven_groups_kept((group, getattr(keys, group)) for group, *_ in KEY_GROUPS)
        if kept:
            col.separator()
            row = col.row()
            row.alert = True
            row.label(text=f"{' and '.join(kept)}: driven by bones", icon="ERROR")
            draw_paragraph(
                col,
                "Exported files don't contain the drivers, so reconnect these keys"
                " to the bones in the other program.",
                enabled=False,
            )

    def _draw_keep_selection(self, layout, keys, group, items):
        """The keys of a kept group to tick, in a collapsible list."""
        box = self._draw_selection_box(layout, keys, f"open_{group}", items, group, "keys")
        if not box:
            return
        if not items:
            draw_paragraph(box, "Nothing to select, refresh the lists.", enabled=False)
        grid = box.grid_flow(columns=2, align=True, row_major=True)
        for item in items:
            grid.prop(item, "enabled", text=item.name)


class HG_PT_TEXTURES(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_TEXTURES"
    bl_label = "Bake textures"
    bl_order = 5
    icon_name = "TEXTURE"
    toggle_group = "textures"
    help_url = "process/bake-textures"

    def toggle_enabled(self, context) -> bool:
        # Files always need the baked textures
        return _props(context).output.format == "in_file"

    def summary(self, context) -> str:
        """The resolution tier, files bake whatever the toggle says."""
        props = _props(context)
        if not props.textures.enabled and props.output.format == "in_file":
            return ""
        return TIER_LABELS[texture_tier_of(_resolution_from_props(props.textures))]

    def draw(self, context):
        props = _props(context)
        textures = props.textures
        self.layout.enabled = textures.enabled or props.output.format != "in_file"
        self._draw_documentation_button()
        col = self.layout.column()
        if props.output.format != "in_file":
            draw_paragraph(col, "Files need baked textures, so this is always on.", enabled=False)

        flow = _flow(col)
        flow.prop(textures, "tier", text="Resolution")
        flow.prop(textures, "file_format", text="Format")
        if textures.file_format == "jpeg" and props.haircards.enabled:
            row = flow.row()
            row.alert = True
            row.label(text="JPEG drops the hair alpha", icon="ERROR")

        col.separator()
        self.draw_subtitle("Material setup", col, alignment="LEFT")
        flow = _flow(col)
        flow.prop(textures, "workflow")
        flow.prop(textures, "normal_map")

        box = self._draw_advanced(col, textures)
        if not box:
            return
        self.draw_subtitle("Resolution per set", box, alignment="LEFT")
        flow = _flow(box)
        for set_name in TEXTURE_SETS:
            flow.prop(textures, f"res_{set_name}", text=set_name.capitalize())

        box.separator()
        self.draw_subtitle("Passes", box, alignment="LEFT")
        grid = box.grid_flow(columns=len(TEXTURE_PASSES) + 1, align=True, row_major=True)
        grid.label(text="")
        for pass_id, *_ in TEXTURE_PASSES:
            grid.label(text=PASS_LABELS[pass_id])
        for set_name in TEXTURE_SETS:
            grid.label(text=set_name.capitalize())
            for pass_id, *_ in TEXTURE_PASSES:
                grid.prop(textures, f"pass_{set_name}_{pass_id}", text="")

        box.separator()
        row = box.row()
        row.enabled = textures.file_format != "jpeg" and props.haircards.enabled
        row.prop(textures, "pack_hair_alpha")
        row = box.row(align=True)
        row.label(text="Samples")
        row.prop(textures, "samples", expand=True)


class HG_PT_ANIMATIONS(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_ANIMATIONS"
    bl_label = "Animations"
    bl_order = 6
    icon_name = "ACTION"
    toggle_group = "animations"
    help_url = "process/animations"

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        # Experimental, see the preferences. The API and recipes still run it.
        if not get_prefs().experimental_features:
            return False
        return _props(context).output.format in ("in_file", "fbx", "glb", "gltf")

    def summary(self, context) -> str:
        animations = _props(context).animations
        if not animations.enabled:
            return ""
        return f"{sum(1 for clip in animations.clips if clip.enabled)} clips"

    def draw(self, context):
        self.check_enabled(context)
        self._draw_documentation_button()
        props = _props(context)
        animations = props.animations
        col = self.layout.column()

        row = col.row(align=True)
        row.prop(animations, "source", expand=True)
        row.operator("hg3d.refresh_clips", text="", icon="FILE_REFRESH")

        box = self._draw_selection_box(
            col, animations, "clips_open", animations.clips, "clips", "clips"
        )
        if box:
            if not animations.clips:
                text = (
                    "No animations on this human, see the Pose section."
                    if animations.source == "human"
                    else "No animations in the library."
                )
                draw_paragraph(box, text, enabled=False)
            sub = box.column(align=True)
            for clip in animations.clips:
                row = sub.row(align=True)
                row.prop(clip, "enabled", text="")
                row.label(text=clip.name, icon="ACTION" if clip.is_hg else "ANIM_DATA")
        if animations.source == "human" and any(not clip.is_hg for clip in animations.clips):
            draw_paragraph(
                col,
                "Clips that are not from the animation library are exported as"
                " they are, in the A-pose rest pose.",
                enabled=False,
            )

        col.separator()
        if props.output.format != "in_file":
            _flow(col).prop(animations, "layout", text="Files")

        box = self._draw_advanced(col, animations)
        if not box:
            return
        flow = _flow(box)
        flow.prop(animations, "root_motion")
        if props.output.format == "fbx":
            flow.prop(animations, "sample_rate")


class HG_PT_SCRIPTS(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_SCRIPTS"
    bl_label = "Scripts"
    bl_order = 7
    icon_name = "FILE_SCRIPT"
    toggle_group = "scripts"
    help_url = "process/scripts"

    def summary(self, context) -> str:
        scripts = _props(context).scripts
        count = len(scripts.items)
        return f"{count} script{'s' if count != 1 else ''}" if scripts.enabled and count else ""

    def draw(self, context):
        self.check_enabled(context)
        self._draw_documentation_button()
        props = _props(context)
        scripts = props.scripts
        col = self.layout.column()
        draw_paragraph(
            col,
            "Python scripts that run on the processed copy, before or after the"
            " file is written. Scripts of a stage run top to bottom.",
            enabled=False,
        )

        for index, item in enumerate(scripts.items):
            box = col.box()
            row = box.row(align=True)
            row.prop(
                item,
                "menu_open",
                text="",
                icon="TRIA_DOWN" if item.menu_open else "TRIA_RIGHT",
                emboss=False,
            )
            row.label(text=item.name)
            subrow = row.row(align=True)
            subrow.scale_x = 0.8
            op = subrow.operator("hg3d.move_script", text="", icon="TRIA_UP")
            op.index, op.direction = index, -1
            op = subrow.operator("hg3d.move_script", text="", icon="TRIA_DOWN")
            op.index, op.direction = index, 1
            row.separator()
            row.operator("hg3d.remove_script", text="", icon="X").index = index

            if not item.menu_open:
                continue
            if item.description:
                sub = box.row()
                sub.enabled = False
                draw_paragraph(sub, text=item.description, alignment="LEFT")
            flow = _flow(box)
            flow.prop(item, "stage")
            flow.prop(item, "on_error")
            for arg in item.args:
                arg.draw_prop(flow)

        row = col.row(align=True)
        row.scale_y = 1.2
        row.operator_menu_enum("hg3d.add_script", "script", text="Add script", icon="ADD")
        row.operator("hg3d.new_script", text="New", icon="FILE_NEW")


class HG_PT_Z_PROCESS_LOWER(ProcessPanel, bpy.types.Panel):
    bl_options = {"HIDE_HEADER"}
    bl_order = 8

    def draw(self, context):
        box = self.layout.box()
        is_trial = get_prefs().is_trial
        box.enabled = not is_trial
        props = _props(context)
        output = props.output
        is_file = output.format != "in_file"

        self.draw_subtitle("Output", box, icon="SETTINGS")
        flow = _flow(box)
        flow.prop(output, "name", text="Name")
        if is_file:
            flow.prop(output, "folder", text="Folder")
            row = flow.row()
            row.alignment = "RIGHT"
            row.enabled = False
            folder = output_folder(props_to_settings(props))
            row.label(text=self._shorten(folder), icon="INFO")

        advanced = self._draw_advanced(box, output)
        if advanced:
            draw_docs_button(advanced, "process/output")
            flow = _flow(advanced)
            flow.prop(output, "naming")
            if output.naming == "custom":
                for name in ("rig", "mesh", "material", "texture"):
                    flow.prop(output, f"template_{name}")
            if is_file:
                flow.prop(output, "textures")
                flow.prop(output, "keep_copy")
            if output.format == "fbx":
                advanced.separator()
                self.draw_subtitle("FBX", advanced, alignment="LEFT")
                flow = _flow(advanced)
                fbx = output.fbx
                flow.prop(fbx, "axis_forward")
                flow.prop(fbx, "axis_up")
                flow.prop(fbx, "primary_bone_axis")
                flow.prop(fbx, "secondary_bone_axis")
                flow.prop(fbx, "smoothing")
                flow.prop(fbx, "triangulate")
                flow.prop(fbx, "leaf_bones")
                flow.prop(fbx, "custom_properties")
            elif output.format in ("glb", "gltf"):
                advanced.separator()
                self.draw_subtitle("glTF", advanced, alignment="LEFT")
                flow = _flow(advanced)
                flow.prop(output.gltf, "image_format")
                flow.prop(output.gltf, "tangents")
                flow.prop(output.gltf, "draco")

        human_rigs = find_multiple_in_list(context.selected_objects)
        count = len(human_rigs)
        box.separator(factor=0.5)
        humans_box = box.box()
        row = humans_box.row()
        row.alignment = "CENTER"
        row.prop(
            props,
            "human_list_isopen",
            text=f"{count} {'human' if count == 1 else 'humans'} selected",
            icon="TRIA_DOWN" if props.human_list_isopen else "TRIA_RIGHT",
            emboss=False,
        )
        if props.human_list_isopen:
            for human_rig in sorted(human_rigs, key=lambda rig: rig.name):
                humans_box.label(text=human_rig.name, icon="DOT")

        row = box.row(align=True)
        row.scale_y = 1.5
        label = LABELS.get(output.format, output.format)
        if is_file:
            text = f"Export to {label}" if count == 1 else f"Export {count} humans to {label}"
        else:
            text = "Make processed copy" if count == 1 else f"Make {count} processed copies"
        row.operator("hg3d.process", text=text, depress=True, icon="EXPORT" if is_file else "DUPLICATE")

        draw_paragraph(
            box,
            text="The result is a processed copy that can't be edited with Human"
            " Generator. The original human is not changed.",
            enabled=False,
        )

        human = _human(context)
        if human:
            check = preflight(human, props_to_settings(props), context)
            if check.errors or check.warnings:
                box.separator(factor=0.5)
            for error in check.errors:
                row = box.row()
                row.alert = True
                draw_paragraph(row, error, alignment="LEFT")
            for warning in check.warnings:
                row = box.row()
                row.label(text="", icon="ERROR")
                draw_paragraph(row, warning, alignment="LEFT", enabled=False)

        draw_docs_button(self.layout, "process", text="Process Guide", icon="URL", emboss=False)

    @staticmethod
    def _shorten(path: str, length: int = 38) -> str:
        home = os.path.expanduser("~")
        if path.startswith(home):
            path = "~" + path[len(home) :]
        return path if len(path) <= length else "…" + path[-length:]
