# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE


import bpy
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

    @classmethod
    def poll(cls, context):
        return Human.find_multiple_in_list(context.selected_objects)

    def draw_header(self, context):
        if hasattr(self, "enabled_propname"):
            # retreiver = attrgetter(self.propspace)
            # propgroup = retreiver(context.scene.HG3D  # type:ignore[attr-defined]
            self.layout.prop(context.scene.HG3D.process, self.enabled_propname, text="")
        try:
            self.layout.label(text="", icon_value=get_hg_icon(self.icon_name))
        except KeyError:
            self.layout.label(text="", icon=self.icon_name)


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
        row.operator("hg3d.bake", text="", icon="ADD")

        box = col.box()
        human_rigs = Human.find_multiple_in_list(context.selected_objects)
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
    enabled_propname = "bake"

    def draw(self, context):
        layout = self.layout
        layout.enabled = getattr(context.scene.HG3D.process, self.enabled_propname)

        sett = context.scene.HG3D  # type:ignore[attr-defined]
        bake_sett = sett.bake

        if self._draw_baking_warning_labels(context, layout):
            return

        col = get_flow(sett, layout)
        self.draw_centered_subtitle("Quality", col, "SETTINGS")
        col.prop(bake_sett, "samples", text="Samples")

        layout.separator()

        col = get_flow(sett, layout)

        self.draw_centered_subtitle("Resolution", col, "IMAGE_PLANE")

        for res_type in ["body", "eyes", "teeth", "clothes"]:
            col.prop(bake_sett, f"res_{res_type}", text=res_type.capitalize())

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

        if "hg_baked" in human.rig_obj:
            if context.scene.HG3D.batch_idx:
                layout.label(text="Baking in progress")
            else:
                layout.label(text="Already baked")

            return True

        return False


class HG_PT_MODAPPLY(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_MODAPPLY"
    bl_label = "Apply Modifiers"
    icon_name = "MOD_SUBSURF"
    enabled_propname = "modapply_enabled"

    def draw(self, context):
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
        col.prop(sett, "modapply_search_modifiers", text="")

        row = col.row(align=True)
        row.operator("hg3d.ulrefresh", text="Refresh").uilist_type = "modapply"
        row.operator("hg3d.selectmodapply", text="All").select_all = True
        row.operator("hg3d.selectmodapply", text="None").select_all = False

        col = layout.column(align=True)
        col.label(text="Objects to apply:")
        row = col.row(align=True)
        row.prop(sett, "modapply_search_objects", text="")

        layout.separator()
        col = layout.column(align=True)
        self.draw_centered_subtitle("Options", col, "SETTINGS")
        col.prop(sett, "modapply_keep_shapekeys", text="Keep shapekeys")
        col.prop(sett, "modapply_apply_hidden", text="Apply hidden modifiers")


class HG_PT_LOD(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_LOD"
    bl_label = "Levels of Detail"
    icon_name = "NORMALS_VERTEX"
    enabled_propname = "lod_enabled"

    def draw(self, context):
        col = self.layout.column()
        col.label(text="Output(s):")
        lod_output_col = context.scene.lod_output_col
        for output in lod_output_col:
            self._draw_output_box(col, output)
        col.operator("hg3d.add_lod_output", text="", icon="ADD")

    def _draw_output_box(self, col, output_item):
        col = col.box().column()
        row = col.row(align=True)
        row.prop(
            output_item,
            "menu_open",
            text="",
            icon="TRIA_DOWN" if output_item.menu_open else "TRIA_RIGHT",
            emboss=False,
        )
        row.prop(output_item, "suffix", text="")
        row.operator(
            "hg3d.remove_lod_output", text="", icon="TRASH"
        ).name = output_item.name

        if not output_item.menu_open:
            return

        col.separator()

        self.draw_centered_subtitle("Body LOD", col, icon=get_hg_icon("body"))
        col.prop(output_item, "body_lod", text="")

        col.separator()
        self.draw_centered_subtitle("Clothing", col, icon=get_hg_icon("outfit"))
        col.prop(output_item, "decimate_ratio", text="Decimate ratio")
        col.prop(output_item, "remove_clothing_subdiv", text="Remove clothing subdiv")
        col.prop(
            output_item, "remove_clothing_solidify", text="Remove clothing solidify"
        )

        col.label(text="Texture resolution:")


class HG_PT_HAIRCARDS(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_HAIRCARDS"
    bl_label = "Haircards"
    icon_name = "hair"
    enabled_propname = "haircards_enabled"

    def draw(self, context):
        self.layout.label(text="test")


class HG_PT_RIG(ProcessPanel, bpy.types.Panel):
    bl_idname = "HG_PT_RIG"
    bl_label = "Rig options"
    icon_name = "MOD_ARMATURE"
    enabled_propname = "rig_enabled"

    def draw(self, context):
        self.layout.label(text="test")


class HG_PT_Z_PROCESS_LOWER(ProcessPanel, bpy.types.Panel):
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        box = self.layout.box()
        sett = context.scene.HG3D  # type:ignore[attr-defined]
        process_sett = sett.process

        self.draw_centered_subtitle("Output", box, icon="SETTINGS")

        if process_sett.bake:
            col = box.column(align=True)
            col.use_property_split = True
            col.use_property_decorate = False
            bake_sett = sett.bake
            col.prop(bake_sett, "file_type", text="Format:")
            col.prop(bake_sett, "export_folder", text="Tex. Folder")

            row = col.row()
            row.alignment = "RIGHT"
            row.label(text="HG folder when empty", icon="INFO")

        col = box.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.5
        row.prop(process_sett, "output", text="")
        row = col.row(align=True)
        row.scale_y = 1.5
        row.alert = True
        row.operator("hg3d.process", text="Process", depress=True, icon="COMMUNITY")
