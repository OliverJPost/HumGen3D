# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy
from HumGen3D.backend import get_prefs
from HumGen3D.batch_generator.batch_functions import (
    get_batch_marker_list,
    height_from_bell_curve,
)
from HumGen3D.user_interface.icons.icons import get_hg_icon
from HumGen3D.user_interface.ui_baseclasses import draw_icon_title

from ..documentation.tips_suggestions_ui import draw_tips_suggestions_ui
from ..panel_functions import draw_panel_switch_header, draw_paragraph, get_flow


class Batch_PT_Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"

    def Header(self, _):
        return True


class HG_PT_BATCH_Panel(Batch_PT_Base, bpy.types.Panel):
    bl_idname = "HG_PT_Batch_Panel"
    bl_label = "Batch"  # Tab name

    @classmethod
    def poll(cls, context):
        sett = context.scene.HG3D  # type:ignore[attr-defined]
        return sett.ui.active_tab == "BATCH" and not sett.ui.content_saving

    def draw_header(self, context):
        draw_panel_switch_header(
            self.layout, context.scene.HG3D
        )  # type:ignore[attr-defined]

    def draw(self, context):
        layout = self.layout
        batch_sett = context.scene.HG3D.batch

        col = layout.column(align=True)

        row = col.row(align=True)
        row.scale_x = 0.7
        row.alignment = "CENTER"
        draw_icon_title("Batch Generator", row, True)
        col.separator(factor=0.5)
        draw_paragraph(
            col,
            "Generate many humans in one go!",
            alignment="CENTER",
            enabled=False,
        )
        col.separator(factor=0.5)

        col = col.column(align=True)
        col.scale_y = 1.5
        col.prop(batch_sett, "marker_selection", text="")

        marker_total = len(get_batch_marker_list(context))

        col = col.column(align=True)
        if batch_sett.idx:
            col.prop(batch_sett, "progress", text=f"Building Human {batch_sett.idx}")
        else:
            col.alert = True
            col.operator(
                "hg3d.generate",
                text=f"Generate {marker_total} humans",
                depress=True,
                icon="TIME",
            ).run_immediately = False


class HG_PT_B_GENERATION_PROBABILITY(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = "Generation Probability"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(text="", icon="MOD_TINT")

    def draw(self, context):
        layout = self.layout
        batch_sett = context.scene.HG3D.batch

        col = layout.column(align=True)

        flow = get_flow(batch_sett, col)
        flow.separator()
        flow.prop(batch_sett, "male_chance")
        flow.prop(batch_sett, "female_chance")
        flow.separator()

        flow.prop(batch_sett, "caucasian_chance")
        flow.prop(batch_sett, "black_chance")
        flow.prop(batch_sett, "asian_chance")


class HG_PT_B_HEIGHT_VARIATION(bpy.types.Panel, Batch_PT_Base):
    """Subpanel with options for height variation in the generation of batch humans."""

    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = "Height variation"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_hg_icon("height"))

    def draw(self, context):
        layout = self.layout
        batch_sett = context.scene.HG3D.batch

        row = layout.box().row(align=True)
        row.scale_y = 1.5
        row.prop(batch_sett, "height_system", expand=True)

        layout.label(text="Average height:", icon="EMPTY_SINGLE_ARROW")

        self._draw_average_height_props(layout, batch_sett)

        layout.separator()
        layout.label(text="Bell curve settings:", icon="SMOOTHCURVE")

        col = layout.column(align=True)
        col.prop(batch_sett, "standard_deviation", slider=False)

        box = layout.box()
        box.prop(
            batch_sett,
            "show_height_examples",
            text="Show height examples",
            icon="TRIA_DOWN" if batch_sett.show_height_examples else "TRIA_RIGHT",
            emboss=False,
            toggle=True,
        )
        if batch_sett.show_height_examples:
            split = box.split()
            for gender in ["male", "female"]:
                col_l = split.column()
                col_l.separator()
                col_l.label(text=f"{gender.capitalize()} examples:")

                self._draw_examples_list(col_l, batch_sett, gender)

    def _draw_average_height_props(self, layout, batch_sett):
        """Draws props for the user to select the average height.

        In either metric or imperial system.

        Args:
            layout (UILayout): layout to draw in
            sett (PropertyGroup): addon props
        """
        col = layout.column(align=True)
        if batch_sett.height_system == "metric":
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(batch_sett, "average_height_cm_male")
            col.prop(batch_sett, "average_height_cm_female")
        else:
            for gender in ["male", "female"]:
                row = col.row(align=True)
                row.label(text=gender.capitalize())
                row.prop(batch_sett, f"average_height_ft_{gender}")
                row.prop(batch_sett, f"average_height_in_{gender}")

    def _draw_examples_list(self, layout, batch_sett, gender):
        """Draws a list of example heights based on the settings the user selected.

        Args:
            layout (UILayout): layout to draw in
            sett (PropertyGroup): Add-on preferences
            gender (str): 'male' or 'female', determines which average height to
                sample from.
        """
        if batch_sett.height_system == "metric":
            avg_height_cm = getattr(batch_sett, f"average_height_cm_{gender}")
        else:
            ft = getattr(batch_sett, f"average_height_ft_{gender}")
            inch = getattr(batch_sett, f"average_height_in_{gender}")
            avg_height_cm = ft * 30.48 + inch * 2.54

        length_list = height_from_bell_curve(
            avg_height_cm, batch_sett.standard_deviation, random_seed=False, samples=10
        )

        col = layout.column(align=True)
        col.scale_y = 0.8

        for i in length_list:
            length_m = round(i / 100, 2)

            length_label = self._unit_conversion(batch_sett, length_m)

            row = col.row(align=True)
            row.alert = i > 200 or i < 150
            row.label(text=length_label)

    def _unit_conversion(self, sett, length_m):
        if sett.batch_height_system == "imperial":
            length_feet = length_m / 0.3048
            length_inches = int(length_feet * 12.0 - int(length_feet) * 12.0)
            length_label = str(int(length_feet)) + "' " + str(length_inches) + '"'
        else:
            # Add 0 for vertical alignment if float has 1 decimal
            alignment = "0 " if len(str(length_m)) == 3 else " "
            length_label = str(length_m) + alignment + "m"

        return length_label


