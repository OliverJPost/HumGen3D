# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from sys import platform

import bpy
from HumGen3D.user_interface.panel_functions import draw_paragraph

from ..ui_baseclasses import MainPanelPart, subpanel_draw


class HG_PT_SKIN(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_SKIN"
    phase_name = "skin"

    @subpanel_draw
    def draw(self, context):
        """Collapsable section with options for changing the shader of the human."""
        sett = self.sett

        col = self.layout.column()

        if self.human.process.was_baked:
            col.alert = True
            draw_paragraph(col, "Textures are baked! Baked textures can't be changed.")
            return

        self._draw_texture_subsection(sett, col)
        self._draw_main_skin_subsection(sett, col)
        self._draw_freckles_subsection(sett, col)
        self._draw_eye_subsection(sett, col)

        gender = self.human.gender
        if gender == "female":
            self._draw_makeup_subsection(sett, col)
        else:
            self._draw_beard_shadow_subsection(sett, col)

    def _draw_main_skin_subsection(self, sett, box):
        """Collapsable section with main sliders of skin effects.

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of the skin section
            nodes (Shadernode list): All nodes in the .human material
        """
        is_open, boxbox = self.draw_sub_spoiler(
            box, sett.ui, "main_skin", "⚙️ Main settings"
        )
        if not is_open:
            return

        col = boxbox.column(align=True)
        col.scale_y = 1.2

        col.operator(
            "hg3d.random_value", text="Randomize skin", icon="FILE_REFRESH"
        ).random_type = "skin"

        col.separator()
        skin = self.human.skin
        skin.tone.draw_prop(col, "Tone")
        skin.redness.draw_prop(col, "Redness")
        skin.saturation.draw_prop(col, "Saturation")

        col.separator()

        skin.normal_strength.draw_prop(col, "Normal Strength")
        skin.roughness_multiplier.draw_prop(col, "Roughness mult.")

        col.separator()

        row = col.row()
        row.label(text="Subsurface scattering")
        row.operator(
            "hg3d.showinfo", text="", icon="QUESTION", emboss=False
        ).info = "subsurface"

        row = col.row(align=True)
        row.prop(sett, "skin_sss", expand=True)

        col.label(text="Underwear:")
        row = col.row(align=True)
        row.prop(sett, "underwear_switch", expand=True)

    def _draw_texture_subsection(self, sett, box):
        """Shows a template_icon_view for different texture options.

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of the skin section
        """
        is_open, boxbox = self.draw_sub_spoiler(box, sett.ui, "texture", "🌃 Texture sets")
        if not is_open:
            return

        self.draw_content_selector(layout=boxbox, pcoll_name="texture")

    def _draw_eye_subsection(self, sett, col):
        is_open, boxbox = self.draw_sub_spoiler(col, sett.ui, "eyes", "👁️ Eyes")
        if not is_open:
            return

        mat = self.human.objects.eyes.data.materials[1]
        nodes = mat.node_tree.nodes

        col = boxbox.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False
        row = col.row(align=True)

        eyes = self.human.eyes
        eyes.iris_color.draw_prop(row, "Iris Color")
        row.operator(
            "hg3d.random_value", text="", icon="FILE_REFRESH"
        ).random_type = "eyes"
        eyes.sclera_color.draw_prop(col, "Sclera Color")

    def _draw_freckles_subsection(self, sett, box):
        """Collapsable section with sliders for freckles.

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of the skin section
            nodes (Shadernode list): All nodes in the .human material
        """
        is_open, boxbox = self.draw_sub_spoiler(box, sett.ui, "freckles", "⋰ Freckles")
        if not is_open:
            return

        col = boxbox.column(align=True)
        col.scale_y = 1.2
        self.human.skin.freckles.draw_prop(col, "Freckles")
        self.human.skin.splotches.draw_prop(col, "Splotches")

    def _draw_makeup_subsection(self, sett, box):
        """Collapsable section with sliders for makeup.

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of the skin section
            nodes (Shadernode list): All nodes in the .human material
        """
        is_open, boxbox = self.draw_sub_spoiler(box, sett.ui, "makeup", "Makeup")
        if not is_open:
            return

        nodes = self.human.skin.nodes

        makeup_node = nodes["Gender_Group"]

        # TODO make loop. First try failed, don't remember why
        flow = self._get_skin_flow(boxbox, "Foundation:")
        flow.prop(
            makeup_node.inputs["Foundation Amount"],
            "default_value",
            text="Amount",
            slider=True,
        )
        flow.prop(
            makeup_node.inputs["Foundation Color"],
            "default_value",
            text="Color",
        )

        flow = self._get_skin_flow(boxbox, "Blush:")
        flow.prop(
            makeup_node.inputs["Blush Opacity"],
            "default_value",
            text="Opacity",
            slider=True,
        )
        flow.prop(makeup_node.inputs["Blush Color"], "default_value", text="Color")

        flow = self._get_skin_flow(boxbox, "Eyeshadow:")
        flow.prop(
            makeup_node.inputs["Eyeshadow Opacity"],
            "default_value",
            text="Opacity",
            slider=True,
        )
        flow.prop(
            makeup_node.inputs["Eyeshadow Color"],
            "default_value",
            text="Color",
        )

        flow = self._get_skin_flow(boxbox, "Lipstick:")
        flow.prop(
            makeup_node.inputs["Lipstick Opacity"],
            "default_value",
            text="Opacity",
            slider=True,
        )
        flow.prop(makeup_node.inputs["Lipstick Color"], "default_value", text="Color")

        flow = self._get_skin_flow(boxbox, "Eyeliner:")
        flow.prop(
            makeup_node.inputs["Eyeliner Opacity"],
            "default_value",
            text="Opacity",
            slider=True,
        )
        flow.prop(makeup_node.inputs["Eyeliner Color"], "default_value", text="Color")

        return  # TODO hide eyebrow section until issue resolved
        flow = self.skin_section_flow(boxbox, "Eyebrows:")

        flow.prop(
            makeup_node.inputs["Eyebrows Opacity"],
            "default_value",
            text="Opacity",
            slider=True,
        )
        flow.prop(makeup_node.inputs["Eyebrows Color"], "default_value", text="Color")

    def _get_skin_flow(self, layout, label):
        """Generates a property split layout.

        Args:
            layout (UILayout): boxbox from makeup/beard section
            label (str): Name for the ui section

        Returns:
            UILayout: layout with property split and title bar
        """
        row = layout.row()
        row.alignment = "CENTER"
        row.label(text=label, icon="HANDLETYPE_AUTO_CLAMP_VEC")

        flow = self.get_flow(layout)
        flow.scale_y = 1.2

        return flow

    def _draw_beard_shadow_subsection(self, sett, box):
        """Collapsable section with sliders for beard shadow.

        Args:
            sett (PropertyGroup): HumGen propss
            box (UILayout): layout.box of the skin section
            nodes (Shadernode list): All nodes in the .human material
        """
        is_open, boxbox = self.draw_sub_spoiler(
            box, sett.ui, "beard_shadow", "🧔 Beard Shadow"
        )
        if not is_open:
            return

        nodes = self.human.skin.nodes

        beard_node = nodes["Gender_Group"]

        flow = self.get_flow(boxbox)
        flow.scale_y = 1.2
        self.human.skin.gender_specific.mustache_shadow.draw_prop(flow, "Mustache")
        self.human.skin.gender_specific.beard_shadow.draw_prop(flow, "Mustache")
