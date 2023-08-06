# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE
from abc import ABC, abstractmethod
from collections import defaultdict

import bpy
from HumGen3D.common import find_multiple_in_list
from HumGen3D.human.human import Human
from HumGen3D.user_interface.icons.icons import get_hg_icon
from HumGen3D.user_interface.panel_functions import (
    draw_panel_switch_header,
    draw_paragraph,
    get_flow,
)

from ..ui_baseclasses import HGPanel, draw_icon_title


class ProcessPanel(HGPanel):
    bl_parent_id = "HG_PT_PROCESS"
    bl_options = {"DEFAULT_CLOSED"}
    icon_name: str

    @property
    def enabled_propname(self):
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement enabled propname"
        )

    @property
    def help_url(self):
        raise NotImplementedError(f"{self.__class__.__name__} must implement help_url")

    @classmethod
    def poll(cls, context):
        return find_multiple_in_list(context.selected_objects)

    def draw_header(self, context):
        if hasattr(self, "enabled_propname"):
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
        col = self.layout.column()

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


class HG_PT_BAKE(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_BAKE"
    bl_label = "Bake Textures"
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

        row.enabled = context.scene.HG3D.process.haircards_enabled or human.process.has_haircards
        row.prop(bake_sett, "res_haircards", text="Haircards")

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


class HG_PT_LOD(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_LOD"
    bl_label = "Levels of Detail"
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

        self.draw_subtitle("Body LOD", col, icon=get_hg_icon("body"), alignment="LEFT")
        col.prop(lod_sett, "body_lod", text="")

        col.separator()
        self.draw_subtitle(
            "Clothing", col, icon=get_hg_icon("outfit"), alignment="LEFT"
        )
        col.prop(lod_sett, "decimate_ratio", text="Decimate ratio")
        col.prop(lod_sett, "remove_clothing_subdiv", text="Remove clothing subdiv")
        col.prop(lod_sett, "remove_clothing_solidify", text="Remove clothing solidify")


class HG_PT_HAIRCARDS(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_HAIRCARDS"
    bl_label = "Haircards"
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
        col.scale_y = 1.5
        hairc_sett = context.scene.HG3D.process.haircards

        col.prop(hairc_sett, "quality")

        row = self.layout.row(align=True)
        row.prop(hairc_sett, "face_hair")
        r_row = row.row(align=True)
        r_row.alert = True
        r_row.label(text="ALPHA")

        message = (
            "If you are baking textures, see Bake Textures menu for haircard"
            + "baking resolution."
        )

        draw_paragraph(self.layout, text=message, enabled=False)


class HG_PT_RIG(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_RIG"
    bl_label = "Bone Renaming"
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

    def draw(self, context):
        box = self.layout.box()
        sett = context.scene.HG3D  # type:ignore[attr-defined]
        pr_sett = sett.process

        self.draw_subtitle("Output", box, icon="SETTINGS")

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

        col = box.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.5
        row.prop(pr_sett, "output", text="")
        row = col.row(align=True)
        row.scale_y = 1.5
        row.alert = True
        row.operator("hg3d.process", text="Process", depress=True, icon="COMMUNITY")

        human = Human.from_existing(context.object)
        self.layout.operator(
            "wm.url_open", text="Process Guide", icon="URL", emboss=False
        ).url = "https://help.humgen3d.com/process/overview"
        self.draw_warning_labels(pr_sett, human)

    def draw_warning_labels(self, pr_sett, human):
        col = self.layout.column()
        col.alert = True

        if pr_sett.haircards_enabled:
            draw_paragraph(
                col,
                text="After adding haircards, you can't change the hair style anymore.",
            )

        if pr_sett.baking_enabled:
            draw_paragraph(
                col,
                text="Baking is enabled. This will take a long time."
                "Also, you won't be able to change the material settings"
                " anymore.",
            )

        if pr_sett.lod_enabled:
            draw_paragraph(
                col,
                text="LOD is enabled. Many features won't work anymore."
                "For example, you can't change the height, proportions, add hair, etc.",
            )

        if pr_sett.rig_renaming_enabled:
            draw_paragraph(
                col,
                text="Rig renaming is enabled. You won't be able to"
                " change the height of the human anymore.",
            )

        if pr_sett.scripting_enabled:
            draw_paragraph(
                col,
                text="Custom scripts are enabled. These may cause"
                " certain Human Generator features to not work anymore"
                " after processing this human.",
            )