class HG_PT_B_QUALITY(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = "Quality"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(text="", icon="OPTIONS")

    def draw(self, context):
        layout = self.layout
        batch_sett = context.scene.HG3D.batch

        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False

        col.label(text="Texture resolution:", icon="IMAGE_PLANE")
        col.prop(batch_sett, "texture_resolution", text="")

        # col.separator()

        # col.label(text = 'Polygon reduction [BETA]:', icon = 'MOD_DECIM')
        # col.prop(sett, 'batch_poly_reduction', text = '')


class HG_PT_B_HAIR(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = " Hair"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        header(self, context, "hair")
        self.layout.label(text="", icon_value=get_hg_icon("hair"))

    def draw(self, context):
        layout = self.layout
        batch_sett = context.scene.HG3D.batch
        layout.enabled = batch_sett.batch_hair

        row = layout.row(align=True)
        row.scale_y = 1.5
        row.prop(batch_sett, "hairtype", expand=True)
        if batch_sett.hairtype == "particle":
            layout.prop(
                batch_sett,
                "hair_quality_{}".format(batch_sett.batch_hairtype),
                text="Quality",
            )
        else:
            col = layout.column()
            col.alert = True
            col.label(text="Coming soon!")


class HG_PT_B_CLOTHING(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = " Clothing"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        header(self, context, "clothing")
        self.layout.label(text="", icon_value=get_hg_icon("clothing"))

    def draw(self, context):
        layout = self.layout
        batch_sett = context.scene.HG3D.batch
        layout.enabled = batch_sett.clothing

        col = layout.column(align=True)
        box = col.box().row()
        box.label(text="Select libraries:")
        box.operator("hg3d.refresh_batch_uilists", text="", icon="FILE_REFRESH")

        # col.scale_y = 1.5
        row = col.row(align=False)
        row.template_list(
            "HG_UL_BATCH_CLOTHING",
            "",
            context.scene,
            "batch_clothing_col",
            context.scene,
            "batch_clothing_col_index",
        )

        col = layout.column()
        count = sum(
            [
                (item.male_items + item.female_items)
                for item in context.scene.batch_clothing_col
                if item.enabled
            ]
        )

        if count == 0:
            col.alert = True

        col.label(text="Total: {} Outfits".format(count))


class HG_PT_B_EXPRESSION(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = " Expression"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        header(self, context, "expression")
        self.layout.label(text="", icon_value=get_hg_icon("expression"))

    def draw(self, context):
        layout = self.layout
        batch_sett = context.scene.HG3D.batch
        layout.enabled = batch_sett.expression

        col = layout.column(align=True)
        box = col.box().row()
        box.label(text="Select libraries:")
        box.operator("hg3d.refresh_batch_uilists", text="", icon="FILE_REFRESH")
        col = col.column()
        col.template_list(
            "HG_UL_BATCH_EXPRESSIONS",
            "",
            context.scene,
            "batch_expression_col",
            context.scene,
            "batch_expression_col_index",
        )

        count = sum(
            [item.count for item in context.scene.batch_expression_col if item.enabled]
        )
        if count == 0:
            col.alert = True
        col.label(text="Total: {} Expressions".format(count))


# class HG_PT_B_BAKING(Batch_PT_Base, bpy.types.Panel):
#     bl_parent_id = "HG_PT_Batch_Panel"
#     bl_label = " Bake textures"
#     bl_options = {"DEFAULT_CLOSED"}

#     @classmethod
#     def poll(cls, context):
#         return False

#     def draw_header(self, context):
#         header(self, context, "bake")
#         self.layout.label(text="", icon="RENDERLAYERS")

#     def draw(self, context):
#         layout = self.layout
#         sett = context.scene.HG3D  # type:ignore[attr-defined]
#         layout.enabled = sett.batch_bake

#         col = get_flow(sett, layout.box())
#         col.prop(sett, "bake_samples", text="Quality")

#         col = get_flow(sett, layout.box())

#         draw_resolution_box(sett, col, show_batch_comparison=True)

#         col = get_flow(sett, layout.box())
#         col.prop(sett, "bake_export_folder", text="Output Folder:")

#         row = col.row()
#         row.alignment = "RIGHT"
#         row.label(text="HumGen folder when left empty", icon="INFO")
#         col.prop(sett, "bake_file_type", text="Format:")


def header(self, context, categ):
    sett = context.scene.HG3D  # type:ignore[attr-defined]
    layout = self.layout
    layout.prop(sett.batch, categ, text="")


class HG_PT_BATCH_TIPS(Batch_PT_Base, bpy.types.Panel):
    bl_parent_id = "HG_PT_Batch_Panel"
    bl_label = "Tips and suggestions!"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return get_prefs().show_tips

    def draw(self, context):
        layout = self.layout

        draw_tips_suggestions_ui(layout, context)

        if get_prefs().full_height_menu:
            layout.separator(factor=200)
