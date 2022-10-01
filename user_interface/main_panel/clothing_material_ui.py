# Copyright (c) 2022 Oliver J. Post & Alexander Lashko - GNU GPL V3.0, see LICENSE

import bpy
from HumGen3D.backend import preview_collections
from HumGen3D.human.human import Human
from HumGen3D.user_interface.icons.icons import get_hg_icon

from ..panel_functions import get_flow, searchbox


class HG_PT_CLOTHMAT(bpy.types.Panel):
    bl_idname = "HG_PT_CLOTHMAT"
    bl_label = "HumGen"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HumGen"

    @classmethod
    def poll(cls, context):
        if not context.object:
            return False

        return "cloth" in context.object or "shoe" in context.object

    # TODO add compatibility with any material, not just standard material
    def draw(self, context):
        """draws ui for changing the material of the active clothing object"""
        layout = self.layout
        self.sett = context.scene.HG3D
        self.human = Human.from_existing(context.object, strict_check=False)
        if "hg_baked" in self.human.rig_obj:
            layout.label(text="Textures are baked", icon="INFO")
            return

        sett = self.sett

        col = layout.column(align=True)

        self._draw_clothmat_header(context, col)

        nodes = context.object.data.materials[0].node_tree.nodes
        control_node = nodes["HG_Control"]

        self._draw_clothmat_color_subsection(layout, control_node)
        self._draw_clothmat_options_subsection(layout, control_node)

        if "Pattern" in control_node.inputs:
            self._draw_pattern_subsection(sett, layout, control_node)

    def _draw_clothmat_header(self, context, col):
        """Draws header for the clothing material UI, with clothing name,
        button to go back to normal UI and button to delete clothing item

        Args:
            context (bpy.context): Blender context
            hg_icons (list): icon preview collection
            col (UILayout): column of clothing material UI
        """
        box = col.box().row()
        box.scale_y = 1.5
        box.alignment = "CENTER"
        box.label(
            text=context.object.name.replace("_", " ").replace("HG", ""),
            icon_value=(
                get_hg_icon("outfit")
                if "cloth" in context.object
                else get_hg_icon("footwear")
            ),
        )

        col.operator(
            "hg3d.backhuman",
            text="Go back to human",
            icon="RESTRICT_SELECT_OFF",
            depress=True,
        )
        alert_col = col.column(align=True)
        alert_col.alert = True
        alert_col.operator(
            "hg3d.deletecloth",
            text="Delete clothing item",
            icon="TRASH",
            depress=True,
        )

    def _draw_clothmat_color_subsection(self, layout, control_node):
        """draws subsection for changing colors of the different zones on this
        clothing material

        Args:
            layout (UILAyout): layout of clothmat section
            control_node (ShaderNodeGroup): node that controls the clot material
        """
        color_flow, _ = self.make_box_flow(layout, "Colors", "COLOR")

        for node_input in [control_node.inputs[i] for i in (4, 5, 6)]:
            if node_input.name:
                self._draw_color_row(color_flow, node_input)

    def _draw_color_row(self, color_flow, node_input):
        """Draws color picker and color randomize button on row

        Args:
            color_flow (UILayout): indented list where color pickers are placed
            node_input (ShaderNodeInput): input of the color value on group node
        """

        color_dict = {
            "C0": [
                "88C1FF",
                "5C97FF",
                "F5FFFF",
                "777C7F",
                "2F3133",
                "46787B",
                "9EC4BD",
                "7B366F",
                "5B7728",
                "1F3257",
            ]
        }

        color_groups = tuple(["_{}".format(name) for name in color_dict])
        color_group = (
            node_input.name[-2:] if node_input.name.endswith(color_groups) else None
        )

        row = color_flow.row(align=False)
        row.prop(
            node_input,
            "default_value",
            text=node_input.name[:-3] if color_group else node_input.name,
        )

        if not color_group:
            return

        c_random = row.operator("hg3d.color_random", text="", icon="FILE_REFRESH")
        c_random.input_name = node_input.name
        c_random.color_group = color_group

    def _draw_clothmat_options_subsection(self, layout, control_node):
        """draws sliders for roughness, normal and any custom values on group

        Args:
            layout (UILAyout): main layout of clothmat section
            control_node (ShaderNodeGroup): control node group of cloth material
        """
        flow, _ = self.make_box_flow(layout, "Options", "OPTIONS")

        for input_idx, node_input in enumerate(control_node.inputs):
            if (input_idx > 13 and not node_input.is_linked) or node_input.name in [
                "Roughness Multiplier",
                "Normal Strength",
            ]:
                flow.prop(node_input, "default_value", text=node_input.name)

    def _draw_pattern_subsection(self, sett, layout, control_node):
        """draws subsection for adding patterns to this clothing item

        Args:
            sett (PropertyGroup): HumGen props
            layout (UILayout): layout of clothmat section
            control_node (ShaderNodeGroup): control nodegroup of cloth material
        """
        p_flow, p_box = self.make_box_flow(layout, "Pattern", "NODE_TEXTURE")

        pattern = True if control_node.inputs[9].is_linked else False

        if pattern:
            self._draw_pattern_selector_ui(sett, control_node, p_flow)
            self._draw_pattern_color_ui(sett, control_node, p_flow)

        row = p_box.row(align=True)
        row.scale_y = 1.3
        row.operator(
            "hg3d.pattern",
            text="Remove" if pattern else "Add Pattern",
            icon="TRASH" if pattern else "TEXTURE",
        ).add = (
            False if pattern else True
        )

        if pattern:
            row.popover(
                panel="HG_PT_ROT_LOC_SCALE",
                text="Transform",
                icon="ORIENTATION_GLOBAL",
            )

    def _draw_pattern_selector_ui(self, sett, control_node, p_flow):
        """draws template_icon_view for adding patterns

        Args:
            sett (PropertyGroup): HumGen props
            control_node (ShaderNodeGroup): control nodegroup of cloth material
            p_flow (UILayout): layout where the pattern stuff is drawn in
        """
        searchbox(sett, "pattern", p_flow)

        col = p_flow.column(align=False)
        col.scale_y = 0.8
        col.template_icon_view(
            sett.pcoll, "pattern", show_labels=True, scale=5, scale_popup=6
        )

    def _draw_pattern_color_ui(self, sett, control_node, p_flow):
        """shows sliders and options for manipulating the pattern colors

        Args:
            sett (PropertyGroup): HumGen props
            control_node (ShaderNodeGRoup): control nodegroup of cloth materiaL
            p_flow (UILAyout): layout pattern ui is drawn in
        """
        row_h = p_flow.row(align=True)
        row_h.scale_y = 1.5 * 0.8  # quick fix because history
        row_h.prop(sett, "pattern_category", text="")
        row_h.operator(
            "hg3d.random_choice", text="Random", icon="FILE_REFRESH"
        ).pcoll_name = "pattern"

        p_flow.separator()

        for input_idx, node_input in enumerate(
            [control_node.inputs[i] for i in ("PC1", "PC2", "PC3")]
        ):
            p_flow.prop(
                node_input,
                "default_value",
                text="Color {}".format(input_idx + 1),
            )

        p_flow.prop(
            control_node.inputs["Pattern Opacity"],
            "default_value",
            text="Opacity",
            slider=True,
        )

    def make_box_flow(self, layout, name, icon):
        """creates a box with title

        Args:
            layout (UILayout): layout to draw box in
            name (str): name to show as title
            icon (str): code for icon to display next to title

        Returns:
            tuple(flow, box):
                UILayout: flow below box
                UILayout: box itself
        """
        box = layout.box()

        row = box.row()
        row.alignment = "CENTER"
        row.label(text=name, icon=icon)

        flow = get_flow(self.sett, box)
        flow.scale_y = 1.2

        return flow, box


# TODO incorrect naming per Blender scheme
class HG_PT_ROT_LOC_SCALE(bpy.types.Panel):
    """
    Popover for the rot, loc and scale of the pattern
    """

    bl_label = "Pattern RotLocScale"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    def draw(self, context):
        layout = self.layout

        mat = context.object.active_material
        mapping_node = mat.node_tree.nodes["HG_Pattern_Mapping"]

        col = layout.column()

        col.label(text="Location")
        col.prop(mapping_node.inputs["Location"], "default_value", text="")

        col.label(text="Rotation")
        col.prop(mapping_node.inputs["Rotation"], "default_value", text="")

        col.label(text="Scale")
        col.prop(mapping_node.inputs["Scale"], "default_value", text="")
