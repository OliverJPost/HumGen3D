# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Optional

import bpy
from HumGen3D.common import find_multiple_in_list
from HumGen3D.human.human import Human
from HumGen3D.user_interface.icons.icons import get_hg_icon
from HumGen3D.user_interface.panel_functions import (
    draw_panel_switch_header,
    draw_paragraph,
    get_flow,
)

from HumGen3D.backend import get_prefs
from ..ui_baseclasses import HGPanel, draw_icon_title


class ProcessPanel(HGPanel):
    bl_parent_id = "HG_PT_PROCESS"
    bl_options = {"DEFAULT_CLOSED"}
    icon_name: str
    # Sections without this are always applied when processing
    enabled_propname: Optional[str] = None
    help_url: Optional[str] = None

    @classmethod
    def poll(cls, context):
        if context.scene.HG3D.process.mode != "recipe":
            return False
        return find_multiple_in_list(context.selected_objects)

    def draw_header(self, context):
        is_trial = get_prefs().is_trial
        self.layout.enabled = not is_trial

        if self.enabled_propname:
            self.layout.prop(context.scene.HG3D.process, self.enabled_propname, text="")

        icon_name = self.icon_name
        if hasattr(self, "forbidden_propname"):
            is_forbidden = getattr(Human.from_existing(context.object).process, self.forbidden_propname)
            is_enabled = getattr(context.scene.HG3D.process, self.enabled_propname, False)
            if is_forbidden and is_enabled:
                self.layout.alert = True
                icon_name = "ERROR"
            if is_forbidden and not is_enabled:
                icon_name = "CHECKMARK"

        try:
            self.layout.label(text="", icon_value=get_hg_icon(icon_name))
        except KeyError:
            self.layout.label(text="", icon=icon_name)

    def check_enabled(self, context):
        self.layout.enabled = getattr(context.scene.HG3D.process, self.enabled_propname)

    def _draw_category_title(self, layout, text, icon_name, tris_count):
        """Subtitle of a category with its estimated triangle count on the right."""
        row = layout.row()
        row.label(text=text, icon_value=get_hg_icon(icon_name))
        self._draw_tris_count(row, tris_count)

    @staticmethod
    def _draw_tris_count(row, tris_count):
        # Rounded, as it's an estimate
        rounded = round(tris_count, -3 if tris_count >= 10_000 else -2)
        sub = row.row()
        sub.alignment = "RIGHT"
        sub.enabled = False
        sub.label(text=f"~{rounded:,} tris")

    def _draw_thumbnail_picker(self, context, layout, props, prop_name, icon_prefix):
        """Draw an enum as a wireframe thumbnail per option, with a toggle button
        below each so users see what every option does to the mesh. The icons are
        named {icon_prefix}_{option}."""
        items = props.bl_rna.properties[prop_name].enum_items
        # Fit the thumbnails to the width of the sidebar, as they don't shrink
        ui_scale = context.preferences.system.ui_scale
        available_width = context.region.width / ui_scale - 30
        scale = min(4.5, available_width / len(items) / 20)

        row = layout.row(align=True)
        for item in items:
            col = row.column(align=True)
            icon = get_hg_icon(f"{icon_prefix}_{item.identifier}")
            col.template_icon(icon, scale=scale)
            col.prop_enum(props, prop_name, item.identifier)

    def _draw_documentation_button(self):
        self.layout.operator(
            "wm.url_open",
            text="Documentation",
            icon="HELP",
        ).url = (
            "https://help.humgen3d.com/" + self.help_url
        )


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
        draw_panel_switch_header(
            self.layout, context.scene.HG3D
        )  # type:ignore[attr-defined]

    def draw(self, context):
        process_sett = context.scene.HG3D.process
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
            "Process for other programs, workflows, or results.",
            alignment="CENTER",
            enabled=False,
        )

        col.separator()

        row = col.row(align=True)
        row.scale_y = 1.5
        row.prop(process_sett, "mode", expand=True)

        col.separator()

        if process_sett.mode == "multi_recipe":
            self._draw_multi_recipe_list(col, process_sett)
            return

        col = col.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.5
        row.prop(process_sett, "presets", text="")
        row.operator("hg3d.save_process_template", text="", icon="ADD")

        box = col.box()
        human_rigs = find_multiple_in_list(context.selected_objects)
        row = box.row()
        row.alignment = "CENTER"
        amount = len(human_rigs)
        if amount == 0:
            row.alert = True
            row.label(text="No humans selected!")
            return

        human_plural_tag = "human" if amount == 1 else "humans"
        row.prop(
            process_sett,
            "human_list_isopen",
            text=f"{amount} {human_plural_tag} selected",
            icon="TRIA_DOWN" if process_sett.human_list_isopen else "TRIA_RIGHT",
            emboss=False,
        )

        if process_sett.human_list_isopen:
            for human_rig in human_rigs:
                box.label(text=human_rig.name, icon="DOT")

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


    @staticmethod
    def _draw_multi_recipe_list(layout, process_sett):
        row = layout.row()
        row.template_list(
            "HG_UL_MULTI_RECIPE",
            "",
            process_sett,
            "multi_recipes",
            process_sett,
            "multi_recipes_index",
            rows=4,
        )
        # Placeholder until recipes can be added to the list
        button_col = row.column()
        button_col.enabled = False
        button_col.label(text="", icon="ADD")

        draw_paragraph(
            layout,
            "Processing with multiple recipes at once is not available yet.",
            alignment="CENTER",
            enabled=False,
        )


