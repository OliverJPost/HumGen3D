# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

from sys import platform

import bpy

from ..panel_functions import draw_sub_spoiler
from ..ui_baseclasses import MainPanelPart, subpanel_draw


class HG_PT_SKIN(MainPanelPart, bpy.types.Panel):
    bl_idname = "HG_PT_SKIN"
    phase_name = "skin"

    @subpanel_draw
    def draw(self, context):
        """Collapsable section with options for changing the shader of the human."""
        sett = self.sett

        col = self.layout.column()

        if "hg_baked" in self.human.rig_obj:
            col.label(text="Textures are baked", icon="INFO")
            return

        self._draw_texture_subsection(sett, col)
        self._draw_main_skin_subsection(sett, col)
        self._draw_freckles_subsection(sett, col)

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
        is_open, boxbox = draw_sub_spoiler(box, sett, "main_skin", "Main settings")
        if not is_open:
            return

        col = boxbox.column(align=True)
        col.scale_y = 1.2

        col.operator(
            "hg3d.random_value", text="Randomize skin", icon="FILE_REFRESH"
        ).random_type = "skin"

        col.separator()
        nodes = self.human.skin.nodes
        tone_node = nodes["Skin_tone"]
        col.prop(tone_node.inputs[1], "default_value", text="Tone", slider=True)
        col.prop(tone_node.inputs[2], "default_value", text="Redness", slider=True)
        if len(tone_node.inputs) > 3:
            col.prop(
                tone_node.inputs[3],
                "default_value",
                text="Saturation",
                slider=True,
            )

        col.separator()

        normal_node = nodes["Normal Map"]
        r_node = nodes["R_Multiply"]
        col.prop(normal_node.inputs[0], "default_value", text="Normal Strength")
        col.prop(r_node.inputs[1], "default_value", text="Roughness mult.")

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
        is_open, boxbox = draw_sub_spoiler(box, sett, "texture", "Texture sets")
        if not is_open:
            return

        self.draw_content_selector(layout=boxbox, pcoll_name="texture")

    def _draw_age_subsection(self, sett, box):
        """Collapsable section with sliders age effects.

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of the skin section
            nodes (Shadernode list): All nodes in the .human material
        """
        is_open, boxbox = draw_sub_spoiler(box, sett, "age", "Age")
        if not is_open:
            return

        hg_body = self.human.body_obj
        sk = hg_body.data.shape_keys.key_blocks

        nodes = self.human.skin.nodes

        age_sk = sk["age_old.Transferred"]
        age_node = nodes["HG_Age"]

        col = boxbox.column(align=True)
        col.scale_y = 1.2
        col.prop(age_sk, "value", text="Skin sagging [Mesh]", slider=True)
        col.prop(age_node.inputs[1], "default_value", text="Wrinkles", slider=True)

    def _draw_freckles_subsection(self, sett, box):
        """Collapsable section with sliders for freckles.

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of the skin section
            nodes (Shadernode list): All nodes in the .human material
        """
        is_open, boxbox = draw_sub_spoiler(box, sett, "freckles", "Freckles")
        if not is_open:
            return

        nodes = self.human.skin.nodes

        freckles_node = nodes["Freckles_control"]
        splotches_node = nodes["Splotches_control"]

        col = boxbox.column(align=True)
        col.scale_y = 1.2
        col.prop(
            freckles_node.inputs["Pos2"],
            "default_value",
            text="Freckles",
            slider=True,
        )
        col.prop(
            splotches_node.inputs["Pos2"],
            "default_value",
            text="Splotches",
            slider=True,
        )

    def _draw_makeup_subsection(self, sett, box):
        """Collapsable section with sliders for makeup.

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of the skin section
            nodes (Shadernode list): All nodes in the .human material
        """
        is_open, boxbox = draw_sub_spoiler(box, sett, "makeup", "Makeup")
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

        flow = self.get_flow(self.sett, layout)
        flow.scale_y = 1.2

        return flow

    def _draw_beautyspots_subsection(self, sett, box):
        """Collapsable section with sliders for beautyspots.

        Args:
            sett (PropertyGroup): HumGen props
            box (UILayout): layout.box of the skin section
            nodes (Shadernode list): All nodes in the .human material
        """
        if platform == "darwin":  # not compatible with MacOS 8-texture material
            return

        is_open, boxbox = draw_sub_spoiler(box, sett, "beautyspots", "Beauty Spots")
        if not is_open:
            return

        nodes = self.human.skin.nodes

        bs_node = nodes["BS_Control"]
        opacity_node = nodes["BS_Opacity"]

        col = boxbox.column(align=True)
        col.scale_y = 1.2
        col.prop(bs_node.inputs[2], "default_value", text="Amount", slider=True)
        col.prop(
            opacity_node.inputs[1],
            "default_value",
            text="Opacity",
            slider=True,
        )
        col.prop(bs_node.inputs[1], "default_value", text="Seed [Randomize]")

    def _draw_beard_shadow_subsection(self, sett, box):
        """Collapsable section with sliders for beard shadow.

        Args:
            sett (PropertyGroup): HumGen propss
            box (UILayout): layout.box of the skin section
            nodes (Shadernode list): All nodes in the .human material
        """
        is_open, boxbox = draw_sub_spoiler(box, sett, "beard_shadow", "Beard Shadow")
        if not is_open:
            return

        nodes = self.human.skin.nodes

        beard_node = nodes["Gender_Group"]

        flow = self.get_flow(boxbox)
        flow.scale_y = 1.2
        flow.prop(beard_node.inputs[2], "default_value", text="Mustache", slider=True)
        flow.prop(beard_node.inputs[3], "default_value", text="Beard", slider=True)