class HG_PT_BAKE(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_BAKE"
    bl_label = "Bake Textures"
    bl_order = 4
    icon_name = "RENDERLAYERS"
    enabled_propname = "baking_enabled"
    help_url = "baking"
    forbidden_propname = "was_baked"

    def draw(self, context):
        self.check_enabled(context)
        self._draw_documentation_button()
        human = Human.from_existing(context.object)
        layout = self.layout
        layout.enabled = getattr(context.scene.HG3D.process, self.enabled_propname)
        if human.process.was_baked:
            layout.alert = True
            layout.label(text="Already baked!")
            return

        sett = context.scene.HG3D  # type:ignore[attr-defined]
        bake_sett = sett.process.baking

        if self._draw_baking_warning_labels(context, layout):
            return

        col = get_flow(sett, layout)
        self.draw_subtitle("Quality", col, "SETTINGS")
        col.prop(bake_sett, "samples", text="Samples")

        layout.separator()

        col = get_flow(sett, layout)

        self.draw_subtitle("Resolution", col, "IMAGE_PLANE")

        for res_type in ["body", "eyes", "teeth", "clothes"]:
            col.prop(bake_sett, f"res_{res_type}", text=res_type.capitalize())

        row = col.row(align=True)

        has_haircards = (
            context.scene.HG3D.process.haircards_enabled or human.process.has_haircards
        )
        row.enabled = has_haircards
        row.prop(bake_sett, "res_haircards", text="Haircards")

        row = col.row(align=True)
        row.enabled = has_haircards and bake_sett.file_type != "jpeg"
        row.prop(bake_sett, "pack_haircard_alpha")

    def _draw_baking_warning_labels(self, context, layout) -> bool:
        """Draws warning if no human is selected or textures are already baked.

        Args:
            context (bpy.context): Blender context
            layout (UILayout): layout to draw warning labels in

        Returns:
            bool: True if problem found, causing rest of ui to cancel
        """
        human = Human.from_existing(context.object)
        if not human:
            layout.label(text="No human selected")
            return True

        if "hg_baked" in human.objects.rig:
            layout.label(text="Already baked")
            return True

        return False


class HG_PT_MODAPPLY(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_MODAPPLY"
    bl_label = "Apply Modifiers"
    bl_order = 5
    icon_name = "MOD_SUBSURF"
    enabled_propname = "modapply_enabled"
    help_url = "modapply"

    def draw(self, context):
        self.check_enabled(context)
        self._draw_documentation_button()
        layout = self.layout
        sett = context.scene.HG3D  # type:ignore[attr-defined]
        col = layout.column(align=True)
        col.label(text="Select modifiers to be applied:")
        col.template_list(
            "HG_UL_MODAPPLY",
            "",
            context.scene,
            "modapply_col",
            context.scene,
            "modapply_col_index",
        )

        row = col.row(align=True)
        row.operator("hg3d.ulrefresh", text="Refresh").uilist_type = "modapply"
        row.operator("hg3d.selectmodapply", text="All").select_all = True
        row.operator("hg3d.selectmodapply", text="None").select_all = False

        layout.separator(factor=0.5)

        col = layout.column(align=True)
        col.label(text="Objects to apply:")
        row = col.row(align=True)
        row.prop(sett.process.modapply, "apply_body", toggle=True)
        row.prop(sett.process.modapply, "apply_eyes", toggle=True)
        row = col.row(align=True)
        row.prop(sett.process.modapply, "apply_teeth", toggle=True)
        row.prop(sett.process.modapply, "apply_clothing", toggle=True)

        layout.separator()
        col = layout.column(align=True)
        self.draw_subtitle("Options", col, "SETTINGS")
        col.prop(sett.process.modapply, "keep_shapekeys", text="Keep shapekeys")
        col.prop(sett.process.modapply, "apply_hidden", text="Apply hidden modifiers")


class HG_PT_MESHES(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_MESHES"
    bl_label = "Optimize Meshes"
    bl_order = 0
    icon_name = "NORMALS_VERTEX"
    enabled_propname = "lod_enabled"
    help_url = "lod"
    forbidden_propname = "is_lod"

    def draw(self, context):
        self.check_enabled(context)
        self._draw_documentation_button()
        col = self.layout.column()
        human = Human.from_existing(context.object)
        if human.is_trial:
            col.label(text="Not available in trial version.")
            col.label(text="Reason: LOD won't work properly")
            col.label(text="on mesh with holes.")
            return
        if human.process.is_lod:
            col.alert = True
            col.label(text="LOD already generated!")
            return

        lod_sett = context.scene.HG3D.process.lod
        tris = human.process.lod.estimate_triangles(
            int(lod_sett.body_lod),
            lod_sett.clothing,
            lod_sett.eyes,
            int(lod_sett.teeth),
            lod_sett.remove_clothing_subdiv,
            lod_sett.remove_clothing_solidify,
        )

        self._draw_category_title(col, "Body", "body", tris["body"])
        self._draw_thumbnail_picker(context, col, lod_sett, "body_lod", "lod_body")

        col.separator()
        self._draw_category_title(col, "Clothing", "outfit", tris["clothing"])
        self._draw_thumbnail_picker(
            context, col, lod_sett, "clothing", "lod_clothing"
        )
        col.prop(lod_sett, "remove_clothing_subdiv", text="Remove clothing subdiv")
        col.prop(lod_sett, "remove_clothing_solidify", text="Remove clothing solidify")

        col.separator()
        self._draw_category_title(col, "Eyes", "eyes", tris["eyes"])
        self._draw_thumbnail_picker(context, col, lod_sett, "eyes", "lod_eyes")
        if lod_sett.eyes == "original":
            col.label(text="Not game ready", icon="ERROR")
            draw_paragraph(
                col,
                "The layered eyes with a transparent cornea only render in Blender.",
                enabled=False,
            )

        col.separator()
        self._draw_category_title(col, "Teeth", "face", tris["teeth"])
        self._draw_thumbnail_picker(context, col, lod_sett, "teeth", "lod_teeth")

        col.separator()
        row = col.row()
        row.label(text="Total, without hair:")
        self._draw_tris_count(row, sum(tris.values()))


class HG_PT_HAIRCARDS(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_HAIRCARDS"
    bl_label = "Generate Haircards"
    bl_order = 1
    icon_name = "hair"
    enabled_propname = "haircards_enabled"
    help_url = "haircards"
    forbidden_propname = "has_haircards"

    def draw(self, context):
        self.check_enabled(context)
        self._draw_documentation_button()
        human = Human.from_existing(context.object)
        if human.process.has_haircards:
            self.layout.alert = True
            self.layout.label(text="Haircards already generated!")
            return

        col = self.layout.column()
        hairc_sett = context.scene.HG3D.process.haircards

        tris = human.hair.estimate_haircards_triangles(hairc_sett.quality)
        self._draw_category_title(col, "Hair", "hair", tris)
        # A large thumbnail of the chosen quality, clicking it shows all of them
        col.template_icon_view(
            hairc_sett, "quality", show_labels=True, scale=8, scale_popup=6
        )
        col.prop(hairc_sett, "quality", text="")

        message = (
            "The quality applies to the hair on the scalp and the face. If you are"
            " baking textures, see Bake Textures menu for haircard baking resolution."
        )

        draw_paragraph(self.layout, text=message, enabled=False)


class HG_PT_RIG(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_RIG"
    bl_label = "Rig"
    bl_order = 2
    icon_name = "ARMATURE_DATA"

    def draw(self, context):
        human = Human.from_existing(context.object)
        is_rigify = human.pose.rigify.is_rigify

        col = self.layout.column()
        self.draw_subtitle("Rest pose", col, alignment="LEFT")
        row = col.row(align=True)
        row.scale_y = 1.5
        row.enabled = not is_rigify
        row.prop(context.scene.HG3D.process, "rest_pose", expand=True)

        if is_rigify:
            draw_paragraph(
                col, text="T-pose is not available for Rigify humans.", enabled=False
            )


class HG_PT_BONE_RENAMING(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_BONE_RENAMING"
    bl_label = "Bone Renaming"
    bl_order = 3
    icon_name = "MOD_ARMATURE"
    enabled_propname = "rig_renaming_enabled"
    help_url = "bonerename"

    def draw(self, context):
        self.check_enabled(context)
        self._draw_documentation_button()
        naming_sett = context.scene.HG3D.process.rig_renaming
        col = self.layout.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False

        self.draw_subtitle("Suffix naming", col, "MOD_MIRROR")
        col.prop(naming_sett, "suffix_L", text="Left")
        col.prop(naming_sett, "suffix_R", text="Right")

        prop_dict = defaultdict()
        for prop in naming_sett.bl_rna.properties:
            description = prop.description
            if not description.startswith("Category"):
                continue
            category = description.split(" ")[1].replace(",", "").capitalize()
            prop_dict.setdefault(category, []).append(prop)

        for category, props in prop_dict.items():
            col.separator()
            self.draw_subtitle(category, col, icon="OPTIONS", alignment="CENTER")
            for prop in props:
                mirrored_icon = (
                    {"icon": "MOD_MIRROR"} if "True" in prop.description else {}
                )
                col.prop(naming_sett, prop.identifier, **mirrored_icon)


def create_token_row(layout, token_name):
    row = layout.row()
    row.scale_y = 0.8
    row.label(text=token_name)


def create_disabled_row(layout, text):
    row = layout.row()
    row.scale_y = 0.8
    row.enabled = False
    row.label(text=text)


class HG_PT_RENAMING(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_RENAMING"
    bl_label = "Other Renaming"
    bl_order = 6
    icon_name = "OUTLINER_OB_FONT"
    enabled_propname = "renaming_enabled"
    help_url = "otherrename"

    def draw(self, context):
        self.check_enabled(context)
        self._draw_documentation_button()
        rename_sett = context.scene.HG3D.process.renaming

        box = self.layout.box()
        self.draw_subtitle("Tokens", box, "HELP")

        col = box.column(align=True)
        create_token_row(col, ". (period at start of name)")
        create_disabled_row(col, "Hides material in Blender")
        create_token_row(col, "Suffix")
        create_disabled_row(col, "Custom suffix: e.g. _LOD1")
        create_token_row(col, "{name}")
        create_disabled_row(col, "Human name: e.g. Jake")
        create_token_row(col, "{original_name}")
        create_disabled_row(col, "Original name: e.g. HG_Eyes")
        create_token_row(col, "{custom}")
        create_disabled_row(col, "Custom token defined below.")

        col = self.layout.column()
        col.use_property_decorate = False
        col.use_property_split = True
        col.prop(rename_sett, "custom_token", text="{custom}")
        col.prop(rename_sett, "suffix", text="Suffix")
        self.layout.separator()

        self.draw_subtitle("Objects", self.layout, "MESH_CUBE")
        row = self.layout.row()
        row.alignment = "CENTER"
        row.scale_y = 0.8
        row.prop(rename_sett, "use_suffix")
        for prop_name in (
            "rig_obj",
            "body_obj",
            "eye_obj",
            "haircards_obj",
            "upper_teeth_obj",
            "lower_teeth_obj",
            "clothing",
        ):
            self.layout.prop(rename_sett, prop_name)

        self.layout.separator()
        self.draw_subtitle("Materials", self.layout, "MATERIAL")

        row = self.layout.row()
        row.alignment = "CENTER"
        row.scale_y = 0.8
        row.prop(rename_sett.materials, "use_suffix")
        for prop in rename_sett.materials.bl_rna.properties:
            if prop.identifier in ("bl_rna", "rna_type", "name", "use_suffix"):
                continue
            self.layout.prop(rename_sett.materials, prop.identifier)


class HG_PT_SCRIPTS(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_SCRIPTS"
    bl_label = "Custom scripts"
    bl_order = 7
    icon_name = "FILE_SCRIPT"
    enabled_propname = "scripting_enabled"
    help_url = "scripts"

    def draw(self, context):
        self.check_enabled(context)
        self._draw_documentation_button()
        col = self.layout.column()
        self.draw_subtitle("Available Scripts", col)
        row = col.row(align=True)
        row.scale_y = 1.5
        row.prop(context.scene.HG3D.process.scripting, "available_scripts", text="")
        row.operator("hg3d.add_script", text="", icon="ADD")

        coll = context.scene.hg_scripts_col
        if coll:
            self.draw_subtitle("Selected Scripts", col)
            draw_paragraph(
                col, text="Executed top to bottom.", alignment="CENTER", enabled=False
            )
        for item in coll:
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
            op.name = item.name
            op.move_up = False
            op = subrow.operator("hg3d.move_script", text="", icon="TRIA_DOWN")
            op.name = item.name
            op.move_up = True

            row.separator()

            row.operator("hg3d.remove_script", text="", icon="X").name = item.name

            if not item.menu_open:
                continue

            row = box.row()
            row.enabled = False
            draw_paragraph(row, text=item.description, alignment="LEFT")
            if not item.args:
                continue
            col = box.column()
            col.label(text="Arguments:")
            for arg in item.args:
                arg.draw_prop(col)


class HG_PT_Z_PROCESS_LOWER(ProcessPanel, bpy.types.Panel):
    bl_options = {"HIDE_HEADER"}
    bl_order = 8

    def draw(self, context):
        box = self.layout.box()
        is_trial = get_prefs().is_trial
        box.enabled = not is_trial

        sett = context.scene.HG3D  # type:ignore[attr-defined]
        pr_sett = sett.process

        self.draw_subtitle("Output", box, icon="SETTINGS")

        row = box.row(align=True)
        row.scale_y = 1.5
        row.prop(pr_sett, "output", expand=True)

        if pr_sett.baking_enabled or pr_sett.output == "export":
            col = box.column(align=True)
            col.use_property_split = True
            col.use_property_decorate = False

            bake_sett = sett.process.baking
            if pr_sett.baking_enabled:
                col.prop(bake_sett, "file_type", text="Format:", icon="TEXTURE")

            if pr_sett.output == "export":
                col.prop(pr_sett, "file_type", text=" ", icon="MESH_CUBE")
                col.prop(pr_sett, "output_name", text="Filename")

            label = "Tex. Folder" if pr_sett.output != "export" else "Folder"
            col.prop(bake_sett, "export_folder", text=label)

            row = col.row()
            row.alignment = "RIGHT"
            row.label(text="HG folder when empty", icon="INFO")

        row = box.row(align=True)
        row.scale_y = 1.5
        row.operator("hg3d.process", text="Process", depress=True, icon="COMMUNITY")

        draw_paragraph(
            box,
            text="The result is a processed copy that can't be edited with Human"
            " Generator. The original human is not changed.",
            enabled=False,
        )

        self.layout.operator(
            "wm.url_open", text="Process Guide", icon="URL", emboss=False
        ).url = "https://help.humgen3d.com/process/overview"
